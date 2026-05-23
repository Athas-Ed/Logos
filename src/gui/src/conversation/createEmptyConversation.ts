import type { ChatMessage } from "../types/chat";

import {

  readStoredOperatingMode,

  readStoredPresentation,

} from "../preferences/chatPrefs";

import type { ConversationRecord } from "./types";

import type { ConversationState, TaskPhase } from "./storeTypes";



export function createEmptyConversationState(

  id: string,

  title = "新对话",

  skillId?: string,

  taskPhase?: TaskPhase,

): ConversationState {

  return {

    id,

    skillId,

    taskPhase,

    taskInputText: undefined,

    title,

    status: "idle",

    messages: [],

    citations: [],

    toolTraceLog: [],

    pipelineSteps: [],

    pipelineWarnings: [],

    pipelineWrittenPaths: [],

    promoteMessage: null,

    promoteBusy: false,

    operatingMode: readStoredOperatingMode() ?? "author",

    presentation: readStoredPresentation() ?? "work",

    streaming: false,

    queued: false,

    streamError: null,

    unread: false,

    hydrated: true,

    persistError: null,

  };

}



export function conversationStateFromRecord(

  record: ConversationRecord,

): ConversationState {

  const taskInputText =

    typeof record.task_input?.text === "string"

      ? record.task_input.text

      : undefined;

  return {

    id: record.id,

    skillId: record.skill_id,

    taskPhase: record.task_phase,

    taskInputText,

    title: record.title,

    status: record.status,

    messages: record.messages,

    citations: record.citations,

    toolTraceLog: record.tool_trace_log,

    pipelineSteps: [],

    pipelineWarnings: [],

    pipelineWrittenPaths: [],

    promoteMessage: null,

    promoteBusy: false,

    operatingMode: record.operating_mode,

    presentation: record.presentation,

    streaming: false,

    queued: false,

    streamError: null,

    unread: false,

    hydrated: true,

    persistError: null,

  };

}



export function messagesForApi(messages: ChatMessage[]): ChatMessage[] {

  const copy = [...messages];

  const last = copy[copy.length - 1];

  if (

    last?.role === "assistant" &&

    !last.content.trim() &&

    !(last.reasoning?.length ?? 0)

  ) {

    copy.pop();

  }

  return copy;

}


