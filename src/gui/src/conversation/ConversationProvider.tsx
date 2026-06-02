import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { fetchBootstrap } from "../api/bootstrap";
import { promoteSettingEntry } from "../api/promoteSettingEntry";
import { streamChat, type StreamChatEvent } from "../api/sseChat";
import type { ChatMessage } from "../types/chat";
import {
  panelSkillsFromBootstrap,
  resolveBootstrapUi,
} from "../types/bootstrap";
import { FALLBACK_PANEL_SKILLS } from "../skills/catalog";
import { getSkillMeta, hydrateSkillRegistry } from "../skills/registry";
import { conversationNavPath } from "../skills/routing";
import {
  conversationStateFromRecord,
  createEmptyConversationState,
  createEmptyReviewState,
  messagesForApi,
} from "./createEmptyConversation";
import { skillSupportsContinuousQa } from "../skills/continuousQa";
import {
  appendToolTraceToTurn,
  applyCitationToTurn,
  applyReactStepLimitToTurn,
  beginNewQaTurn,
  finalizeTurnTrace,
} from "./turnState";
import {
  finalizeStreamAssistantMessage,
  lastQaTurnHitStepLimit,
} from "./reactStepLimit";
import { generateConversationId } from "./generateId";
import {
  isConversationIpcAvailable,
  listConversationsIpc,
  readConversationIpc,
} from "./ipc";
import { deriveConversationTitle } from "./record";
import {
  bindConversationPersistGuard,
  bindConversationPersistSource,
  cancelConversationPersist,
  flushConversationPersist,
  scheduleConversationPersist,
} from "./persistScheduler";
import { notifyConversationsStorageChanged } from "./storageNotify";
import { currentAppPath, isConversationRoute } from "./routeUtils";
import {
  clearSessionDismissed,
  isSessionDismissed,
  markSessionDismissed,
} from "./sessionDismissed";
import type { ConversationState } from "./storeTypes";
import { buildConversationRecord } from "./record";
import { writeConversationIpc } from "./ipc";
import { normalizeInterruptedConversationState } from "./streamLifecycle";
import {
  notifyAllConversations,
  notifyConversation,
  subscribeAllConversations,
  subscribeConversation,
} from "./subscribe";

export type ConversationActions = {
  ensureOpenTab: (id: string) => void;
  createTab: () => string;
  /** Vite 范式试验台：多轮对话 + 可选 Skill / 范式覆盖 */
  createLabTab: () => string;
  /** 从技能面板创建单任务向导并进入 ``/task/:id`` */
  createTask: (skillId: string) => string;
  /** 多轮 Skill（如 chat_inspire）→ ``/chat/:id`` */
  createInspireChat: (skillId: string) => string;
  archiveTab: (id: string) => void;
  /** 从 /cache 恢复 archived → idle 并加入顶栏（F6-04） */
  restoreArchivedConversation: (id: string) => Promise<boolean>;
  clearUnread: (id: string) => void;
  patchConversation: (
    id: string,
    patch:
      | Partial<ConversationState>
      | ((prev: ConversationState) => ConversationState),
  ) => void;
  sendMessage: (id: string, text: string) => void;
  /** 任务向导：提交第二步输入并启动 SSE（须已绑定 skillId） */
  submitTaskRun: (id: string, text: string) => void;
  /** 任务页统一发送：连续问答同会话追加；触顶后自动新开 tab 并作为首问 */
  submitTaskSend: (id: string, text: string) => void;
  /** 检索问答：新开 tab（不归档当前会话） */
  createNewTopicTask: (skillId: string) => string;
  /** 完成后回到输入步（保留 skill，清空本轮消息） */
  resetTaskToInput: (id: string) => void;
  /** import_setting：将 setting_entry 草稿晋升至 KSFS（F6-08） */
  promotePipelineDrafts: (id: string) => Promise<void>;
  /** 从技能面板或 import_setting 创建审核晋升会话页。 */
  createReviewSession: (scope?: string) => void;
  stopStream: (id: string) => void;
};

export type ConversationMeta = {
  ready: boolean;
  openTabIds: string[];
  sseMaxNum: number;
  activeStreamCount: number;
  queueLength: number;
};

const ConversationActionsContext = createContext<ConversationActions | null>(
  null,
);

type StoreRuntime = {
  getState: (id: string) => ConversationState | undefined;
  getMeta: () => ConversationMeta;
  subscribe: (id: string, onChange: () => void) => () => void;
  subscribeMeta: (onChange: () => void) => () => void;
};

const ConversationRuntimeContext = createContext<StoreRuntime | null>(null);

function applyStreamEventToMessages(
  messages: ChatMessage[],
  ev: StreamChatEvent,
  acc: { assistantText: string; reasoningText: string },
): ChatMessage[] {
  const copy = [...messages];
  const last = copy.length - 1;
  if (last < 0 || copy[last].role !== "assistant") {
    return copy;
  }
  if (ev.kind === "reasoning_summary") {
    acc.reasoningText = ev.text;
    copy[last] = { ...copy[last], reasoning: acc.reasoningText };
  } else if (ev.kind === "reasoning_full") {
    acc.reasoningText += ev.text;
    copy[last] = { ...copy[last], reasoning: acc.reasoningText };
  } else if (ev.kind === "delta") {
    acc.assistantText += ev.text;
    copy[last] = {
      ...copy[last],
      content: acc.assistantText,
      reasoning: acc.reasoningText || copy[last].reasoning,
    };
  }
  return copy;
}

export function ConversationProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const activeIdRef = useRef<string | null>(null);
  const [ready, setReady] = useState(false);
  const [, setById] = useState<Record<string, ConversationState>>({});
  const [openTabIds, setOpenTabIds] = useState<string[]>([]);
  const openTabIdsRef = useRef<string[]>([]);

  const [sseMaxNum, setSseMaxNum] = useState(3);

  /** 须在 setById updater 内同步写入；勿在 render 中用 React state 覆盖（会冲掉未提交的 SSE patch）。 */
  const byIdRef = useRef<Record<string, ConversationState>>({});
  const sseMaxNumRef = useRef(sseMaxNum);
  sseMaxNumRef.current = sseMaxNum;
  const activeStreamCountRef = useRef(0);
  const queueRef = useRef<string[]>([]);
  const abortControllersRef = useRef<Map<string, AbortController>>(new Map());
  const pendingSendRef = useRef<Set<string>>(new Set());
  /** 已占用 SSE 槽位的会话 id（与 activeStreamCountRef 一一对应） */
  const streamSlotOwnersRef = useRef<Set<string>>(new Set());
  /** 归档/关闭过程中，禁止 ensureOpenTab 把标签重新加回顶栏 */
  const closingTabsRef = useRef<Set<string>>(new Set());
  const runStreamRef = useRef<(conversationId: string) => Promise<void>>(
    async () => {},
  );

  useEffect(() => {
    const m =
      location.pathname.match(/\/lab\/([^/]+)/) ??
      location.pathname.match(/\/chat\/([^/]+)/) ??
      location.pathname.match(/\/task\/([^/]+)/);
    activeIdRef.current = m?.[1] ?? null;
  }, [location.pathname]);

  const metaSnapshotRef = useRef<ConversationMeta>({
    ready: false,
    openTabIds: [],
    sseMaxNum: 3,
    activeStreamCount: 0,
    queueLength: 0,
  });

  const publishMeta = useCallback(() => {
    openTabIdsRef.current = openTabIds;
    metaSnapshotRef.current = {
      ready,
      openTabIds,
      sseMaxNum,
      activeStreamCount: activeStreamCountRef.current,
      queueLength: queueRef.current.length,
    };
    notifyAllConversations();
  }, [ready, openTabIds, sseMaxNum]);

  const commitConversationState = useCallback(
    (
      id: string,
      updater: (prev: ConversationState) => ConversationState,
    ) => {
      setById((prev) => {
        const merged = { ...prev, ...byIdRef.current };
        const cur = merged[id];
        if (!cur) {
          return prev;
        }
        const nextState = updater(cur);
        const next = { ...merged, [id]: nextState };
        byIdRef.current = next;
        notifyConversation(id);
        return next;
      });
    },
    [],
  );

  const syncQueueMeta = useCallback(() => {
    publishMeta();
  }, [publishMeta]);

  const tryAcquireStreamSlot = useCallback(
    (conversationId: string): boolean => {
      if (streamSlotOwnersRef.current.has(conversationId)) {
        return true;
      }
      if (activeStreamCountRef.current >= sseMaxNumRef.current) {
        return false;
      }
      streamSlotOwnersRef.current.add(conversationId);
      activeStreamCountRef.current += 1;
      syncQueueMeta();
      return true;
    },
    [syncQueueMeta],
  );

  const releaseStreamSlotFor = useCallback(
    (conversationId: string) => {
      if (!streamSlotOwnersRef.current.delete(conversationId)) {
        return false;
      }
      activeStreamCountRef.current = Math.max(
        0,
        activeStreamCountRef.current - 1,
      );
      syncQueueMeta();
      return true;
    },
    [syncQueueMeta],
  );

  const patchConversation = useCallback(
    (
      id: string,
      patch:
        | Partial<ConversationState>
        | ((prev: ConversationState) => ConversationState),
    ) => {
      setById((prev) => {
        if (
          !prev[id] &&
          (closingTabsRef.current.has(id) || isSessionDismissed(id))
        ) {
          return prev;
        }
        const merged = { ...prev, ...byIdRef.current };
        const cur = merged[id] ?? createEmptyConversationState(id);
        const nextState =
          typeof patch === "function"
            ? patch(cur)
            : { ...cur, ...patch, id };
        const next = { ...merged, [id]: nextState };
        byIdRef.current = next;
        if (
          nextState.hydrated &&
          nextState.status === "idle" &&
          !closingTabsRef.current.has(id)
        ) {
          scheduleConversationPersist(id, nextState);
        }
        // 须在 ref 写入后同步通知：异步 SSE onEvent 中若先 notify 再落盘，useSyncExternalStore 会读到旧快照
        notifyConversation(id);
        return next;
      });
    },
    [],
  );

  const drainStreamQueue = useCallback(() => {
    while (
      queueRef.current.length > 0 &&
      activeStreamCountRef.current < sseMaxNumRef.current
    ) {
      const nextId = queueRef.current.shift()!;
      if (!tryAcquireStreamSlot(nextId)) {
        queueRef.current.unshift(nextId);
        break;
      }
      patchConversation(nextId, (s) => ({
        ...s,
        streaming: true,
        queued: false,
        streamError: null,
      }));
      void runStreamRef.current(nextId);
    }
  }, [patchConversation, tryAcquireStreamSlot]);

  const runStream = useCallback(
    async (conversationId: string) => {
      const state = byIdRef.current[conversationId];
      if (!state) {
        releaseStreamSlotFor(conversationId);
        pendingSendRef.current.delete(conversationId);
        return;
      }
      if (abortControllersRef.current.has(conversationId)) {
        pendingSendRef.current.delete(conversationId);
        return;
      }
      if (!streamSlotOwnersRef.current.has(conversationId)) {
        if (!tryAcquireStreamSlot(conversationId)) {
          pendingSendRef.current.delete(conversationId);
          if (!queueRef.current.includes(conversationId)) {
            queueRef.current.push(conversationId);
          }
          patchConversation(conversationId, (s) => ({
            ...s,
            streaming: false,
            queued: true,
            streamError: null,
          }));
          return;
        }
      }

      const ac = new AbortController();
      abortControllersRef.current.set(conversationId, ac);

      patchConversation(conversationId, (s) => ({
        ...s,
        streaming: true,
        queued: false,
        streamError: null,
      }));
      pendingSendRef.current.delete(conversationId);

      const acc = { assistantText: "", reasoningText: "" };
      let streamReactHitStepLimit = false;

      try {
        const st = byIdRef.current[conversationId]!;
        const taskInput =
          st.taskInputText?.trim() ?
            { text: st.taskInputText.trim() }
          : undefined;
        const skillForApi =
          st.skillId ?? (st.labMode ? "lint_zh" : undefined);
        await streamChat({
          messages: messagesForApi(st.messages),
          operatingMode: st.operatingMode,
          presentation: st.presentation,
          skillId: skillForApi,
          taskInput,
          paradigmOverride: st.paradigmOverride,
          signal: ac.signal,
          onEvent: (ev) => {
            if (ev.kind === "citations") {
              patchConversation(conversationId, (s) => ({
                ...s,
                ...applyCitationToTurn(s, ev.items),
              }));
              return;
            }
            if (ev.kind === "tool_trace_summary") {
              const line = `[${ev.status}] ${ev.tool}: ${ev.detail}`;
              patchConversation(conversationId, (s) => ({
                ...s,
                ...appendToolTraceToTurn(s, line),
              }));
              return;
            }
            if (ev.kind === "tool_trace_full") {
              const block = JSON.stringify(
                {
                  tool: ev.tool,
                  arguments: ev.arguments,
                  result: ev.result,
                  error: ev.error,
                },
                null,
                2,
              );
              patchConversation(conversationId, (s) => ({
                ...s,
                ...appendToolTraceToTurn(s, block),
              }));
              return;
            }
            if (ev.kind === "error") {
              patchConversation(conversationId, (s) => ({
                ...s,
                streamError: `${ev.code}: ${ev.message}`,
              }));
              return;
            }
            if (ev.kind === "pipeline_step") {
              patchConversation(conversationId, (s) => {
                const rest = s.pipelineSteps.filter(
                  (x) => x.stepId !== ev.stepId,
                );
                return {
                  ...s,
                  pipelineSteps: [
                    ...rest,
                    {
                      stepId: ev.stepId,
                      status: ev.status,
                      summary: ev.summary,
                    },
                  ],
                };
              });
              return;
            }
            if (ev.kind === "pipeline_warning") {
              patchConversation(conversationId, (s) => ({
                ...s,
                pipelineWarnings: ev.warnings,
              }));
              return;
            }
            if (ev.kind === "done") {
              const raw = ev.payload.written_paths;
              const written =
                Array.isArray(raw) ? raw.map((p) => String(p)) : [];
              streamReactHitStepLimit =
                ev.payload.react_hit_step_limit === true;
              patchConversation(conversationId, (s) => ({
                ...s,
                ...(written.length > 0 ? { pipelineWrittenPaths: written } : {}),
                ...applyReactStepLimitToTurn(s, streamReactHitStepLimit),
                ...finalizeTurnTrace(s),
              }));
              return;
            }
            if (
              ev.kind === "delta" ||
              ev.kind === "reasoning_summary" ||
              ev.kind === "reasoning_full"
            ) {
              patchConversation(conversationId, (s) => {
                const messages = applyStreamEventToMessages(
                  s.messages,
                  ev,
                  acc,
                );
                const isBackground =
                  activeIdRef.current !== conversationId;
                return {
                  ...s,
                  messages,
                  title: deriveConversationTitle(messages),
                  unread: isBackground ? true : s.unread,
                };
              });
            }
          },
        });
      } catch (err) {
        if (!ac.signal.aborted) {
          patchConversation(conversationId, (s) => ({
            ...s,
            streamError:
              err instanceof Error ? err.message : String(err),
          }));
        } else {
          patchConversation(conversationId, (s) => ({
            ...s,
            streamError: "已中断",
          }));
        }
      } finally {
        abortControllersRef.current.delete(conversationId);
        releaseStreamSlotFor(conversationId);
        const teardown = (s: ConversationState): ConversationState => {
          const messages = finalizeStreamAssistantMessage(s.messages, acc, {
            stripSuffix: streamReactHitStepLimit,
          });
          const stepLimitPatch =
            streamReactHitStepLimit ?
              applyReactStepLimitToTurn(s, true)
            : {};
          const next: ConversationState = normalizeInterruptedConversationState(
            {
              ...s,
              ...stepLimitPatch,
              messages,
              ...finalizeTurnTrace(s),
            },
          );
          return next;
        };
        if (byIdRef.current[conversationId]) {
          commitConversationState(conversationId, teardown);
        }
        syncQueueMeta();
        drainStreamQueue();
      }
    },
    [
      commitConversationState,
      drainStreamQueue,
      patchConversation,
      releaseStreamSlotFor,
      tryAcquireStreamSlot,
      syncQueueMeta,
    ],
  );

  useEffect(() => {
    runStreamRef.current = runStream;
  }, [runStream]);

  const enqueueOrRunStream = useCallback(
    (conversationId: string) => {
      if (tryAcquireStreamSlot(conversationId)) {
        patchConversation(conversationId, (s) => ({
          ...s,
          streaming: true,
          queued: false,
          streamError: null,
        }));
        void runStream(conversationId);
        return;
      }
      if (!queueRef.current.includes(conversationId)) {
        queueRef.current.push(conversationId);
      }
      patchConversation(conversationId, (s) => ({
        ...s,
        streaming: false,
        queued: true,
        streamError: null,
      }));
      syncQueueMeta();
    },
    [patchConversation, runStream, syncQueueMeta, tryAcquireStreamSlot],
  );

  const startTaskRun = useCallback(
    (
      conversationId: string,
      text: string,
      mode: "first" | "follow-up",
    ) => {
      const trimmed = text.trim();
      if (!trimmed) {
        return;
      }
      const cur = byIdRef.current[conversationId];
      if (!cur?.skillId) {
        return;
      }
      if (cur.streaming || cur.queued) {
        return;
      }
      pendingSendRef.current.add(conversationId);
      const userMsg: ChatMessage = { role: "user", content: trimmed };
      const continuous = skillSupportsContinuousQa(cur.skillId);

      patchConversation(conversationId, (s) => {
        const turnReset =
          continuous ? beginNewQaTurn(s) : { citations: [], toolTraceLog: [] };
        const assistantPlaceholder: ChatMessage = {
          role: "assistant",
          content: "",
          reasoning: "",
        };
        const nextMessages: ChatMessage[] =
          continuous && mode === "follow-up" ?
            [...s.messages, userMsg, assistantPlaceholder]
          : [userMsg, assistantPlaceholder];
        return {
          ...s,
          ...turnReset,
          taskPhase: "running",
          taskInputText: trimmed,
          streamError: null,
          streaming: false,
          queued: false,
          reactHitStepLimit: false,
          messages: nextMessages,
          pipelineSteps: [],
          pipelineWarnings: [],
          pipelineWrittenPaths: [],
          promoteMessage: null,
          promoteBusy: false,
          title: deriveConversationTitle(
            continuous && mode === "follow-up" ? nextMessages : [userMsg],
          ),
        };
      });
      enqueueOrRunStream(conversationId);
    },
    [enqueueOrRunStream, patchConversation],
  );

  const submitTaskRun = useCallback(
    (conversationId: string, text: string) => {
      startTaskRun(conversationId, text, "first");
    },
    [startTaskRun],
  );

  const sendMessage = useCallback(
    (conversationId: string, text: string) => {
      const trimmed = text.trim();
      if (!trimmed) {
        return;
      }
      if (
        pendingSendRef.current.has(conversationId) ||
        abortControllersRef.current.has(conversationId)
      ) {
        return;
      }
      const cur = byIdRef.current[conversationId];
      if (cur?.streaming || cur?.queued) {
        return;
      }

      pendingSendRef.current.add(conversationId);

      const userMsg: ChatMessage = { role: "user", content: trimmed };
      patchConversation(conversationId, (s) => {
        if (
          s.streaming ||
          s.queued ||
          abortControllersRef.current.has(conversationId)
        ) {
          return s;
        }
        const nextMessages = [...s.messages, userMsg];
        return {
          ...s,
          streaming: false,
          queued: false,
          messages: [
            ...nextMessages,
            { role: "assistant", content: "", reasoning: "" },
          ],
          citations: [],
          toolTraceLog: [],
          streamError: null,
          title: deriveConversationTitle(nextMessages),
        };
      });

      enqueueOrRunStream(conversationId);
    },
    [enqueueOrRunStream, patchConversation],
  );

  const stopStream = useCallback(
    (conversationId: string) => {
      const hadActiveStream = abortControllersRef.current.has(conversationId);
      const ac = abortControllersRef.current.get(conversationId);
      ac?.abort();
      abortControllersRef.current.delete(conversationId);
      queueRef.current = queueRef.current.filter((id) => id !== conversationId);
      if (!hadActiveStream) {
        releaseStreamSlotFor(conversationId);
      }
      patchConversation(conversationId, (s) =>
        normalizeInterruptedConversationState(s),
      );
      syncQueueMeta();
      if (!hadActiveStream) {
        drainStreamQueue();
      }
    },
    [drainStreamQueue, patchConversation, releaseStreamSlotFor, syncQueueMeta],
  );

  const resetTaskToInput = useCallback(
    (conversationId: string) => {
      stopStream(conversationId);
      patchConversation(conversationId, (s) =>
        s.skillId ?
          {
            ...s,
            taskPhase: "input",
            taskInputText: undefined,
            messages: [],
            citations: [],
            toolTraceLog: [],
            citationTurns: [],
            toolTraceTurns: [],
            pipelineSteps: [],
            pipelineWarnings: [],
            pipelineWrittenPaths: [],
            promoteMessage: null,
            promoteBusy: false,
            streamError: null,
            streaming: false,
            queued: false,
          }
        : s,
      );
    },
    [patchConversation, stopStream],
  );

  const createReviewSession = useCallback(
    (scope?: string) => {
      const id = generateConversationId();
      const params = scope ? `?scope=${encodeURIComponent(scope)}` : "";
      const state = createEmptyReviewState(id, scope);
      setById((prev) => {
        const next = { ...prev, [id]: state };
        byIdRef.current = next;
        return next;
      });
      notifyConversation(id);
      setOpenTabIds((prev) => (prev.includes(id) ? prev : [...prev, id]));
      navigate(`/review/${id}${params}`);
    },
    [navigate],
  );

  const promotePipelineDrafts = useCallback(
    async (conversationId: string) => {
      const cur = byIdRef.current[conversationId];
      if (!cur?.skillId || cur.promoteBusy) {
        return;
      }
      const rels = cur.pipelineWrittenPaths
        .map((p) => p.replace(/^setting_entry\//, ""))
        .filter((p) => p.length > 0);
      patchConversation(conversationId, (s) => ({
        ...s,
        promoteBusy: true,
        promoteMessage: null,
      }));
      try {
        const report = await promoteSettingEntry(
          rels.length > 0 ? { draftRelpaths: rels } : undefined,
        );
        const msg =
          report.ok
            ? report.applied.length > 0
              ? `已晋升 ${report.applied.length} 个文件至 KSFS：${report.applied.join("、")}`
              : report.notes || "无文件被晋升"
            : `晋升失败：${report.notes}`;
        patchConversation(conversationId, (s) => ({
          ...s,
          promoteBusy: false,
          promoteMessage: msg,
        }));
      } catch (err) {
        patchConversation(conversationId, (s) => ({
          ...s,
          promoteBusy: false,
          promoteMessage:
            err instanceof Error ? err.message : String(err),
        }));
      }
    },
    [patchConversation],
  );

  const archiveTab = useCallback(
    (conversationId: string) => {
      closingTabsRef.current.add(conversationId);
      stopStream(conversationId);
      pendingSendRef.current.delete(conversationId);
      queueRef.current = queueRef.current.filter((id) => id !== conversationId);
      cancelConversationPersist(conversationId);
      syncQueueMeta();

      markSessionDismissed(conversationId);

      const stateRaw =
        byIdRef.current[conversationId] ??
        createEmptyConversationState(conversationId);
      const state = normalizeInterruptedConversationState({
        ...stateRaw,
        ...finalizeTurnTrace(stateRaw),
      });
      const record = buildConversationRecord({
        id: state.id,
        messages: state.messages,
        citationTurns: state.citationTurns,
        toolTraceTurns: state.toolTraceTurns,
        reactStepLimitTurns: state.reactStepLimitTurns,
        operatingMode: state.operatingMode,
        presentation: state.presentation,
        status: "archived",
        title: state.title,
        skillId: state.skillId,
        taskPhase: state.taskPhase,
        taskInputText: state.taskInputText,
      });

      const path = currentAppPath();
      const onArchivedRoute = isConversationRoute(path, conversationId);

      void (async () => {
        if (isConversationIpcAvailable()) {
          await writeConversationIpc(conversationId, record);
          notifyConversationsStorageChanged();
        }

        setOpenTabIds((prev) => {
          const next = prev.filter((x) => x !== conversationId);
          openTabIdsRef.current = next;
          if (onArchivedRoute) {
            if (next.length === 0) {
              navigate("/", { replace: true });
            } else {
              const nextState = byIdRef.current[next[0]];
              navigate(
                nextState
                  ? conversationNavPath(nextState)
                  : `/chat/${next[0]}`,
                { replace: true },
              );
            }
          }
          return next;
        });

        setById((prev) => {
          if (openTabIdsRef.current.includes(conversationId)) {
            closingTabsRef.current.delete(conversationId);
            return prev;
          }
          const next = { ...prev };
          delete next[conversationId];
          byIdRef.current = next;
          return next;
        });
        notifyConversation(conversationId);
        closingTabsRef.current.delete(conversationId);
      })();
    },
    [navigate, stopStream, syncQueueMeta],
  );

  const restoreArchivedConversation = useCallback(
    async (conversationId: string): Promise<boolean> => {
      if (!isConversationIpcAvailable()) {
        return false;
      }
      closingTabsRef.current.delete(conversationId);
      pendingSendRef.current.delete(conversationId);
      const staleAc = abortControllersRef.current.get(conversationId);
      staleAc?.abort();
      abortControllersRef.current.delete(conversationId);
      queueRef.current = queueRef.current.filter((id) => id !== conversationId);

      const read = await readConversationIpc(conversationId);
      if (!read.ok) {
        return false;
      }
      const state = normalizeInterruptedConversationState(
        conversationStateFromRecord({
          ...read.record,
          status: "idle",
        }),
      );
      const record = buildConversationRecord({
        id: state.id,
        messages: state.messages,
        citationTurns: state.citationTurns,
        toolTraceTurns: state.toolTraceTurns,
        reactStepLimitTurns: state.reactStepLimitTurns,
        operatingMode: state.operatingMode,
        presentation: state.presentation,
        status: "idle",
        title: state.title,
        skillId: state.skillId,
        taskPhase: state.taskPhase,
        taskInputText: state.taskInputText,
      });
      record.updated_at = new Date().toISOString();
      const written = await writeConversationIpc(conversationId, record);
      if (!written.ok) {
        return false;
      }
      notifyConversationsStorageChanged();
      clearSessionDismissed(conversationId);
      setById((prev) => {
        const next = { ...prev, [conversationId]: state };
        byIdRef.current = next;
        return next;
      });
      notifyConversation(conversationId);
      setOpenTabIds((prev) => {
        const next =
          prev.includes(conversationId) ? prev : [...prev, conversationId];
        openTabIdsRef.current = next;
        return next;
      });
      syncQueueMeta();
      navigate(conversationNavPath(state));
      return true;
    },
    [navigate, syncQueueMeta],
  );

  const createTab = useCallback(() => {
    const id = generateConversationId();
    setById((prev) => {
      const next = { ...prev, [id]: createEmptyConversationState(id) };
      byIdRef.current = next;
      return next;
    });
    notifyConversation(id);
    setOpenTabIds((prev) => [...prev, id]);
    navigate(`/chat/${id}`);
    return id;
  }, [navigate]);

  const createLabTab = useCallback(() => {
    const id = generateConversationId();
    const base = createEmptyConversationState(id, "范式试验");
    const state = {
      ...base,
      labMode: true as const,
      skillId: "lint_zh",
    };
    setById((prev) => {
      const next = { ...prev, [id]: state };
      byIdRef.current = next;
      return next;
    });
    notifyConversation(id);
    setOpenTabIds((prev) => (prev.includes(id) ? prev : [...prev, id]));
    navigate(`/lab/${id}`);
    return id;
  }, [navigate]);

  const openConversationTab = useCallback(
    (
      id: string,
      state: ConversationState,
      path: string,
    ) => {
      setById((prev) => {
        const next = { ...prev, [id]: state };
        byIdRef.current = next;
        return next;
      });
      notifyConversation(id);
      flushConversationPersist(id, state);
      setOpenTabIds((prev) =>
        prev.includes(id) ? prev : [...prev, id],
      );
      navigate(path);
      return id;
    },
    [navigate],
  );

  const createTask = useCallback(
    (skillId: string) => {
      const card = getSkillMeta(skillId);
      const title = card?.display_name ?? skillId;
      const id = generateConversationId();
      const state = createEmptyConversationState(
        id,
        title,
        skillId,
        "input",
      );
      return openConversationTab(id, state, `/task/${id}`);
    },
    [openConversationTab],
  );

  const createNewTopicTask = useCallback(
    (skillId: string) => createTask(skillId),
    [createTask],
  );

  const submitTaskSend = useCallback(
    (conversationId: string, text: string) => {
      const trimmed = text.trim();
      if (!trimmed) {
        return;
      }
      const cur = byIdRef.current[conversationId];
      if (!cur?.skillId || cur.streaming || cur.queued) {
        return;
      }
      if (lastQaTurnHitStepLimit(cur.reactStepLimitTurns)) {
        const newId = createTask(cur.skillId);
        startTaskRun(newId, trimmed, "first");
        return;
      }
      const continuous = skillSupportsContinuousQa(cur.skillId);
      const hasPriorUser = cur.messages.some((m) => m.role === "user");
      if (continuous && hasPriorUser) {
        startTaskRun(conversationId, trimmed, "follow-up");
      } else {
        startTaskRun(conversationId, trimmed, "first");
      }
    },
    [createTask, startTaskRun],
  );

  const createInspireChat = useCallback(
    (skillId: string) => {
      const card = getSkillMeta(skillId);
      const title = card?.display_name ?? skillId;
      const id = generateConversationId();
      const state = createEmptyConversationState(id, title, skillId);
      return openConversationTab(id, state, `/chat/${id}`);
    },
    [openConversationTab],
  );

  const ensureOpenTab = useCallback(
    (conversationId: string) => {
      if (closingTabsRef.current.has(conversationId)) {
        return;
      }
      const cur = byIdRef.current[conversationId];
      if (cur) {
        if (cur.status === "archived") {
          return;
        }
        setOpenTabIds((prev) =>
          prev.includes(conversationId) ? prev : [...prev, conversationId],
        );
        return;
      }
      void (async () => {
        if (closingTabsRef.current.has(conversationId)) {
          return;
        }
        if (!isConversationIpcAvailable()) {
          return;
        }
        const result = await readConversationIpc(conversationId);
        if (closingTabsRef.current.has(conversationId)) {
          return;
        }
        if (!result.ok || result.record.status === "archived") {
          if (isConversationRoute(currentAppPath(), conversationId)) {
            navigate("/", { replace: true });
          }
          return;
        }
        patchConversation(
          conversationId,
          conversationStateFromRecord(result.record),
        );
        setOpenTabIds((prev) =>
          prev.includes(conversationId) ? prev : [...prev, conversationId],
        );
      })();
    },
    [navigate, patchConversation],
  );

  const clearUnread = useCallback(
    (conversationId: string) => {
      patchConversation(conversationId, (s) =>
        s.unread ? { ...s, unread: false } : s,
      );
    },
    [patchConversation],
  );

  useEffect(() => {
    publishMeta();
  }, [publishMeta]);

  useEffect(() => {
    bindConversationPersistSource((id) => byIdRef.current[id]);
    bindConversationPersistGuard(
      (id, state) =>
        !closingTabsRef.current.has(id) &&
        state.status !== "archived" &&
        !isSessionDismissed(id),
    );
  }, []);

  useEffect(() => {
    void (async () => {
      const b = await fetchBootstrap();
      const fromApi = panelSkillsFromBootstrap(b?.skills);
      hydrateSkillRegistry(
        fromApi.length > 0 ? fromApi : [...FALLBACK_PANEL_SKILLS],
      );
      const ui = resolveBootstrapUi(b?.ui);
      setSseMaxNum(ui.SSE_maxNum);
      sseMaxNumRef.current = ui.SSE_maxNum;

      let tabIds: string[] = [];
      const loaded: Record<string, ConversationState> = {};

      if (isConversationIpcAvailable()) {
        const metas = await listConversationsIpc();
        const idleCandidates = metas.filter((m) => m.status === "idle");
        for (const { id } of idleCandidates) {
          if (isSessionDismissed(id)) {
            const r = await readConversationIpc(id);
            if (r.ok && r.record.status === "archived") {
              clearSessionDismissed(id);
            } else if (r.ok && r.record.status === "idle") {
              await writeConversationIpc(id, {
                ...r.record,
                status: "archived",
                updated_at: new Date().toISOString(),
              });
            }
            continue;
          }
          const r = await readConversationIpc(id);
          if (!r.ok || r.record.status !== "idle") {
            continue;
          }
          loaded[id] = conversationStateFromRecord(r.record);
          tabIds.push(id);
        }
      } else {
        tabIds = [];
      }

      setById(loaded);
      byIdRef.current = loaded;
      setOpenTabIds(tabIds);
      setReady(true);
    })();
  }, []);

  const actions = useMemo(
    (): ConversationActions => ({
      ensureOpenTab,
      createTab,
      createLabTab,
      createTask,
      createInspireChat,
      archiveTab,
      restoreArchivedConversation,
      clearUnread,
      patchConversation,
      resetTaskToInput,
      promotePipelineDrafts,
      createReviewSession,
      sendMessage,
      submitTaskRun,
      submitTaskSend,
      createNewTopicTask,
      stopStream,
    }),
    [
      archiveTab,
      restoreArchivedConversation,
      clearUnread,
      createTab,
      createLabTab,
      createTask,
      createNewTopicTask,
      createInspireChat,
      ensureOpenTab,
      patchConversation,
      promotePipelineDrafts,
      createReviewSession,
      resetTaskToInput,
      sendMessage,
      submitTaskRun,
      submitTaskSend,
      stopStream,
    ],
  );

  const runtime = useMemo(
    (): StoreRuntime => ({
      getState: (id) => byIdRef.current[id],
      getMeta: () => metaSnapshotRef.current,
      subscribe: subscribeConversation,
      subscribeMeta: subscribeAllConversations,
    }),
    [],
  );

  return (
    <ConversationActionsContext.Provider value={actions}>
      <ConversationRuntimeContext.Provider value={runtime}>
        {children}
      </ConversationRuntimeContext.Provider>
    </ConversationActionsContext.Provider>
  );
}

export function useConversationActions(): ConversationActions {
  const ctx = useContext(ConversationActionsContext);
  if (!ctx) {
    throw new Error("useConversationActions 须在 ConversationProvider 内使用");
  }
  return ctx;
}

function useConversationRuntime(): StoreRuntime {
  const ctx = useContext(ConversationRuntimeContext);
  if (!ctx) {
    throw new Error("useConversationRuntime 须在 ConversationProvider 内使用");
  }
  return ctx;
}

export function useConversationState(
  id: string,
): ConversationState | undefined {
  const rt = useConversationRuntime();
  return useSyncExternalStore(
    (onStoreChange) => rt.subscribe(id, onStoreChange),
    () => rt.getState(id),
    () => rt.getState(id),
  );
}

export function useConversationMeta(): ConversationMeta {
  const rt = useConversationRuntime();
  return useSyncExternalStore(
    (onStoreChange) => rt.subscribeMeta(onStoreChange),
    () => rt.getMeta(),
    () => rt.getMeta(),
  );
}

/** @deprecated 请用 useConversationActions + useConversationState */
export function useConversationStore(): ConversationActions & ConversationMeta {
  const actions = useConversationActions();
  const meta = useConversationMeta();
  return { ...actions, ...meta };
}

export function useConversation(conversationId: string) {
  const actions = useConversationActions();
  const conv = useConversationState(conversationId);
  const meta = useConversationMeta();

  useEffect(() => {
    actions.ensureOpenTab(conversationId);
    actions.clearUnread(conversationId);
  }, [actions, conversationId]);

  return { actions, conv, meta };
}
