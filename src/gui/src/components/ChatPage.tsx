import { useCallback, useEffect, useRef, useState } from "react";
import { fetchHealth } from "../api/health";
import { streamChat } from "../api/sseChat";
import {
  OPERATING_MODES,
  type ChatMessage,
  type CitationItem,
  type OperatingMode,
} from "../types/chat";
import styles from "./ChatPage.module.css";

const MODE_LABELS: Record<OperatingMode, string> = {
  author: "作者（author）",
  screenwriter: "编剧（screenwriter）",
};

export function ChatPage() {
  const [healthOk, setHealthOk] = useState<boolean | null>(null);
  const [operatingMode, setOperatingMode] =
    useState<OperatingMode>("author");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [citations, setCitations] = useState<CitationItem[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const listEndRef = useRef<HTMLDivElement | null>(null);

  const refreshHealth = useCallback(async () => {
    setHealthOk(await fetchHealth());
  }, []);

  // 与「发消息」无关：仅轮询 /api/v1/health 更新右上角圆点。开发模式下 React StrictMode 可能让本 effect 多跑一次。
  useEffect(() => {
    void refreshHealth();
    const id = window.setInterval(() => void refreshHealth(), 60000);
    return () => window.clearInterval(id);
  }, [refreshHealth]);

  useEffect(() => {
    listEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streaming]);

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

    setStreaming(true);
    const ac = new AbortController();
    abortRef.current = ac;

    let assistantText = "";
    let reasoningText = "";

    try {
      await streamChat({
        messages: [...nextMessages],
        operatingMode,
        signal: ac.signal,
        onEvent: (ev) => {
          if (ev.kind === "reasoning_delta") {
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
  }, [input, messages, operatingMode, streaming]);

  return (
    <div className={styles.layout}>
      <header className={styles.header}>
        <div className={styles.titleBlock}>
          <h1 className={styles.title}>Logos 对话</h1>
          <p className={styles.subtitle}>
            V0.1 · POST /api/v1/chat（SSE）· operating_mode 随请求体发送
          </p>
        </div>
        <div className={styles.headerActions}>
          <label className={styles.modeLabel}>
            <span>模式</span>
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
          <button
            type="button"
            className={styles.ghostBtn}
            onClick={() => void refreshHealth()}
          >
            检查健康
          </button>
          <div
            className={styles.health}
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
                发送一条消息开始对话。SSE：reasoning_delta 为 ReAct
                中间输出（多为 JSON），delta 为最终答复；citations 在右侧。
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
                          推理过程（流式）
                        </summary>
                        <pre className={styles.reasoningPre}>{m.reasoning}</pre>
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
              尚无引用事件；后端可在流中发送 event: citations。
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
