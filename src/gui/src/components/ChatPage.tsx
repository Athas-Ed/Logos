import { useCallback, useEffect, useRef, useState } from "react";
import { fetchBootstrap } from "../api/bootstrap";
import {
  fetchDeveloperUi,
  putPromptEcho,
} from "../api/developer";
import { fetchHealth } from "../api/health";
import { streamChat } from "../api/sseChat";
import {
  OPERATING_MODES,
  type ChatMessage,
  type CitationItem,
  type LogProfile,
  type OperatingMode,
  type PresentationMode,
  PRESENTATION_STORAGE_KEY,
} from "../types/chat";
import styles from "./ChatPage.module.css";

const MODE_LABELS: Record<OperatingMode, string> = {
  author: "作者（author）",
  screenwriter: "编剧（screenwriter）",
};

const PRESENTATION_LABELS: Record<PresentationMode, string> = {
  work: "工作展示（摘要）",
  developer: "开发者展示（全文）",
};

function readStoredPresentation(): PresentationMode | null {
  try {
    const raw = sessionStorage.getItem(PRESENTATION_STORAGE_KEY);
    if (raw === "work" || raw === "developer") return raw;
  } catch {
    /* sessionStorage 不可用 */
  }
  return null;
}

function persistPresentation(mode: PresentationMode) {
  try {
    sessionStorage.setItem(PRESENTATION_STORAGE_KEY, mode);
  } catch {
    /* ignore */
  }
}

function normalizeOperatingFromServer(raw: string): OperatingMode {
  return raw.trim().toLowerCase() === "screenwriter"
    ? "screenwriter"
    : "author";
}

function normalizeLogProfile(raw: string): LogProfile | null {
  const s = raw.trim().toLowerCase();
  if (
    s === "minimal" ||
    s === "standard" ||
    s === "verbose" ||
    s === "audit"
  ) {
    return s;
  }
  return null;
}

export function ChatPage() {
  const [shellBackendHint, setShellBackendHint] = useState<string | null>(null);
  const [shellBackendTone, setShellBackendTone] = useState<"warn" | "err">(
    "warn",
  );
  const [healthOk, setHealthOk] = useState<boolean | null>(null);
  const [operatingMode, setOperatingMode] =
    useState<OperatingMode>("author");
  const [presentation, setPresentation] =
    useState<PresentationMode>("work");
  const [logProfile, setLogProfile] = useState<LogProfile | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [citations, setCitations] = useState<CitationItem[]>([]);
  const [toolTraceLog, setToolTraceLog] = useState<string[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [devUi, setDevUi] = useState<{
    show: boolean;
    promptEcho: boolean;
  } | null>(null);
  const [devToggleBusy, setDevToggleBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const listEndRef = useRef<HTMLDivElement | null>(null);

  const refreshHealth = useCallback(async () => {
    setHealthOk(await fetchHealth());
  }, []);

  useEffect(() => {
    const bridge = window.logosElectron?.onBackendStatus;
    if (!bridge) {
      return;
    }
    return bridge((s) => {
      if (s.state === "ready") {
        setShellBackendHint(null);
        void refreshHealth();
        void (async () => {
          const b = await fetchBootstrap();
          if (b) {
            const lp = normalizeLogProfile(b.log_profile);
            if (lp) setLogProfile(lp);
            setOperatingMode(normalizeOperatingFromServer(b.operating_mode));
          }
        })();
        return;
      }
      setShellBackendTone(s.state === "failed" ? "err" : "warn");
      setShellBackendHint(s.message ?? (s.state === "failed" ? "后端不可用" : "后端恢复中"));
    });
  }, [refreshHealth]);

  useEffect(() => {
    void refreshHealth();
    const id = window.setInterval(() => void refreshHealth(), 60000);
    return () => window.clearInterval(id);
  }, [refreshHealth]);

  useEffect(() => {
    void (async () => {
      const stored = readStoredPresentation();
      const b = await fetchBootstrap();
      if (b) {
        const lp = normalizeLogProfile(b.log_profile);
        if (lp) setLogProfile(lp);
        setOperatingMode(normalizeOperatingFromServer(b.operating_mode));
        setPresentation(stored ?? b.default_presentation);
      } else if (stored) {
        setPresentation(stored);
      }
    })();
  }, []);

  useEffect(() => {
    void (async () => {
      const s = await fetchDeveloperUi();
      if (!s?.show_dev_tools_ui) {
        setDevUi(null);
        return;
      }
      setDevUi({ show: true, promptEcho: s.prompt_echo });
    })();
  }, []);

  useEffect(() => {
    listEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streaming, toolTraceLog]);

  const stopStream = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setStreaming(false);
  }, []);

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || streaming) return;

    setStreamError(null);
    setInput("");

    const userMsg: ChatMessage = { role: "user", content: text };
    const nextMessages = [...messages, userMsg];
    setMessages([
      ...nextMessages,
      { role: "assistant", content: "", reasoning: "" },
    ]);
    setCitations([]);
    setToolTraceLog([]);

    setStreaming(true);
    const ac = new AbortController();
    abortRef.current = ac;

    let assistantText = "";
    let reasoningText = "";

    try {
      await streamChat({
        messages: [...nextMessages],
        operatingMode,
        presentation,
        signal: ac.signal,
        onEvent: (ev) => {
          if (ev.kind === "reasoning_summary") {
            reasoningText = ev.text;
            setMessages((prev) => {
              const copy = [...prev];
              const last = copy.length - 1;
              if (last >= 0 && copy[last].role === "assistant") {
                copy[last] = {
                  ...copy[last],
                  reasoning: reasoningText,
                };
              }
              return copy;
            });
          } else if (ev.kind === "reasoning_full") {
            reasoningText += ev.text;
            setMessages((prev) => {
              const copy = [...prev];
              const last = copy.length - 1;
              if (last >= 0 && copy[last].role === "assistant") {
                copy[last] = {
                  ...copy[last],
                  reasoning: reasoningText,
                };
              }
              return copy;
            });
          } else if (ev.kind === "delta") {
            assistantText += ev.text;
            setMessages((prev) => {
              const copy = [...prev];
              const last = copy.length - 1;
              if (last >= 0 && copy[last].role === "assistant") {
                copy[last] = {
                  ...copy[last],
                  content: assistantText,
                  reasoning: reasoningText || copy[last].reasoning,
                };
              }
              return copy;
            });
          } else if (ev.kind === "citations") {
            setCitations(ev.items);
          } else if (ev.kind === "tool_trace_summary") {
            const line = `[${ev.status}] ${ev.tool}: ${ev.detail}`;
            setToolTraceLog((prev) => [...prev, line]);
          } else if (ev.kind === "tool_trace_full") {
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
            setToolTraceLog((prev) => [...prev, block]);
          } else if (ev.kind === "error") {
            setStreamError(`${ev.code}: ${ev.message}`);
          } else if (ev.kind === "done") {
            /* no-op */
          }
        },
      });
    } catch (err) {
      if (ac.signal.aborted) {
        setStreamError("已中断");
      } else {
        setStreamError(
          err instanceof Error ? err.message : String(err),
        );
      }
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  }, [input, messages, operatingMode, presentation, streaming]);

  return (
    <div className={styles.layout}>
      {shellBackendHint ? (
        <div
          className={
            shellBackendTone === "err"
              ? styles.shellBannerErr
              : styles.shellBannerWarn
          }
          role="status"
        >
          {shellBackendHint}
        </div>
      ) : null}
      <header className={styles.header}>
        <div className={styles.titleBlock}>
          <h1 className={styles.title}>Logos 对话</h1>
          <p className={styles.subtitle}>
            V0.2 · POST /api/v1/chat（SSE）· operating_mode 随请求体；展示档位
            仅会话有效（见 SPEC-DISPLAY-AND-LOGGING）
            {logProfile ? ` · 日志档位（只读）: ${logProfile}` : null}
          </p>
        </div>
        <div className={styles.headerActions}>
          <label className={styles.modeLabel}>
            <span>运行模式</span>
            <select
              className={styles.select}
              value={operatingMode}
              disabled={streaming}
              onChange={(e) =>
                setOperatingMode(e.target.value as OperatingMode)
              }
            >
              {OPERATING_MODES.map((m) => (
                <option key={m} value={m}>
                  {MODE_LABELS[m]}
                </option>
              ))}
            </select>
          </label>
          <label className={styles.modeLabel}>
            <span>展示档位</span>
            <select
              className={styles.select}
              value={presentation}
              disabled={streaming}
              title="仅写入浏览器会话，不回写服务器配置"
              onChange={(e) => {
                const v = e.target.value as PresentationMode;
                setPresentation(v);
                persistPresentation(v);
              }}
            >
              {(Object.keys(PRESENTATION_LABELS) as PresentationMode[]).map(
                (m) => (
                  <option key={m} value={m}>
                    {PRESENTATION_LABELS[m]}
                  </option>
                ),
              )}
            </select>
          </label>
          {devUi?.show ? (
            <label
              className={styles.devToolToggle}
              title="不调用 LLM，将完整 Prompt 作为助手答复（检视 CB 拼装）"
            >
              <input
                type="checkbox"
                checked={devUi.promptEcho}
                disabled={devToggleBusy || streaming}
                onChange={(e) => {
                  const on = e.target.checked;
                  setDevToggleBusy(true);
                  void (async () => {
                    const ok = await putPromptEcho(on);
                    if (ok) {
                      setDevUi((prev) =>
                        prev ? { ...prev, promptEcho: on } : prev,
                      );
                    }
                    setDevToggleBusy(false);
                  })();
                }}
              />
              <span>Prompt 回显</span>
            </label>
          ) : null}
          <button
            type="button"
            className={styles.ghostBtn}
            onClick={() => void refreshHealth()}
          >
            检查健康
          </button>
          <div
            className={styles.health}
            data-testid="health-indicator"
            data-health={
              healthOk === null ? "unknown" : healthOk ? "ok" : "bad"
            }
            title={healthOk === null ? "未检测" : healthOk ? "后端正常" : "后端不可用"}
          >
            <span
              className={
                healthOk === null
                  ? styles.healthDotUnknown
                  : healthOk
                    ? styles.healthDotOk
                    : styles.healthDotBad
              }
            />
            <span className={styles.healthText}>
              GET /api/v1/health
            </span>
          </div>
        </div>
      </header>

      <div className={styles.main}>
        <section className={styles.chatPanel}>
          {streamError ? (
            <div className={styles.errorBanner} role="alert">
              {streamError}
            </div>
          ) : null}

          <div className={styles.messageList}>
            {messages.length === 0 ? (
              <p className={styles.emptyHint}>
                发送一条消息开始对话。SSE：work 档为{" "}
                <code className={styles.inlineCode}>reasoning_summary</code>{" "}
               （滚动摘要）、
                <code className={styles.inlineCode}>citations_partial</code>、
                <code className={styles.inlineCode}>tool_trace_summary</code>
                ；developer 档为{" "}
                <code className={styles.inlineCode}>reasoning_full</code>、
                <code className={styles.inlineCode}>citations_full</code>、
                <code className={styles.inlineCode}>tool_trace_full</code>
                ；正文均为 <code className={styles.inlineCode}>delta</code>
                。引用在右侧边栏。
              </p>
            ) : (
              messages.map((m, i) => (
                <article
                  key={`${i}-${m.role}`}
                  className={
                    m.role === "user" ? styles.bubbleUser : styles.bubbleAssistant
                  }
                >
                  <div className={styles.bubbleMeta}>
                    {m.role === "user" ? "你" : "助手"}
                  </div>
                  <div className={styles.bubbleContent}>
                    {m.role === "assistant" &&
                    (m.reasoning?.length ?? 0) > 0 ? (
                      <details className={styles.reasoningFold} open>
                        <summary className={styles.reasoningSummary}>
                          推理（{presentation === "work" ? "摘要" : "全文"}）
                        </summary>
                        <pre className={styles.reasoningPre}>{m.reasoning}</pre>
                      </details>
                    ) : null}
                    {m.role === "assistant" &&
                    presentation === "developer" &&
                    toolTraceLog.length > 0 &&
                    i === messages.length - 1 ? (
                      <details className={styles.toolTraceFold}>
                        <summary className={styles.reasoningSummary}>
                          工具轨迹（{toolTraceLog.length}）
                        </summary>
                        <pre className={styles.toolTracePre}>
                          {toolTraceLog.join("\n---\n")}
                        </pre>
                      </details>
                    ) : null}
                    {m.role === "assistant" &&
                    streaming &&
                    i === messages.length - 1 &&
                    !m.content &&
                    (m.reasoning?.length ?? 0) === 0
                      ? "…"
                      : m.content}
                  </div>
                </article>
              ))
            )}
            <div ref={listEndRef} />
          </div>

          <div className={styles.composer}>
            <textarea
              className={styles.textarea}
              rows={3}
              placeholder="输入消息…（Enter 发送，Shift+Enter 换行）"
              value={input}
              disabled={streaming}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void send();
                }
              }}
            />
            <div className={styles.composerRow}>
              {streaming ? (
                <button
                  type="button"
                  className={styles.secondaryBtn}
                  onClick={stopStream}
                >
                  中断
                </button>
              ) : (
                <span className={styles.muted}>仅 SSE，无同路径 JSON 降级</span>
              )}
              <button
                type="button"
                className={styles.primaryBtn}
                disabled={streaming || !input.trim()}
                onClick={() => void send()}
              >
                发送
              </button>
            </div>
          </div>
        </section>

        <aside className={styles.citePanel}>
          <h2 className={styles.citeTitle}>引用 citations</h2>
          {citations.length === 0 ? (
            <p className={styles.citeEmpty}>
              尚无引用事件；后端在 work 档发送{" "}
              <code className={styles.inlineCode}>citations_partial</code>
              ，developer 档发送{" "}
              <code className={styles.inlineCode}>citations_full</code>。
            </p>
          ) : (
            <ul className={styles.citeList}>
              {citations.map((c, idx) => (
                <li key={`${c.path}-${idx}`} className={styles.citeCard}>
                  <div className={styles.citePath}>{c.path}</div>
                  <div className={styles.citeScore}>
                    score: {Number.isFinite(c.score) ? c.score.toFixed(4) : c.score}
                  </div>
                  <pre className={styles.citeSnippet}>{c.snippet}</pre>
                </li>
              ))}
            </ul>
          )}
        </aside>
      </div>
    </div>
  );
}
