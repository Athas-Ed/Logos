import { useState, useCallback } from "react";
import { marked } from "marked";
import styles from "./OutlineResult.module.css";

export interface OutlineResultProps {
  resultText: string;
  streaming: boolean;
  queued: boolean;
  onCopy: () => void;
  onSave: () => void;
  onRewrite: (userText: string, taskFields: Record<string, unknown>) => void;
  onNew: () => void;
  /** Context needed for rewrite */
  originalUserText: string;
  originalTaskFields: Record<string, unknown>;
}

function parseOutline(text: string): { title: string; steps: string[] } | null {
  const trimmed = text.trim();
  if (!trimmed) return null;

  const candidates: string[] = [trimmed];

  // strip markdown code block fences
  const codeBlock = trimmed.match(/```(?:json)?\s*([\s\S]*?)\s*```/);
  if (codeBlock && codeBlock[1]) {
    candidates.unshift(codeBlock[1].trim());
  }

  for (const candidate of candidates) {
    try {
      const parsed = JSON.parse(candidate);
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        // ReAct JSON wrapper: extract final_answer
        if (parsed.final_answer !== undefined) {
          const fa = parsed.final_answer;
          if (typeof fa === "string") {
            try {
              const inner = JSON.parse(fa);
              if (inner && typeof inner.title === "string" && Array.isArray(inner.steps)) {
                return { title: inner.title, steps: inner.steps.map(String) };
              }
            } catch { /* not JSON string */ }
          } else if (fa && typeof fa === "object" && !Array.isArray(fa) && typeof (fa as Record<string,unknown>).title === "string" && Array.isArray((fa as Record<string,unknown>).steps)) {
            const obj = fa as { title: string; steps: unknown[] };
            return { title: obj.title, steps: obj.steps.map(String) };
          }
        }
        // direct outline object
        if (typeof parsed.title === "string" && Array.isArray(parsed.steps)) {
          return { title: parsed.title, steps: parsed.steps.map(String) };
        }
      }
    } catch {
      // not JSON, try next candidate
    }
  }

  return null;
}

function outlineToMarkdown(text: string): string {
  const outline = parseOutline(text);
  if (!outline) return text;
  return `# ${outline.title}\n\n${outline.steps.map((s, i) => `${i + 1}. ${s}`).join("\n")}\n`;
}

export function OutlineResult({
  resultText,
  streaming: _streaming,
  queued,
  onCopy,
  onSave,
  onRewrite,
  onNew,
  originalUserText,
  originalTaskFields,
}: OutlineResultProps) {
  const [viewMode, setViewMode] = useState<"json" | "markdown">("json");
  const [expandedSteps, setExpandedSteps] = useState<Set<number>>(new Set());
  const [showRewrite, setShowRewrite] = useState(false);
  const [rewriteFeedback, setRewriteFeedback] = useState("");

  const outline = parseOutline(resultText);
  const steps = outline?.steps ?? [];
  const title = outline?.title ?? "大纲";

  const mdContent = outlineToMarkdown(resultText);

  const renderMarkdown = (content: string) => ({
    __html: marked.parse(content, { async: false }) as string,
  });

  const toggleStep = (i: number) => {
    setExpandedSteps((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  };

  const handleRewrite = useCallback(() => {
    const fb = rewriteFeedback.trim();
    if (!fb) return;
    const combined = [
      originalUserText || resultText.slice(0, 200),
      "",
      "【当前大纲】",
      resultText,
      "",
      "【修改意见】",
      fb,
      "",
      "请根据以上修改意见重新生成一份大纲。",
    ].join("\n");
    setShowRewrite(false);
    setRewriteFeedback("");
    onRewrite(combined, originalTaskFields);
  }, [rewriteFeedback, resultText, originalUserText, originalTaskFields, onRewrite]);

  return (
    <div className={styles.result} data-testid="outline-result">
      <div className={styles.toolbar}>
        <h3 className={styles.title}>{title}</h3>
        <div className={styles.toolbarActions}>
          <button
            type="button"
            className={`${styles.secondaryBtn} ${viewMode === "json" ? styles.activeBtn : ""}`}
            data-testid="outline-view-json"
            onClick={() => setViewMode("json")}
          >
            JSON
          </button>
          <button
            type="button"
            className={`${styles.secondaryBtn} ${viewMode === "markdown" ? styles.activeBtn : ""}`}
            data-testid="outline-view-md"
            onClick={() => setViewMode("markdown")}
          >
            Markdown
          </button>
          <button
            type="button"
            className={styles.secondaryBtn}
            data-testid="outline-save"
            onClick={onSave}
          >
            保存
          </button>
          <button
            type="button"
            className={styles.secondaryBtn}
            data-testid="outline-setting-check"
            onClick={() => alert("设定一致性检查将在 setting_check Skill 完成后接入。")}
          >
            设定检查
          </button>
          <button
            type="button"
            className={styles.secondaryBtn}
            data-testid="outline-copy"
            onClick={onCopy}
          >
            复制
          </button>
          <button
            type="button"
            className={styles.secondaryBtn}
            data-testid="outline-rewrite"
            onClick={() => setShowRewrite((v) => !v)}
          >
            重写
          </button>
          <button
            type="button"
            className={styles.secondaryBtn}
            data-testid="outline-new"
            onClick={onNew}
          >
            新建
          </button>
        </div>
      </div>

      {showRewrite ?
        <div className={styles.rewritePanel}>
          <textarea
            className={styles.textarea}
            data-testid="rewrite-feedback"
            rows={3}
            placeholder="输入修改意见（如：减少步骤、增加悬疑元素、以张三为主角…）"
            value={rewriteFeedback}
            disabled={queued}
            onChange={(e) => setRewriteFeedback(e.target.value)}
          />
          <div className={styles.rewriteActions}>
            <button
              type="button"
              className={styles.primaryBtn}
              data-testid="rewrite-submit"
              disabled={!rewriteFeedback.trim() || queued}
              onClick={handleRewrite}
            >
              重新生成
            </button>
            <button
              type="button"
              className={styles.secondaryBtn}
              onClick={() => {
                setShowRewrite(false);
                setRewriteFeedback("");
              }}
            >
              取消
            </button>
          </div>
        </div>
      : null}

      {steps.length > 0 && viewMode === "json" ?
        <div className={styles.stepCards} data-testid="outline-step-cards">
          {steps.map((step, i) => {
            const isExpanded = expandedSteps.has(i);
            return (
              <div
                key={i}
                className={`${styles.stepCard} ${isExpanded ? styles.stepCardExpanded : ""}`}
                data-testid={`outline-step-${i}`}
              >
                <button
                  type="button"
                  className={styles.stepCardHeader}
                  onClick={() => toggleStep(i)}
                  aria-expanded={isExpanded}
                >
                  <span className={styles.stepIndex}>步骤 {i + 1}</span>
                  <span className={styles.stepPreview}>
                    {step.length > 60 ? step.slice(0, 60) + "\u2026" : step}
                  </span>
                  <span className={styles.stepToggle}>
                    {isExpanded ? "\u25B4" : "\u25BE"}
                  </span>
                </button>
                {isExpanded ?
                  <div
                    className={styles.stepCardBody}
                    dangerouslySetInnerHTML={renderMarkdown(step)}
                  />
                : null}
              </div>
            );
          })}
        </div>
      :
        <div
          className={styles.mdPreview}
          data-testid="outline-md-preview"
          dangerouslySetInnerHTML={renderMarkdown(mdContent)}
        />
      }
    </div>
  );
}
