import type { ChatMessage, CitationItem } from "../types/chat";
import { readStoredPresentation } from "../preferences/chatPrefs";
import type { ReactStepLimitTurnMeta } from "./reactStepLimit";
import { inferReactStepLimitTurns } from "./reactStepLimit";
import type { ConversationRecord } from "./types";
import type { ConversationState, TaskPhase } from "./storeTypes";

export function currentTurnCitations(state: {
  citationTurns: CitationItem[][];
}): CitationItem[] {
  const turns = state.citationTurns;
  return turns.length > 0 ? turns[turns.length - 1]! : [];
}

export function currentTurnToolTrace(state: {
  toolTraceTurns: string[][];
}): string[] {
  const turns = state.toolTraceTurns;
  return turns.length > 0 ? turns[turns.length - 1]! : [];
}

export function createEmptyReviewState(id: string, _scope?: string): ConversationState {
  return {
    ...createEmptyConversationState(id, "审核晋升", "draft_review"),
    pageType: "review" as const,
    status: "idle" as const,
    persistError: null,
  };
}

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
    citationTurns: [],
    toolTraceTurns: [],
    reactHitStepLimit: false,
    reactStepLimitTurns: [],
    pipelineSteps: [],
    pipelineWarnings: [],
    pipelineWrittenPaths: [],
    promoteMessage: null,
    promoteBusy: false,
    operatingMode: "author",
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
  const citationTurns = record.citation_turns ?? [];
  const toolTraceTurns = record.tool_trace_turns ?? [];
  const reactStepLimitTurns: ReactStepLimitTurnMeta[] =
    record.react_step_limit_turns?.map((t) => ({
      hit: Boolean(t.hit),
    })) ?? inferReactStepLimitTurns(record.messages);
  const lastLimit = reactStepLimitTurns[reactStepLimitTurns.length - 1];
  return {
    id: record.id,
    skillId: record.skill_id,
    taskPhase: record.task_phase,
    taskInputText,
    title: record.title,
    status: record.status,
    messages: record.messages,
    citationTurns,
    toolTraceTurns,
    citations: currentTurnCitations({ citationTurns }),
    toolTraceLog: currentTurnToolTrace({ toolTraceTurns }),
    reactHitStepLimit: Boolean(lastLimit?.hit),
    reactStepLimitTurns,
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
