import { buildConversationRecord } from "./record";

import { writeConversationIpc, isConversationIpcAvailable } from "./ipc";

import type { ConversationState } from "./storeTypes";



const timers = new Map<string, number>();

const SAVE_DEBOUNCE_MS = 600;



function recordFromState(state: ConversationState) {

  return buildConversationRecord({

    id: state.id,

    messages: state.messages,

    citations: state.citations,

    toolTraceLog: state.toolTraceLog,

    operatingMode: state.operatingMode,

    presentation: state.presentation,

    status: state.status,

    title: state.title,

    skillId: state.skillId,

    taskPhase: state.taskPhase,

    taskInputText: state.taskInputText,

  });

}



export function scheduleConversationPersist(

  id: string,

  state: ConversationState,

): void {

  if (!isConversationIpcAvailable() || state.status === "archived") {

    return;

  }

  const prev = timers.get(id);

  if (prev !== undefined) {

    window.clearTimeout(prev);

  }

  const t = window.setTimeout(() => {

    timers.delete(id);

    void writeConversationIpc(id, recordFromState(state));

  }, state.streaming ? SAVE_DEBOUNCE_MS * 2 : SAVE_DEBOUNCE_MS);

  timers.set(id, t);

}



export function flushConversationPersist(

  id: string,

  state: ConversationState,

): void {

  const prev = timers.get(id);

  if (prev !== undefined) {

    window.clearTimeout(prev);

    timers.delete(id);

  }

  if (!isConversationIpcAvailable()) {

    return;

  }

  void writeConversationIpc(id, recordFromState(state));

}

export function cancelConversationPersist(id: string): void {

  const prev = timers.get(id);

  if (prev !== undefined) {

    window.clearTimeout(prev);

    timers.delete(id);

  }

}


