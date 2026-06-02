/** HashRouter 下当前应用内路径（不含 `#`）。 */
export function currentAppPath(): string {
  const hash = window.location.hash.replace(/^#/, "");
  return hash || window.location.pathname || "/";
}

export function isConversationRoute(
  path: string,
  conversationId: string,
): boolean {
  return (
    path === `/chat/${conversationId}` ||
    path === `/task/${conversationId}` ||
    path === `/lab/${conversationId}` ||
    path === `/review/${conversationId}` ||
    path.startsWith(`/review/${conversationId}?`)
  );
}
