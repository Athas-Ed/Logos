import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useParams } from "react-router-dom";

import { useConversation } from "../conversation/ConversationProvider";

import { splitMessageTurns } from "../conversation/historyClip";

import { stripStepLimitSuffix } from "../conversation/reactStepLimit";

import { ReactStepLimitNotice } from "../components/ReactStepLimitNotice";

import { PipelineTaskTrace } from "../components/PipelineTaskTrace";

import { TaskExecutionTrace } from "../components/TaskExecutionTrace";

import type { TaskPhase } from "../conversation/storeTypes";

import { SkillInstructions } from "../components/SkillInstructions";

import { getSkillMeta } from "../skills/registry";

import { skillSupportsContinuousQa } from "../skills/continuousQa";

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

  const pipelineWrittenPaths = conv?.pipelineWrittenPaths ?? [];

  const promoteMessage = conv?.promoteMessage ?? null;

  const promoteBusy = Boolean(conv?.promoteBusy);

  const presentation = conv?.presentation ?? "work";

  const streaming = Boolean(conv?.streaming);

  const queued = Boolean(conv?.queued);

  const streamError = conv?.streamError ?? null;

  const reactStepLimitTurns = conv?.reactStepLimitTurns ?? [];

  const isReactParadigm = skill?.paradigm === "react";

  const isPipeline = skill?.paradigm === "pipeline";

  const continuousQa = skillSupportsContinuousQa(conv?.skillId);

  const turns = splitMessageTurns(messages);

  const hasCompletedTurn = turns.some(

    (t) => t.assistant && t.assistant.content.trim().length > 0,

  );

  const lastTurnHitLimit =

    reactStepLimitTurns[reactStepLimitTurns.length - 1]?.hit === true;

  const showReactTrace =

    phase === "running" &&

    skill?.paradigm === "react" &&

    (toolTraceLog.length > 0 || citations.length > 0 || streaming);

  const showPipelineTrace =

    phase === "running" &&

    isPipeline &&

    (pipelineSteps.length > 0 || pipelineWarnings.length > 0 || streaming);

  const showTracePanel = showReactTrace || showPipelineTrace;

  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");

  const resultText = lastAssistant?.content?.trim() ?? "";

  const showInputPanel = phase === "input" || (continuousQa && !streaming);



  const assistantTurnIndices = useMemo(() => {

    const indices: number[] = [];

    for (let i = 0; i < messages.length; i += 1) {

      if (messages[i]?.role === "assistant") {

        indices.push(i);

      }

    }

    return indices;

  }, [messages]);



  const displayContent = useCallback(

    (role: string, content: string, assistantTurnIdx: number) => {

      if (role !== "assistant" || !isReactParadigm) {

        return content;

      }

      const meta = reactStepLimitTurns[assistantTurnIdx];

      if (meta?.hit || content.includes("本次 ReAct 步数已达")) {

        return stripStepLimitSuffix(content);

      }

      return content;

    },

    [isReactParadigm, reactStepLimitTurns],

  );



  const copyResult = useCallback(async () => {

    if (!resultText) return;

    try {

      await navigator.clipboard.writeText(resultText);

    } catch {

      /* 浏览器策略限制时忽略 */

    }

  }, [resultText]);



  useEffect(() => {

    if (phase === "input" && conv?.taskInputText && !continuousQa) {

      setDraft(conv.taskInputText);

    } else if (phase === "input" && !conv?.taskInputText && !continuousQa) {

      setDraft("");

    }

  }, [conversationId, phase, conv?.taskInputText, continuousQa]);



  useEffect(() => {

    if (phase === "input" && continuousQa) {

      setDraft("");

    }

  }, [conversationId, phase, continuousQa, hasCompletedTurn]);



  useEffect(() => {

    listEndRef.current?.scrollIntoView({ behavior: "smooth" });

  }, [messages, streaming, toolTraceLog, citations]);



  const submitSend = useCallback(() => {

    const text = draft.trim();

    if (!text || streaming || queued) {

      return;

    }

    if (continuousQa && hasCompletedTurn) {

      actions.submitTaskSend(conversationId, text);

    } else {

      actions.submitTaskRun(conversationId, text);

    }

    setDraft("");

  }, [

    actions,

    conversationId,

    draft,

    continuousQa,

    hasCompletedTurn,

    queued,

    streaming,

  ]);



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

          <span className={stepClass(phase, "input")}>输入</span>

          <span className={stepClass(phase, "running")}>执行</span>

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



          {messages.length > 0 ?

            <div className={styles.messageList} data-testid="task-messages">

              {messages.map((m, i) => {

                const assistantTurnIdx =

                  m.role === "assistant" ?

                    assistantTurnIndices.indexOf(i)

                  : -1;

                const limitMeta =

                  assistantTurnIdx >= 0 ?

                    reactStepLimitTurns[assistantTurnIdx]

                  : undefined;

                const showLimitNotice =

                  isReactParadigm && limitMeta?.hit === true;

                return (

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

                    i === messages.length - 1 ?

                      <details className={styles.inlineReasoning}>

                        <summary>推理片段</summary>

                        <pre>{m.reasoning}</pre>

                      </details>

                    : null}

                    {m.role === "assistant" &&

                    streaming &&

                    i === messages.length - 1 &&

                    !m.content ?

                      "…"

                    : displayContent(m.role, m.content, assistantTurnIdx)}

                    {showLimitNotice ?

                      <ReactStepLimitNotice />

                    : null}

                  </div>

                </article>

                );

              })}

              <div ref={listEndRef} />

            </div>

          : null}



          {showInputPanel ?

            <section className={styles.inputPanel} aria-label="任务输入">

              {lastTurnHitLimit && isReactParadigm ?

                <ReactStepLimitNotice variant="banner" />

              : null}

              {conv.skillId ? <SkillInstructions skillId={conv.skillId} /> : null}

              <label className={styles.label} htmlFor="task-input-text">

                {continuousQa && hasCompletedTurn ? "输入" : "输入"}

              </label>

              <textarea

                id="task-input-text"

                className={styles.textarea}

                data-testid="task-input-textarea"

                rows={3}

                placeholder={

                  lastTurnHitLimit && continuousQa

                    ? "发送新问题将自动开启新会话…（Enter 发送，Shift+Enter 换行）"

                  : isPipeline

                    ? "粘贴设定正文（角色、地点、世界观片段等）…（Enter 发送，Shift+Enter 换行）"

                    : continuousQa && hasCompletedTurn

                      ? "输入内容…（Enter 发送，Shift+Enter 换行）"

                      : "输入内容…（Enter 发送，Shift+Enter 换行）"

                }

                value={draft}

                disabled={streaming || queued}

                onChange={(e) => setDraft(e.target.value)}

                onKeyDown={(e) => {

                  if (e.key === "Enter" && !e.shiftKey) {

                    e.preventDefault();

                    submitSend();

                  }

                }}

              />

              <div className={styles.actions}>

                <button

                  type="button"

                  className={styles.primaryBtn}

                  data-testid="task-submit"

                  disabled={!draft.trim() || streaming || queued}

                  onClick={() => submitSend()}

                >

                  发送

                </button>

                {resultText && !continuousQa ?

                  <button

                    type="button"

                    className={styles.secondaryBtn}

                    data-testid="task-copy-result"

                    onClick={() => void copyResult()}

                  >

                    复制结果

                  </button>

                : null}

                {isPipeline && pipelineWrittenPaths.length > 0 && !streaming ?

                  <>

                    <button

                      type="button"

                      className={styles.primaryBtn}

                      data-testid="task-promote-ksfs"

                      disabled={promoteBusy}

                      onClick={() => void actions.promotePipelineDrafts(conversationId)}

                    >

                      {promoteBusy ? "晋升中…" : "晋升至 KSFS"}

                    </button>

                    {promoteMessage && !promoteBusy ?

                      <button

                        type="button"

                        className={styles.secondaryBtn}

                        data-testid="task-go-review"

                        onClick={() => actions.jumpToReview("setting_entry")}

                      >

                        进入审核

                      </button>

                    : null}

                  </>

                : null}

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

                {!continuousQa && streamError && !streaming ?

                  <button

                    type="button"

                    className={styles.secondaryBtn}

                    data-testid="task-new-run"

                    onClick={() => actions.resetTaskToInput(conversationId)}

                  >

                    返回输入

                  </button>

                : null}

              </div>

              {promoteMessage ?

                <p

                  className={styles.promoteHint}

                  data-testid="task-promote-message"

                  role="status"

                >

                  {promoteMessage}

                </p>

              : null}

            </section>

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

