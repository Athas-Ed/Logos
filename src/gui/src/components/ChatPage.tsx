import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useNavigate, useParams } from "react-router-dom";

import { DEFAULT_CONVERSATION_ID } from "../conversation/constants";

import { useConversation } from "../conversation/ConversationProvider";

import { isValidConversationId } from "../conversation/validate";

import { isInspireChatState } from "../skills/routing";

import { getSkillMeta } from "../skills/registry";

import { LabChatControls } from "./LabChatControls";

import { SkillInstructions } from "./SkillInstructions";

import styles from "./ChatPage.module.css";



type ChatPageProps = {

  /** Vite 范式 / Prompt 试验台（/lab/:id） */

  lab?: boolean;

};



const draftByConversation = new Map<string, string>();



export function ChatPage({ lab = false }: ChatPageProps) {

  const { id: routeConversationId } = useParams<{ id: string }>();

  const navigate = useNavigate();

  const conversationId = useMemo(() => {

    if (isValidConversationId(routeConversationId)) {

      return routeConversationId;

    }

    return DEFAULT_CONVERSATION_ID;

  }, [routeConversationId]);



  useEffect(() => {

    if (!routeConversationId || isValidConversationId(routeConversationId)) {

      return;

    }

    navigate(lab ? "/" : `/chat/${DEFAULT_CONVERSATION_ID}`, { replace: true });

  }, [lab, navigate, routeConversationId]);



  const { actions, conv, meta } = useConversation(conversationId);



  const [shellBackendHint, setShellBackendHint] = useState<string | null>(null);

  const [shellBackendTone, setShellBackendTone] = useState<"warn" | "err">(

    "warn",

  );

  const [draft, setDraft] = useState(

    () => draftByConversation.get(conversationId) ?? "",

  );

  const listEndRef = useRef<HTMLDivElement | null>(null);

  const sendingRef = useRef(false);



  const messages = conv?.messages ?? [];

  const citations = conv?.citations ?? [];

  const toolTraceLog = conv?.toolTraceLog ?? [];

  const presentation = conv?.presentation ?? "work";

  const streaming = Boolean(conv?.streaming);

  const queued = Boolean(conv?.queued);

  const streamError = conv?.streamError ?? null;

  const persistError = conv?.persistError ?? null;



  const inspireChat = Boolean(conv && isInspireChatState(conv));

  const skillMeta = conv?.skillId ? getSkillMeta(conv.skillId) : undefined;



  useEffect(() => {

    if (lab || !conv?.hydrated || conv.skillId) {

      return;

    }

    actions.patchConversation(conversationId, {

      skillId: "chat_inspire",

      title: getSkillMeta("chat_inspire")?.display_name ?? "创作启发对话",

    });

  }, [actions, conversationId, conv?.hydrated, conv?.skillId, lab]);



  useEffect(() => {

    setDraft(draftByConversation.get(conversationId) ?? "");

  }, [conversationId]);



  const setDraftForTab = useCallback(

    (value: string) => {

      draftByConversation.set(conversationId, value);

      setDraft(value);

    },

    [conversationId],

  );



  useEffect(() => {

    const bridge = window.logosElectron?.onBackendStatus;

    if (!bridge) {

      return;

    }

    return bridge((s) => {

      if (s.state === "ready") {

        setShellBackendHint(null);

        return;

      }

      setShellBackendTone(s.state === "failed" ? "err" : "warn");

      setShellBackendHint(

        s.message ?? (s.state === "failed" ? "后端不可用" : "后端恢复中"),

      );

    });

  }, []);



  useEffect(() => {

    listEndRef.current?.scrollIntoView({ behavior: "smooth" });

  }, [messages, streaming, toolTraceLog]);



  const send = useCallback(() => {

    const text = draft.trim();

    if (!text || streaming || queued || sendingRef.current) {

      return;

    }

    sendingRef.current = true;

    draftByConversation.set(conversationId, "");

    setDraft("");

    actions.sendMessage(conversationId, text);

    queueMicrotask(() => {

      sendingRef.current = false;

    });

  }, [actions, conversationId, draft, queued, streaming]);



  const stopStream = useCallback(() => {

    actions.stopStream(conversationId);

  }, [actions, conversationId]);



  if (!conv?.hydrated || (!lab && !meta.ready)) {

    return (

      <div className={styles.layout} data-testid="chat-loading">

        <p className={styles.muted}>正在加载会话…</p>

      </div>

    );

  }



  const labSkillId = conv.skillId ?? "lint_zh";

  const pageTestId = lab ? "lab-chat-page" : inspireChat ? "inspire-chat-page" : "chat-page";

  const headerTitle = lab

    ? "范式 / Prompt 试验台"

    : inspireChat

      ? (skillMeta?.display_name ?? "创作启发对话")

      : "Logos 对话";



  return (

    <div className={styles.layout} data-testid={pageTestId}>

      <a href="#logos-main-content" className={styles.skipLink}>

        跳到主内容

      </a>

      {persistError ? (

        <div

          className={styles.shellBannerWarn}

          role="alert"

          data-testid="persist-error-banner"

        >

          {persistError}

        </div>

      ) : null}

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

      {lab ? (

        <LabChatControls

          conversationId={conversationId}

          skillId={labSkillId}

          paradigmOverride={conv.paradigmOverride}

          operatingMode={conv.operatingMode}

          presentation={conv.presentation}

        />

      ) : null}

      <header className={styles.header}>

        <div className={styles.titleBlock}>

          <h1 className={styles.title}>{headerTitle}</h1>

          <p className={styles.subtitle}>

            {inspireChat ? (

              <>

                dialogue · 多轮启发 · Skill{" "}

                <code className={styles.inlineCode}>{conv.skillId}</code>

                {conv.skillId ? (

                  <>

                    {" "}

                    · 会话 <code className={styles.inlineCode}>{conversationId}</code>

                  </>

                ) : null}

              </>

            ) : lab ? (

              <>

                V0.2 · POST /api/v1/chat（SSE）· 会话{" "}

                <code className={styles.inlineCode}>{conversationId}</code>

                {" "}

                · Skill <code className={styles.inlineCode}>{labSkillId}</code>

              </>

            ) : (

              <>

                V0.2 · POST /api/v1/chat（SSE）· 会话{" "}

                <code className={styles.inlineCode}>{conversationId}</code>

                {" "}

                · 运行模式 / 展示档位 / Prompt 回显见设置页

              </>

            )}

          </p>

        </div>

      </header>



      <div

        className={inspireChat ? styles.mainInspire : styles.main}

        id="logos-main-content"

      >

        <section className={styles.chatPanel}>
          {conv.skillId ? <SkillInstructions skillId={conv.skillId} /> : null}

          {streamError ? (

            <div className={styles.errorBanner} role="alert">

              {streamError}

            </div>

          ) : null}

          {queued ? (

            <p className={styles.muted} role="status">

              已加入发送队列（并发上限 {meta.sseMaxNum}）…

            </p>

          ) : null}



          <div className={styles.messageList} data-testid="chat-message-list">

            {messages.length === 0 ? (

              <p className={styles.emptyHint}>

                发送消息开始对话。切换顶栏标签不会中断后台 SSE；超额请求将排队。

              </p>

            ) : (

              messages.map((m, i) => (

                <article

                  key={`${i}-${m.role}`}

                  className={

                    m.role === "user" ? styles.bubbleUser : styles.bubbleAssistant

                  }

                  data-testid={

                    m.role === "user" ? "chat-message-user" : "chat-message-assistant"

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

              placeholder={

                "输入消息…（Enter 发送，Shift+Enter 换行）"

              }

              value={draft}

              disabled={streaming || queued}

              data-testid="chat-composer-textarea"

              onChange={(e) => setDraftForTab(e.target.value)}

              onKeyDown={(e) => {

                if (e.key === "Enter" && !e.shiftKey) {

                  e.preventDefault();

                  send();

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

              ) : null}

              <button

                type="button"

                className={styles.primaryBtn}

                disabled={streaming || queued || !draft.trim()}

                data-testid="chat-send"

                onClick={() => send()}

              >

                发送

              </button>

            </div>

          </div>

        </section>



        {!inspireChat ? (

          <aside className={styles.citePanel}>

            <h2 className={styles.citeTitle}>检索引用</h2>

            <p className={styles.citeHint}>

              助手在 ReAct 中调用检索工具后，由 SSE{" "}

              <code className={styles.inlineCode}>citations_*</code>{" "}

              推送的文档路径、片段与相关度分数（非用户 Prompt）。

            </p>

            {citations.length === 0 ? (

              <p className={styles.citeEmpty}>本轮尚无引用事件。</p>

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

        ) : null}

      </div>

    </div>

  );

}


