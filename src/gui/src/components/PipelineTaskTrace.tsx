import type { PipelineStepEntry } from "../conversation/storeTypes";
import styles from "./PipelineTaskTrace.module.css";

type PipelineTaskTraceProps = {
  steps: PipelineStepEntry[];
  warnings: string[];
  streaming: boolean;
};

export function PipelineTaskTrace({
  steps,
  warnings,
  streaming,
}: PipelineTaskTraceProps) {
  if (steps.length === 0 && warnings.length === 0 && !streaming) {
    return null;
  }

  return (
    <aside
      className={styles.panel}
      data-testid="pipeline-task-trace"
      aria-label="导入流水线进度"
    >
      <h2 className={styles.title}>流水线进度</h2>
      <ol className={styles.stepList}>
        {steps.map((s) => (
          <li
            key={s.stepId}
            className={styles.stepItem}
            data-testid={`pipeline-step-${s.stepId}`}
            data-status={s.status}
          >
            <span className={styles.stepId}>{s.stepId}</span>
            <span className={styles.stepStatus}>{s.status}</span>
            {s.summary ? (
              <span className={styles.stepSummary}>{s.summary}</span>
            ) : null}
          </li>
        ))}
      </ol>
      {streaming && steps.length === 0 ? (
        <p className={styles.muted}>等待阶段事件…</p>
      ) : null}
      {warnings.length > 0 ? (
        <div className={styles.warnings} data-testid="pipeline-warnings">
          <h3 className={styles.warnTitle}>警告</h3>
          <ul>
            {warnings.map((w, i) => (
              <li key={`${i}-${w.slice(0, 24)}`}>{w}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </aside>
  );
}
