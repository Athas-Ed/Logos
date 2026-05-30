import { buildConversationRecord } from "./record";
import { writeConversationIpc, isConversationIpcAvailable } from "./ipc";
import { isSessionDismissed } from "./sessionDismissed";
import type { ConversationState } from "./storeTypes";

const timers = new Map<string, number>();
const writeGeneration = new Map<string, number>();
const SAVE_DEBOUNCE_MS = 600;

type StateGetter = (id: string) => ConversationState | undefined;
type PersistGuard = (id: string, state: ConversationState) => boolean;

let getStateForPersist: StateGetter = () => undefined;
let persistGuard: PersistGuard = () => true;

export function bindConversationPersistSource(getter: StateGetter): void {
  getStateForPersist = getter;
}

export function bindConversationPersistGuard(guard: PersistGuard): void {
  persistGuard = guard;
}

function recordFromState(state: ConversationState) {
  return buildConversationRecord({
    id: state.id,
    messages: state.messages,
    citationTurns: state.citationTurns,
    toolTraceTurns: state.toolTraceTurns,
    reactStepLimitTurns: state.reactStepLimitTurns,
    operatingMode: state.operatingMode,
    presentation: state.presentation,
    status: state.status,
    title: state.title,
    skillId: state.skillId,
    taskPhase: state.taskPhase,
    taskInputText: state.taskInputText,
  });
}

function latestPersistableState(
  id: string,
  fallback?: ConversationState,
): ConversationState | undefined {
  const state = getStateForPersist(id) ?? fallback;
  if (!state) {
    return undefined;
  }
  if (state.status === "archived") {
    return undefined;
  }
  if (isSessionDismissed(id)) {
    return undefined;
  }
  if (!persistGuard(id, state)) {
    return undefined;
  }
  return state;
}

function bumpWriteGeneration(id: string): number {
  const next = (writeGeneration.get(id) ?? 0) + 1;
  writeGeneration.set(id, next);
  return next;
}

/** 作废该会话所有尚未落盘的防抖写盘（如归档开始时调用）。 */
export function invalidateConversationPersist(id: string): void {
  bumpWriteGeneration(id);
}

function scheduleWrite(id: string, generation: number, delayMs: number): void {
  const prev = timers.get(id);
  if (prev !== undefined) {
    globalThis.clearTimeout(prev);
  }

  const t = globalThis.setTimeout(() => {
    timers.delete(id);
    if (writeGeneration.get(id) !== generation) {
      return;
    }
    const state = latestPersistableState(id);
    if (!state || !isConversationIpcAvailable()) {
      return;
    }
    void writeConversationIpc(id, recordFromState(state));
  }, delayMs);

  timers.set(id, t);
}

export function scheduleConversationPersist(
  id: string,
  state: ConversationState,
): void {
  if (!isConversationIpcAvailable() || !latestPersistableState(id, state)) {
    return;
  }
  const generation = bumpWriteGeneration(id);
  scheduleWrite(
    id,
    generation,
    state.streaming ? SAVE_DEBOUNCE_MS * 2 : SAVE_DEBOUNCE_MS,
  );
}

export function flushConversationPersist(
  id: string,
  state: ConversationState,
): void {
  const prev = timers.get(id);
  if (prev !== undefined) {
    globalThis.clearTimeout(prev);
    timers.delete(id);
  }

  const latest = latestPersistableState(id, state);
  if (!latest || !isConversationIpcAvailable()) {
    return;
  }

  const generation = bumpWriteGeneration(id);
  queueMicrotask(() => {
    if (writeGeneration.get(id) !== generation) {
      return;
    }
    const current = latestPersistableState(id, latest);
    if (!current) {
      return;
    }
    void writeConversationIpc(id, recordFromState(current));
  });
}

export function cancelConversationPersist(id: string): void {
  const prev = timers.get(id);
  if (prev !== undefined) {
    globalThis.clearTimeout(prev);
    timers.delete(id);
  }
  invalidateConversationPersist(id);
}
