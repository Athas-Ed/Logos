import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchBootstrap } from "../api/bootstrap";
import {
  isConversationIpcAvailable,
  listConversationsIpc,
} from "../conversation/ipc";
import type { ConversationMeta } from "../conversation/types";
import styles from "./CachePage.module.css";

async function resolveStorageRoot(): Promise<string | null> {
  const ipcRoot = window.logosElectron?.conversations?.root;
  if (ipcRoot) {
    try {
      const p = await ipcRoot();
      if (p.trim()) {
        return p.trim();
      }
    } catch {
      /* fallback */
    }
  }
  const boot = await fetchBootstrap();
  return boot?.conversations_cache_root?.trim() ?? null;
}

export function CachePage() {
  const [archived, setArchived] = useState<ConversationMeta[]>([]);
  const [ipcReady, setIpcReady] = useState(false);
  const [storageRoot, setStorageRoot] = useState<string | null>(null);

  useEffect(() => {
    void resolveStorageRoot().then(setStorageRoot);
  }, []);

  useEffect(() => {
    const ok = isConversationIpcAvailable();
    setIpcReady(ok);
    if (!ok) {
      return;
    }
    void (async () => {
      const metas = await listConversationsIpc();
      setArchived(
        metas
          .filter((m) => m.status === "archived")
          .sort((a, b) => b.updated_at.localeCompare(a.updated_at)),
      );
    })();
  }, []);

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>已归档会话</h1>
        <Link
          className={styles.backLink}
          to="/settings"
          data-testid="cache-back-to-settings"
        >
          返回设置
        </Link>
      </header>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>存储位置（档 B）</h2>
        <p className={styles.muted}>
          每个任务一个 JSON 文件，目录由配置{" "}
          <code>paths.CONVERSATIONS_CACHE</code> 决定（默认仓库内{" "}
          <code>workspace/conversations/</code>，已由 <code>.gitignore</code>{" "}
          忽略）。
        </p>
        {storageRoot ?
          <p className={styles.pathBox} data-testid="conversations-cache-root">
            <code>{storageRoot}</code>
            <span className={styles.pathSuffix}>
              \ &lt;任务 id&gt;.json
            </span>
          </p>
        : (
          <p className={styles.muted} role="status">
            正在解析路径…（需 Electron 或已启动后端以读取 bootstrap）
          </p>
        )}
        <p className={styles.muted}>
          文件中 <code>status</code> 为 <code>archived</code>{" "}
          的即为已归档任务；顶栏「归档」会从标签栏移除，但<strong>不删除</strong>
          该 JSON。
        </p>
        <p className={styles.muted}>
          覆盖方式：<code>config/local.yaml</code> 中修改{" "}
          <code>paths.CONVERSATIONS_CACHE</code>，或环境变量{" "}
          <code>LOGOS_PATHS__CONVERSATIONS_CACHE</code> /{" "}
          <code>LOGOS_CONVERSATIONS_CACHE</code>（须位于仓库根之下）。
        </p>
        <p className={styles.muted}>
          纯 Vite 浏览器开发（无 Electron IPC）时不会写盘，列表为空属正常。
        </p>
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>归档列表</h2>
        {!ipcReady ?
          <p className={styles.muted} role="status">
            当前环境无法访问本地会话目录（请用 Electron 壳）。
          </p>
        : archived.length === 0 ?
          <p className={styles.muted} role="status">
            暂无 <code>archived</code> 会话。在任务页点击「归档任务」或顶栏「归档当前会话」后会出现于此。
          </p>
        : (
          <ul className={styles.list} data-testid="archived-session-list">
            {archived.map((m) => (
              <li key={m.id} className={styles.listItem}>
                <span className={styles.itemTitle}>{m.title}</span>
                <span className={styles.itemMeta}>
                  <code>{m.id}</code> · {m.byte_size.toLocaleString()} 字节 ·{" "}
                  {m.updated_at}
                </span>
              </li>
            ))}
          </ul>
        )}
        <p className={styles.muted}>
          恢复、批量销毁等操作顺延至 G5；本页仅只读列举。
        </p>
      </section>
    </div>
  );
}
