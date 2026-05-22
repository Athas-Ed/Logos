const STORAGE_KEY = "logos.session.dismissedTabIds";

function storageAvailable(): boolean {
  try {
    return typeof localStorage !== "undefined";
  } catch {
    return false;
  }
}

function readSet(): Set<string> {
  if (!storageAvailable()) {
    return new Set();
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return new Set();
    }
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return new Set();
    }
    return new Set(parsed.filter((x): x is string => typeof x === "string"));
  } catch {
    return new Set();
  }
}

function writeSet(ids: Set<string>): void {
  if (!storageAvailable()) {
    return;
  }
  if (ids.size === 0) {
    localStorage.removeItem(STORAGE_KEY);
    return;
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...ids]));
}

export function markSessionDismissed(conversationId: string): void {
  const next = readSet();
  next.add(conversationId);
  writeSet(next);
}

export function clearSessionDismissed(conversationId: string): void {
  const next = readSet();
  if (!next.delete(conversationId)) {
    return;
  }
  writeSet(next);
}

export function isSessionDismissed(conversationId: string): boolean {
  return readSet().has(conversationId);
}
