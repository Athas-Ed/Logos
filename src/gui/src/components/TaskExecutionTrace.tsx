import type { ChatMessage, CitationItem, PresentationMode } from "../types/chat";
import styles from "./TaskExecutionTrace.module.css";

type TaskExecutionTraceProps = {
  paradigm: "dialogue" | "react" | "plan" | "pipeline";
  presentation: PresentationMode;
  messages: ChatMessage[];
  citations: CitationItem[];
  toolTraceLog: string[];
  streaming: boolean;
};

export function TaskExecutionTrace({
  paradigm,
  presentation,
  messages,
  citations,
  toolTraceLog,
  streaming,
}: TaskExecutionTraceProps) {
  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");
  const reasoning = lastAssistant?.reasoning?.trim() ?? "";
  const showReactHint = paradigm === "react";
  const hasTrace =
    toolTraceLog.length > 0 || citations.length > 0 || reasoning.length > 0;

  if (!showReactHint && !hasTrace && !streaming) {
    return null;
  }

  return (
    <aside
      className={styles.panel}
      data-testid="task-execution-trace"
      aria-label="执行轨迹与检索引用"
    >
      <h2 className={styles.title}>执行轨迹</h2>
      <p className={styles.hint}>
        {showReactHint
          ? "ReAct 工具调用与检索引用（工作档为摘要，开发者档为全文）。"
          : "对话范式通常无工具轨迹；若出现引用事件会显示在下方。"}
      </p>

      {reasoning ? (
        <details className={styles.section} open={streaming}>
          <summary className={styles.sectionSummary}>
            推理（{presentation === "work" ? "摘要" : "全文"}）
          </summary>
          <pre className={styles.reasoningPre}>{reasoning}</pre>
        </details>
      ) : null}

      <details
        className={styles.section}
        open={toolTraceLog.length > 0 || streaming}
      >
        <summary className={styles.sectionSummary}>
          工具轨迹（{toolTraceLog.length}）
        </summary>
        {toolTraceLog.length === 0 ? (
          <p className={styles.empty}>
            {streaming ? "等待工具调用…" : "本轮尚无工具事件。"}
          </p>
        ) : (
          <pre className={styles.traceBlock}>{toolTraceLog.join("\n---\n")}</pre>
        )}
      </details>

      <details className={styles.section} open={citations.length > 0}>
        <summary className={styles.sectionSummary}>
          检索引用（{citations.length}）
        </summary>
        {citations.length === 0 ? (
          <p className={styles.empty}>尚无 citations 事件。</p>
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
      </details>
    </aside>
  );
}
