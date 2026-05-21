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
import { streamChat, type StreamChatEvent } from "../api/sseChat";
import type { ChatMessage } from "../types/chat";
import {
  panelSkillsFromBootstrap,
  resolveBootstrapUi,
} from "../types/bootstrap";
import { FALLBACK_PANEL_SKILLS } from "../skills/catalog";
import { getSkillMeta, hydrateSkillRegistry } from "../skills/registry";
import { conversationNavPath } from "../skills/routing";
import { DEFAULT_CONVERSATION_ID } from "./constants";
import {
  conversationStateFromRecord,
  createEmptyConversationState,
  messagesForApi,
} from "./createEmptyConversation";
import { generateConversationId } from "./generateId";
import {
  isConversationIpcAvailable,
  listConversationsIpc,
  readConversationIpc,
} from "./ipc";
import { deriveConversationTitle } from "./record";
import {
  flushConversationPersist,
  scheduleConversationPersist,
} from "./persistScheduler";
import type { ConversationState } from "./storeTypes";
import { buildConversationRecord } from "./record";
import { writeConversationIpc } from "./ipc";
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
  /** 完成后回到输入步（保留 skill，清空本轮消息） */
  resetTaskToInput: (id: string) => void;
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
    const prevContent = copy[last].content ?? "";
    const nextContent = prevContent + ev.text;
    acc.assistantText = nextContent;
    copy[last] = {
      ...copy[last],
      content: nextContent,
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
  const [sseMaxNum, setSseMaxNum] = useState(3);

  /** 须在 setById updater 内同步写入；勿在 render 中用 React state 覆盖（会冲掉未提交的 SSE patch）。 */
  const byIdRef = useRef<Record<string, ConversationState>>({});
  const sseMaxNumRef = useRef(sseMaxNum);
  sseMaxNumRef.current = sseMaxNum;
  const activeStreamCountRef = useRef(0);
  const queueRef = useRef<string[]>([]);
  const abortControllersRef = useRef<Map<string, AbortController>>(new Map());
  const pendingSendRef = useRef<Set<string>>(new Set());
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
    metaSnapshotRef.current = {
      ready,
      openTabIds,
      sseMaxNum,
      activeStreamCount: activeStreamCountRef.current,
      queueLength: queueRef.current.length,
    };
    notifyAllConversations();
  }, [ready, openTabIds, sseMaxNum]);

  const syncQueueMeta = useCallback(() => {
    publishMeta();
  }, [publishMeta]);

  const patchConversation = useCallback(
    (
      id: string,
      patch:
        | Partial<ConversationState>
        | ((prev: ConversationState) => ConversationState),
    ) => {
      setById((prev) => {
        const cur = prev[id] ?? createEmptyConversationState(id);
        const nextState =
          typeof patch === "function"
            ? patch(cur)
            : { ...cur, ...patch, id };
        const next = { ...prev, [id]: nextState };
        byIdRef.current = next;
        if (nextState.hydrated && nextState.status === "idle") {
          scheduleConversationPersist(id, nextState);
        }
        // 须在 ref 写入后同步通知：异步 SSE onEvent 中若先 notify 再落盘，useSyncExternalStore 会读到旧快照
        notifyConversation(id);
        return next;
      });
    },
    [],
  );

  const runStream = useCallback(
    async (conversationId: string) => {
      const state = byIdRef.current[conversationId];
      if (!state) {
        pendingSendRef.current.delete(conversationId);
        return;
      }
      if (abortControllersRef.current.has(conversationId)) {
        pendingSendRef.current.delete(conversationId);
        return;
      }

      activeStreamCountRef.current += 1;
      syncQueueMeta();

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

      try {
        const apiMessages = messagesForApi(
          byIdRef.current[conversationId]?.messages ?? [],
        );
        const st = byIdRef.current[conversationId]!;
        const taskInput =
          st.taskInputText?.trim() ?
            { text: st.taskInputText.trim() }
          : undefined;
        const skillForApi =
          st.skillId ?? (st.labMode ? "lint_zh" : undefined);
        await streamChat({
          messages: apiMessages,
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
                citations: ev.items,
              }));
              return;
            }
            if (ev.kind === "tool_trace_summary") {
              const line = `[${ev.status}] ${ev.tool}: ${ev.detail}`;
              patchConversation(conversationId, (s) => ({
                ...s,
                toolTraceLog: [...s.toolTraceLog, line],
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
                toolTraceLog: [...s.toolTraceLog, block],
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
        activeStreamCountRef.current = Math.max(
          0,
          activeStreamCountRef.current - 1,
        );
        patchConversation(conversationId, (s) => {
          const next: typeof s = {
            ...s,
            streaming: false,
            queued: false,
          };
          if (
            s.skillId &&
            s.taskPhase === "running" &&
            !s.streamError &&
            !ac.signal.aborted
          ) {
            next.taskPhase = "done";
          }
          return next;
        });
        syncQueueMeta();

        while (
          queueRef.current.length > 0 &&
          activeStreamCountRef.current < sseMaxNumRef.current
        ) {
          const nextId = queueRef.current.shift()!;
          syncQueueMeta();
          void runStreamRef.current(nextId);
        }
      }
    },
    [patchConversation, syncQueueMeta],
  );

  useEffect(() => {
    runStreamRef.current = runStream;
  }, [runStream]);

  const enqueueOrRunStream = useCallback(
    (conversationId: string) => {
      if (activeStreamCountRef.current < sseMaxNumRef.current) {
        void runStream(conversationId);
        return;
      }
      queueRef.current.push(conversationId);
      patchConversation(conversationId, (s) => ({ ...s, queued: true }));
      syncQueueMeta();
    },
    [patchConversation, runStream, syncQueueMeta],
  );

  const submitTaskRun = useCallback(
    (conversationId: string, text: string) => {
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
      patchConversation(conversationId, (s) => ({
        ...s,
        taskPhase: "running",
        taskInputText: trimmed,
        streamError: null,
        streaming: true,
        queued: false,
        messages: [userMsg, { role: "assistant", content: "", reasoning: "" }],
        citations: [],
        toolTraceLog: [],
        title: deriveConversationTitle([userMsg]),
      }));
      const after = byIdRef.current[conversationId];
      if (!after?.streaming) {
        pendingSendRef.current.delete(conversationId);
        return;
      }
      enqueueOrRunStream(conversationId);
    },
    [enqueueOrRunStream, patchConversation],
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
          streaming: true,
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

      const after = byIdRef.current[conversationId];
      if (!after?.streaming) {
        pendingSendRef.current.delete(conversationId);
        return;
      }

      enqueueOrRunStream(conversationId);
    },
    [enqueueOrRunStream, patchConversation],
  );

  const stopStream = useCallback(
    (conversationId: string) => {
      const ac = abortControllersRef.current.get(conversationId);
      ac?.abort();
      abortControllersRef.current.delete(conversationId);
      queueRef.current = queueRef.current.filter((id) => id !== conversationId);
      patchConversation(conversationId, (s) => ({
        ...s,
        streaming: false,
        queued: false,
      }));
      syncQueueMeta();
    },
    [patchConversation, syncQueueMeta],
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
            streamError: null,
            streaming: false,
            queued: false,
          }
        : s,
      );
    },
    [patchConversation, stopStream],
  );

  const archiveTab = useCallback(
    (conversationId: string) => {
      stopStream(conversationId);
      queueRef.current = queueRef.current.filter((id) => id !== conversationId);

      const state =
        byIdRef.current[conversationId] ??
        createEmptyConversationState(conversationId);
      const archived = { ...state, status: "archived" as const };
      if (isConversationIpcAvailable()) {
        const record = buildConversationRecord({
          id: archived.id,
          messages: archived.messages,
          citations: archived.citations,
          toolTraceLog: archived.toolTraceLog,
          operatingMode: archived.operatingMode,
          presentation: archived.presentation,
          status: "archived",
          title: archived.title,
          skillId: archived.skillId,
          taskPhase: archived.taskPhase,
          taskInputText: archived.taskInputText,
        });
        void writeConversationIpc(conversationId, record);
      }

      setById((prev) => {
        const next = { ...prev };
        delete next[conversationId];
        byIdRef.current = next;
        return next;
      });
      notifyConversation(conversationId);

      setOpenTabIds((prev) => {
        const next = prev.filter((x) => x !== conversationId);
        if (next.length === 0) {
          const path = window.location.hash.replace(/^#/, "");
          if (
            path.startsWith(`/chat/${conversationId}`) ||
            path.startsWith(`/task/${conversationId}`) ||
            path.startsWith(`/lab/${conversationId}`)
          ) {
            navigate("/", { replace: true });
          }
          return [];
        }
        const path = window.location.hash.replace(/^#/, "");
        const nextState = byIdRef.current[next[0]];
        const nextPath = nextState
          ? conversationNavPath(nextState)
          : `/chat/${next[0]}`;
        if (
          path.startsWith(`/chat/${conversationId}`) ||
          path.startsWith(`/task/${conversationId}`) ||
          path.startsWith(`/lab/${conversationId}`)
        ) {
          navigate(nextPath, { replace: true });
        }
        return next;
      });
    },
    [navigate, patchConversation, stopStream],
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
      setOpenTabIds((prev) => {
        if (prev.includes(conversationId)) {
          return prev;
        }
        return [...prev, conversationId];
      });
      if (byIdRef.current[conversationId]) {
        return;
      }
      void (async () => {
        const result = await readConversationIpc(conversationId);
        if (result.ok) {
          patchConversation(
            conversationId,
            conversationStateFromRecord(result.record),
          );
        } else {
          patchConversation(
            conversationId,
            createEmptyConversationState(conversationId),
          );
        }
      })();
    },
    [patchConversation],
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
        const idle = metas.filter((m) => m.status === "idle");
        tabIds = idle.length > 0 ? idle.map((m) => m.id) : [DEFAULT_CONVERSATION_ID];
        for (const id of tabIds) {
          const r = await readConversationIpc(id);
          if (r.ok) {
            loaded[id] = conversationStateFromRecord(r.record);
          } else {
            loaded[id] = createEmptyConversationState(id);
          }
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
      clearUnread,
      patchConversation,
      resetTaskToInput,
      sendMessage,
      submitTaskRun,
      stopStream,
    }),
    [
      archiveTab,
      clearUnread,
      createTab,
      createLabTab,
      createTask,
      createInspireChat,
      ensureOpenTab,
      patchConversation,
      resetTaskToInput,
      sendMessage,
      submitTaskRun,
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
