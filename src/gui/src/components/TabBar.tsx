import { useNavigate, useParams } from "react-router-dom";
import {
  useConversationActions,
  useConversationMeta,
  useConversationState,
} from "../conversation/ConversationProvider";
import { conversationNavPath } from "../skills/routing";
import styles from "./TabBar.module.css";

function TabItem({ id, active }: { id: string; active: boolean }) {
  const navigate = useNavigate();
  const actions = useConversationActions();
  const conv = useConversationState(id);
  const title = conv?.title?.trim() || id;

  return (
    <div
      role="tab"
      aria-selected={active}
      className={`${styles.tab} ${active ? styles.tabActive : ""}`}
      data-testid={`tab-${id}`}
    >
      <button
        type="button"
        className={styles.tabLabel}
        title={title}
        onClick={() => {
          if (conv) {
            navigate(conversationNavPath(conv));
          }
        }}
      >
        {conv?.streaming ? "… " : null}
        {conv?.queued ? "⏳ " : null}
        {title}
      </button>
      {conv?.unread && !active ? (
        <span className={styles.unreadDot} aria-label="未读" />
      ) : null}
      <button
        type="button"
        className={styles.closeBtn}
        aria-label={`归档会话 ${title}`}
        title="归档（从标签栏移除）"
        onClick={(e) => {
          e.stopPropagation();
          actions.archiveTab(id);
        }}
      >
        ×
      </button>
    </div>
  );
}

export function TabBar() {
  const { id: routeId } = useParams<{ id: string }>();
  const meta = useConversationMeta();

  if (!meta.ready) {
    return null;
  }

  return (
    <nav className={styles.tabBar} aria-label="会话标签">
      <div className={styles.tabList} role="tablist">
        {meta.openTabIds.map((id) => (
          <TabItem key={id} id={id} active={id === routeId} />
        ))}
        <TabNewButton />
      </div>
      <span className={styles.meta} data-testid="sse-queue-meta">
        SSE {meta.activeStreamCount}/{meta.sseMaxNum}
        {meta.queueLength > 0 ? ` · 排队 ${meta.queueLength}` : ""}
      </span>
    </nav>
  );
}

function TabNewButton() {
  const navigate = useNavigate();
  return (
    <button
      type="button"
      className={styles.newTabBtn}
      data-testid="tab-new-skill"
      aria-label="返回技能面板"
      title="选择 Skill 开始新任务"
      onClick={() => navigate("/")}
    >
      +
    </button>
  );
}
