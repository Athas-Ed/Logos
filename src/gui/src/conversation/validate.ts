const ID_PATTERN = /^[a-zA-Z0-9_-]{1,64}$/;

export function isValidConversationId(raw: string | undefined): raw is string {
  if (!raw) {
    return false;
  }
  const id = raw.trim();
  if (id === "." || id === "..") {
    return false;
  }
  return ID_PATTERN.test(id);
}
