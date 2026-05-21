type Listener = () => void;

const perId = new Map<string, Set<Listener>>();
const globalListeners = new Set<Listener>();

export function subscribeConversation(
  id: string,
  listener: Listener,
): () => void {
  let set = perId.get(id);
  if (!set) {
    set = new Set();
    perId.set(id, set);
  }
  set.add(listener);
  return () => {
    set?.delete(listener);
    if (set && set.size === 0) {
      perId.delete(id);
    }
  };
}

export function subscribeAllConversations(listener: Listener): () => void {
  globalListeners.add(listener);
  return () => {
    globalListeners.delete(listener);
  };
}

export function notifyConversation(id: string): void {
  perId.get(id)?.forEach((fn) => fn());
}

export function notifyAllConversations(): void {
  globalListeners.forEach((fn) => fn());
}
