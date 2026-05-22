import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchBootstrap } from "../api/bootstrap";
import { useConversationActions } from "../conversation/ConversationProvider";
import {
  deleteConversationIpc,
  isConversationIpcAvailable,
  listConversationsIpc,
  totalConversationBytesIpc,
} from "../conversation/ipc";
import type { ConversationMeta } from "../conversation/types";
import { formatByteSize } from "./cacheFormat";
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
  const actions = useConversationActions();
  const [archived, setArchived] = useState<ConversationMeta[]>([]);
  const [selected, setSelected] = useState<Set<string>>(() => new Set());
  const [ipcReady, setIpcReady] = useState(false);
  const [storageRoot, setStorageRoot] = useState<string | null>(null);
  const [totalBytes, setTotalBytes] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!isConversationIpcAvailable()) {
      setArchived([]);
      setTotalBytes(null);
      return;
    }
    const [metas, bytes] = await Promise.all([
      listConversationsIpc(),
      totalConversationBytesIpc(),
    ]);
    setArchived(
      metas
        .filter((m) => m.status === "archived")
        .sort((a, b) => b.updated_at.localeCompare(a.updated_at)),
    );
    setTotalBytes(bytes);
    setSelected((prev) => {
      const ids = new Set(
        metas.filter((m) => m.status === "archived").map((m) => m.id),
      );
      return new Set([...prev].filter((id) => ids.has(id)));
    });
  }, []);

  useEffect(() => {
    void resolveStorageRoot().then(setStorageRoot);
  }, []);

  useEffect(() => {
    const ok = isConversationIpcAvailable();
    setIpcReady(ok);
    if (!ok) {
      return;
    }
    void refresh();
  }, [refresh]);

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const selectAll = () => {
    setSelected(new Set(archived.map((m) => m.id)));
  };

  const clearSelection = () => {
    setSelected(new Set());
  };

  const runRestore = async () => {
    if (selected.size === 0 || busy) {
      return;
    }
    setBusy(true);
    setActionError(null);
    const ids = [...selected];
    let okCount = 0;
    for (const id of ids) {
      const ok = await actions.restoreArchivedConversation(id);
      if (ok) {
        okCount += 1;
      }
    }
    if (okCount === 0) {
      setActionError("恢复失败，请重试。");
    }
    await refresh();
    setSelected(new Set());
    setBusy(false);
  };

  const runDestroy = async () => {
    if (selected.size === 0 || busy) {
      return;
    }
    const n = selected.size;
    const confirmed = window.confirm(
      `确定永久删除选中的 ${n} 个归档 JSON？此操作不可撤销。`,
    );
    if (!confirmed) {
      return;
    }
    setBusy(true);
    setActionError(null);
    for (const id of selected) {
      await deleteConversationIpc(id);
    }
    await refresh();
    setSelected(new Set());
    setBusy(false);
  };

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

      {actionError ?
        <div className={styles.errorBanner} role="alert">
          {actionError}
        </div>
      : null}

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>占用</h2>
        <p className={styles.usage} data-testid="cache-total-bytes">
          {ipcReady && totalBytes !== null ?
            <>会话缓存总占用：<strong>{formatByteSize(totalBytes)}</strong></>
          : <span className={styles.muted}>无法统计（需 Electron 档 B IPC）</span>}
        </p>
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>存储位置（档 B）</h2>
        <p className={styles.muted}>
          每个任务一个 JSON 文件；<code>status: archived</code> 的条目仅在本页治理。
        </p>
        {storageRoot ?
          <p className={styles.pathBox} data-testid="conversations-cache-root">
            <code>{storageRoot}</code>
          </p>
        : (
          <p className={styles.muted} role="status">
            正在解析路径…
          </p>
        )}
      </section>

      <section className={styles.section}>
        <div className={styles.toolbar}>
          <h2 className={styles.sectionTitle}>归档列表</h2>
          <div className={styles.toolbarActions}>
            <button
              type="button"
              className={styles.secondaryBtn}
              disabled={!ipcReady || archived.length === 0 || busy}
              onClick={() => selectAll()}
            >
              全选
            </button>
            <button
              type="button"
              className={styles.secondaryBtn}
              disabled={selected.size === 0 || busy}
              onClick={() => clearSelection()}
            >
              取消选择
            </button>
            <button
              type="button"
              className={styles.primaryBtn}
              data-testid="cache-restore-selected"
              disabled={selected.size === 0 || busy || !ipcReady}
              onClick={() => void runRestore()}
            >
              恢复选中
            </button>
            <button
              type="button"
              className={styles.dangerBtn}
              data-testid="cache-destroy-selected"
              disabled={selected.size === 0 || busy || !ipcReady}
              onClick={() => void runDestroy()}
            >
              销毁选中
            </button>
          </div>
        </div>

        {!ipcReady ?
          <p className={styles.muted} role="status">
            当前环境无法访问本地会话目录（请用 Electron 壳，或 E2E 注入 mock IPC）。
          </p>
        : archived.length === 0 ?
          <p className={styles.muted} role="status" data-testid="cache-empty">
            暂无归档会话。在任务页「归档任务」或顶栏「归档当前会话」后会出现于此。
          </p>
        : (
          <ul className={styles.list} data-testid="archived-session-list">
            {archived.map((m) => (
              <li key={m.id} className={styles.listItem}>
                <label className={styles.rowLabel}>
                  <input
                    type="checkbox"
                    checked={selected.has(m.id)}
                    data-testid={`cache-select-${m.id}`}
                    onChange={() => toggleSelect(m.id)}
                  />
                  <span className={styles.itemBody}>
                    <span className={styles.itemTitle}>{m.title}</span>
                    <span className={styles.itemMeta}>
                      <code>{m.id}</code> · {m.byte_size.toLocaleString()} 字节 ·{" "}
                      {m.updated_at}
                    </span>
                  </span>
                </label>
              </li>
            ))}
          </ul>
        )}
        <p className={styles.muted}>
          <strong>恢复</strong>：改回 <code>idle</code> 并重新出现在顶栏标签。
          <strong>销毁</strong>：删除对应 JSON 文件。
        </p>
      </section>
    </div>
  );
}
