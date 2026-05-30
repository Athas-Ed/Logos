/** 档 B 会话 JSON 变更时通知（如归档写盘完成），供 `/cache` 等页刷新列表。 */

const EVENT = "logos:conversations-storage-changed";

export function notifyConversationsStorageChanged(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.dispatchEvent(new CustomEvent(EVENT));
}

export function subscribeConversationsStorageChanged(
  listener: () => void,
): () => void {
  if (typeof window === "undefined") {
    return () => {};
  }
  const handler = () => listener();
  window.addEventListener(EVENT, handler);
  return () => window.removeEventListener(EVENT, handler);
}
