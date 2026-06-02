import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { streamChat, type StreamChatEvent } from "../api/sseChat";

import { useConversation } from "../conversation/ConversationProvider";

import {
  fetchDraftsList,
  fetchDraftRead,
  promoteDrafts,
  rewriteDrafts,
  type DraftFileEntry,
} from "../api/drafts";

import styles from "./ReviewPage.module.css";

/** 审核晋升 Skill 页面：左栏文件列表，右栏预览/对话，底部操作区。 */
export function ReviewPage() {
  const navigate = useNavigate();
  const { id: conversationId } = useParams<{ id: string }>();
  const { actions } = useConversation(conversationId ?? "");
  const [searchParams] = useSearchParams();
  const scope = searchParams.get("scope") ?? "";
  const scopeLabel = scope || "全部 pending_review";

  // ── 文件列表状态 ──
  const [fileList, setFileList] = useState<DraftFileEntry[]>([]);
  const [checkedPaths, setCheckedPaths] = useState<Set<string>>(new Set());
  const [previewPath, setPreviewPath] = useState<string | null>(null);
  const [previewContent, setPreviewContent] = useState("");
  const [rewritingPaths, setRewritingPaths] = useState<Set<string>>(new Set());

  // ── 发送/对话状态 ──
  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([]);
  const [rightTab, setRightTab] = useState<"preview" | "conversation">("preview");
  const [statusText, setStatusText] = useState("");
  const [errorText, setErrorText] = useState("");

  const listEndRef = useRef<HTMLDivElement | null>(null);

  // ── 加载文件列表 ──
  const loadFiles = useCallback(async () => {
    setStatusText("加载文件列表…");
    try {
      const files = await fetchDraftsList(scope);
      setFileList(files);
      setStatusText(`共 ${files.length} 个文件`);
      // 清除已不存在的勾选
      setCheckedPaths((prev) => {
        const valid = new Set(files.map((f) => f.path));
        return new Set([...prev].filter((p) => valid.has(p)));
      });
    } catch {
      setStatusText("加载文件列表失败");
    }
  }, [scope]);

  useEffect(() => {
    void loadFiles();
  }, [loadFiles]);

  // ── 单击文件预览 ──
  const handlePreview = useCallback(async (path: string) => {
    setPreviewPath(path);
    setRightTab("preview");
    try {
      const content = await fetchDraftRead(path);
      setPreviewContent(content);
    } catch {
      setPreviewContent("（读取失败）");
    }
  }, []);

  // ── 勾选切换 ──
  const toggleCheck = useCallback((path: string) => {
    setCheckedPaths((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }, []);

  // ── 晋升 ──
  const canPromote = checkedPaths.size > 0 && !streaming && rewritingPaths.size === 0;
  const handlePromote = useCallback(async () => {
    if (!canPromote) return;
    const paths = [...checkedPaths].filter((p) => !rewritingPaths.has(p));
    if (paths.length === 0) return;
    setStatusText(`晋升中 (${paths.length} 个文件)…`);
    try {
      const result = await promoteDrafts(paths);
      if (result.ok) {
        setStatusText(`✅ 已晋升 ${result.applied.length} 个文件`);
        // 从勾选移除已晋升的
        setCheckedPaths((prev) => {
          const next = new Set(prev);
          for (const p of result.applied) next.delete(p);
          return next;
        });
        // 如果预览的文件被晋升了，清除预览
        if (previewPath && result.applied.includes(previewPath)) {
          setPreviewPath(null);
          setPreviewContent("");
        }
      } else {
        setStatusText(`❌ 晋升完成，${result.failed.length} 个失败: ${result.notes}`);
      }
      void loadFiles(); // 刷新列表
    } catch {
      setStatusText("晋升请求异常");
    }
  }, [canPromote, checkedPaths, rewritingPaths, previewPath, loadFiles]);

  // ── 发送（附带文件清单上下文） ──
  const handleSend = useCallback(async () => {
    const text = draft.trim();
    if (!text || streaming) return;
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setDraft("");
    setRightTab("conversation");
    setStreaming(true);
    setErrorText("");

    // 构造附带文件清单的 system 前缀
    const fileContext = fileList
      .map((f) => `- ${f.path}`)
      .join("\n");
    const systemNote = `当前 pending_review 下的文件清单：\n${fileContext}`;

    const acc = { assistantText: "", reasoningText: "" };
    try {
      await streamChat({
        messages: [
          { role: "system", content: systemNote },
          { role: "user", content: text },
        ],
        operatingMode: "author",
        presentation: "work",
        signal: new AbortController().signal,
        onEvent: (ev: StreamChatEvent) => {
          if (ev.kind === "delta") {
            acc.assistantText += ev.text;
            setMessages((prev) => {
              const copy = [...prev];
              const last = copy[copy.length - 1];
              if (last?.role === "assistant") {
                copy[copy.length - 1] = { ...last, content: acc.assistantText };
              } else {
                copy.push({ role: "assistant", content: acc.assistantText });
              }
              return copy;
            });
          } else if (ev.kind === "error") {
            setErrorText(`${ev.code}: ${ev.message}`);
          } else if (ev.kind === "done") {
            // done
          }
        },
      });
    } catch {
      setErrorText("SSE 请求异常");
    } finally {
      setStreaming(false);
    }
  }, [draft, streaming, fileList]);

  // ── 打回（重写） ──
  const canReject = checkedPaths.size > 0 && !streaming && rewritingPaths.size === 0;
  const handleReject = useCallback(async () => {
    if (!canReject) return;
    const paths = [...checkedPaths].filter((p) => !rewritingPaths.has(p));
    if (paths.length === 0) return;

    // 锁定
    setRewritingPaths((prev) => new Set([...prev, ...paths]));
    setStatusText(`打回重写中 (${paths.length} 个文件)…`);
    setErrorText("");

    // 读取每个文件的原文
    const fileContents: { path: string; content: string }[] = [];
    for (const p of paths) {
      const content = await fetchDraftRead(p);
      fileContents.push({ path: p, content });
    }

    // 记录用户意图到对话区
    setMessages((prev) => [
      ...prev,
      { role: "user", content: `打回重写 ${paths.length} 个文件：${draft.trim() || "优化修订"}` },
    ]);

    // 调结构化重写 API（服务端调 LLM JSON mode，直接写入文件）
    const result = await rewriteDrafts(
      fileContents,
      draft.trim(),
    );

    // 解锁
    setRewritingPaths((prev) => {
      const next = new Set(prev);
      for (const p of paths) next.delete(p);
      return next;
    });

    if (result.ok) {
      setStatusText(`✅ 已重写 ${result.written.length} 个文件${result.failed.length > 0 ? `，${result.failed.length} 个失败` : ""}`);
      // 刷新预览
      if (previewPath) {
        const content = await fetchDraftRead(previewPath);
        setPreviewContent(content);
      }
    } else {
      setStatusText(`❌ 重写失败：${result.failed.length} 个文件未能写入`);
    }
  }, [canReject, checkedPaths, rewritingPaths, draft, previewPath]);

  // ── 滚动到底部 ──
  useEffect(() => {
    listEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const displayCheckedCount = useMemo(
    () => [...checkedPaths].filter((p) => !rewritingPaths.has(p)).length,
    [checkedPaths, rewritingPaths],
  );

  return (
    <div className={styles.page} data-testid="review-page">
      <header className={styles.header}>
        <div className={styles.headerLeft}>
          <button
            type="button"
            className={styles.backBtn}
            data-testid="review-back"
            onClick={() => {
              if (conversationId) actions.archiveTab(conversationId);
              navigate("/skills");
            }}
          >
            ← 返回
          </button>
          <h1 className={styles.title}>审核晋升</h1>
        </div>
        <span className={styles.scopeHint}>{scopeLabel}</span>
        <button
          type="button"
          className={styles.refreshBtn}
          onClick={() => void loadFiles()}
        >
          刷新
        </button>
      </header>

      <div className={styles.body}>
        {/* ── 左栏：文件列表 ── */}
        <aside className={styles.leftPanel} aria-label="文件列表">
          {fileList.length === 0 ? (
            <p className={styles.muted}>暂无文件</p>
          ) : (
            fileList.map((f) => {
              const locked = rewritingPaths.has(f.path);
              return (
                <div
                  key={f.path}
                  className={`${styles.fileItem} ${previewPath === f.path ? styles.fileItemActive : ""} ${locked ? styles.fileLocked : ""}`}
                  onClick={() => void handlePreview(f.path)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") void handlePreview(f.path);
                  }}
                >
                  <input
                    type="checkbox"
                    className={styles.fileCheckbox}
                    checked={checkedPaths.has(f.path)}
                    disabled={locked}
                    onChange={() => toggleCheck(f.path)}
                    onClick={(e) => e.stopPropagation()}
                  />
                  <span className={styles.fileName}>{f.name}</span>
                  {locked ? <span className={styles.lockBadge}>✎</span> : null}
                </div>
              );
            })
          )}
        </aside>

        {/* ── 右栏：预览 / 对话 ── */}
        <section className={styles.rightPanel}>
          <div className={styles.rightTabs}>
            <button
              type="button"
              className={`${styles.rightTab} ${rightTab === "preview" ? styles.rightTabActive : ""}`}
              onClick={() => setRightTab("preview")}
            >
              文件预览
            </button>
            <button
              type="button"
              className={`${styles.rightTab} ${rightTab === "conversation" ? styles.rightTabActive : ""}`}
              onClick={() => setRightTab("conversation")}
            >
              对话
            </button>
          </div>

          {rightTab === "preview" ? (
            previewPath ? (
              <div className={styles.previewArea} data-testid="review-preview">
                {previewContent}
              </div>
            ) : (
              <div className={styles.previewPlaceholder}>
                单击左侧文件以预览
              </div>
            )
          ) : (
            <div className={styles.conversationArea}>
              {messages.length === 0 ? (
                <p className={styles.muted}>输入内容并点击发送或打回开始对话</p>
              ) : (
                messages.map((m, i) => (
                  <article
                    key={i}
                    className={m.role === "user" ? styles.bubbleUser : styles.bubbleAssistant}
                  >
                    {m.content || (m.role === "assistant" ? "…" : "")}
                  </article>
                ))
              )}
              <div ref={listEndRef} />
            </div>
          )}

          {/* ── 状态栏 ── */}
          {statusText || errorText ? (
            <div className={styles.statusBar}>
              {errorText ? (
                <span className={styles.errorBanner}>{errorText}</span>
              ) : null}
              <span className={styles.muted}>{statusText}</span>
            </div>
          ) : null}

          {/* ── 底部输入区 ── */}
          <div className={styles.inputPanel}>
            <textarea
              className={styles.textarea}
              rows={2}
              placeholder="输入内容…（不输入则使用默认要求）"
              value={draft}
              disabled={streaming}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
            />
            <div className={styles.actionRow}>
              <button
                type="button"
                className={styles.primaryBtn}
                disabled={!draft.trim() || streaming}
                onClick={() => void handleSend()}
              >
                发送
              </button>
              <button
                type="button"
                className={styles.promoteBtn}
                disabled={!canPromote}
                onClick={() => void handlePromote()}
              >
                晋升 ({displayCheckedCount})
              </button>
              <button
                type="button"
                className={styles.rejectBtn}
                disabled={!canReject}
                onClick={() => void handleReject()}
              >
                打回 ({displayCheckedCount})
              </button>
              {streaming ?
                <span className={styles.muted}>流式响应中…</span>
              : null}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
