import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { useConversation } from "../conversation/ConversationProvider";
import { PipelineTaskTrace } from "../components/PipelineTaskTrace";
import { TaskExecutionTrace } from "../components/TaskExecutionTrace";
import type { TaskPhase } from "../conversation/storeTypes";
import { SkillInstructions } from "../components/SkillInstructions";
import { getSkillMeta } from "../skills/registry";
import styles from "./TaskPage.module.css";

function stepClass(phase: TaskPhase, target: TaskPhase): string {
  return phase === target ? `${styles.step} ${styles.stepActive}` : styles.step;
}

export function TaskPage() {
  const { id } = useParams<{ id: string }>();
  const conversationId = id ?? "";
  const { actions, conv } = useConversation(conversationId);
  const [draft, setDraft] = useState("");
  const listEndRef = useRef<HTMLDivElement | null>(null);

  const skill = conv?.skillId ? getSkillMeta(conv.skillId) : undefined;
  const phase: TaskPhase = conv?.taskPhase ?? "input";
  const messages = conv?.messages ?? [];
  const citations = conv?.citations ?? [];
  const toolTraceLog = conv?.toolTraceLog ?? [];
  const pipelineSteps = conv?.pipelineSteps ?? [];
  const pipelineWarnings = conv?.pipelineWarnings ?? [];
  const presentation = conv?.presentation ?? "work";
  const streaming = Boolean(conv?.streaming);
  const queued = Boolean(conv?.queued);
  const streamError = conv?.streamError ?? null;
  const isPipeline = skill?.paradigm === "pipeline";
  const showReactTrace =
    phase !== "input" &&
    skill?.paradigm === "react" &&
    (toolTraceLog.length > 0 || citations.length > 0 || streaming);
  const showPipelineTrace =
    phase !== "input" &&
    isPipeline &&
    (pipelineSteps.length > 0 || pipelineWarnings.length > 0 || streaming);
  const showTracePanel = showReactTrace || showPipelineTrace;
  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");
  const resultText = lastAssistant?.content?.trim() ?? "";

  const copyResult = useCallback(async () => {
    if (!resultText) return;
    try {
      await navigator.clipboard.writeText(resultText);
    } catch {
      /* 浏览器策略限制时忽略 */
    }
  }, [resultText]);

  useEffect(() => {
    if (phase === "input" && conv?.taskInputText) {
      setDraft(conv.taskInputText);
    } else if (phase === "input" && !conv?.taskInputText) {
      setDraft("");
    }
  }, [conversationId, phase, conv?.taskInputText]);

  useEffect(() => {
    listEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streaming, toolTraceLog, citations]);

  const submit = useCallback(() => {
    const text = draft.trim();
    if (!text || streaming || queued) {
      return;
    }
    actions.submitTaskRun(conversationId, text);
  }, [actions, conversationId, draft, queued, streaming]);

  if (!id || !conv) {
    return (
      <div className={styles.page}>
        <p className={styles.muted}>任务不存在或尚未加载。</p>
      </div>
    );
  }

  if (!conv.hydrated) {
    return (
      <div className={styles.page} data-testid="task-page-loading">
        <p className={styles.muted}>正在加载任务…</p>
      </div>
    );
  }

  if (!conv.skillId) {
    return (
      <div className={styles.page}>
        <p className={styles.muted}>此会话未绑定 Skill，请从技能面板创建任务。</p>
      </div>
    );
  }

  return (
    <div className={styles.page} data-testid="task-page">
      <header className={styles.header}>
        <h1 className={styles.title}>{conv.title}</h1>
        <p className={styles.meta}>
          {skill ?
            `${skill.display_name} · ${skill.paradigm}`
          : conv.skillId}
        </p>
        <div className={styles.steps} aria-label="任务步骤">
          <span className={stepClass(phase, "input")}>② 输入</span>
          <span className={stepClass(phase, "running")}>③ 执行</span>
          <span className={stepClass(phase, "done")}>完成</span>
        </div>
      </header>

      <div
        className={
          showTracePanel ? `${styles.body} ${styles.bodyWithTrace}` : styles.body
        }
      >
        <div className={styles.mainCol}>
          {streamError ?
            <div className={styles.errorBanner} role="alert">
              {streamError}
            </div>
          : null}
          {queued ?
            <p className={styles.muted} role="status">
              已加入发送队列…
            </p>
          : null}

          {phase === "input" ?
            <section className={styles.inputPanel} aria-label="任务输入">
              {conv.skillId ? <SkillInstructions skillId={conv.skillId} /> : null}
              <label className={styles.label} htmlFor="task-input-text">
                输入
              </label>
              <textarea
                id="task-input-text"
                className={styles.textarea}
                data-testid="task-input-textarea"
                rows={isPipeline ? 10 : 6}
                placeholder={
                  isPipeline
                    ? "粘贴设定正文（角色、地点、世界观片段等）…（Enter 发送，Shift+Enter 换行）"
                    : "输入内容…（Enter 发送，Shift+Enter 换行）"
                }
                value={draft}
                disabled={streaming}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    submit();
                  }
                }}
              />
              <div className={styles.actions}>
                <button
                  type="button"
                  className={styles.primaryBtn}
                  data-testid="task-submit"
                  disabled={!draft.trim() || streaming}
                  onClick={() => submit()}
                >
                  发送
                </button>
              </div>
            </section>
          : null}

          {(phase === "running" || phase === "done") && messages.length > 0 ?
            <div className={styles.messageList} data-testid="task-messages">
              {messages.map((m, i) => (
                <article
                  key={`${i}-${m.role}`}
                  className={
                    m.role === "user" ? styles.bubbleUser : styles.bubbleAssistant
                  }
                >
                  <div className={styles.bubbleMeta}>
                    {m.role === "user" ? "你的输入" : "助手"}
                  </div>
                  <div
                    className={styles.bubbleContent}
                    data-testid={
                      m.role === "assistant" ? "task-assistant-content" : undefined
                    }
                  >
                    {m.role === "assistant" &&
                    (m.reasoning?.length ?? 0) > 0 &&
                    i === messages.length - 1 ? (
                      <details className={styles.inlineReasoning} open={streaming}>
                        <summary>推理片段</summary>
                        <pre>{m.reasoning}</pre>
                      </details>
                    ) : null}
                    {m.role === "assistant" &&
                    streaming &&
                    i === messages.length - 1 &&
                    !m.content ?
                      "…"
                    : m.content}
                  </div>
                </article>
              ))}
              <div ref={listEndRef} />
            </div>
          : null}

          {phase === "running" && !streaming && messages.length === 0 ?
            <p className={styles.muted}>准备执行…</p>
          : null}

          {(phase === "running" || phase === "done") ?
            <div className={styles.actions}>
              {streaming ?
                <button
                  type="button"
                  className={styles.secondaryBtn}
                  data-testid="task-stop"
                  onClick={() => actions.stopStream(conversationId)}
                >
                  中断
                </button>
              : null}
              {phase === "done" ?
                <>
                  {resultText ?
                    <button
                      type="button"
                      className={styles.secondaryBtn}
                      data-testid="task-copy-result"
                      onClick={() => void copyResult()}
                    >
                      复制结果
                    </button>
                  : null}
                  <button
                    type="button"
                    className={styles.primaryBtn}
                    data-testid="task-archive"
                    onClick={() => actions.archiveTab(conversationId)}
                  >
                    归档任务
                  </button>
                  <button
                    type="button"
                    className={styles.secondaryBtn}
                    data-testid="task-new-run"
                    onClick={() => actions.resetTaskToInput(conversationId)}
                  >
                    再来一次
                  </button>
                </>
              : null}
            </div>
          : null}
        </div>

        {showPipelineTrace ?
          <PipelineTaskTrace
            steps={pipelineSteps}
            warnings={pipelineWarnings}
            streaming={streaming}
          />
        : null}
        {showReactTrace && skill ?
          <TaskExecutionTrace
            paradigm={skill.paradigm}
            presentation={presentation}
            messages={messages}
            citations={citations}
            toolTraceLog={toolTraceLog}
            streaming={streaming}
          />
        : null}
      </div>
    </div>
  );
}
