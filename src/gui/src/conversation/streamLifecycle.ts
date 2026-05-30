import type { ChatMessage } from "../types/chat";
import type { ConversationState } from "./storeTypes";

/** 去掉末尾未完成的 assistant 占位（流式中断/归档时常见）。 */
export function stripTrailingEmptyAssistant(
  messages: ChatMessage[],
): ChatMessage[] {
  const copy = [...messages];
  while (copy.length > 0) {
    const last = copy[copy.length - 1]!;
    if (
      last.role === "assistant" &&
      !last.content.trim() &&
      !(last.reasoning?.length ?? 0)
    ) {
      copy.pop();
    } else {
      break;
    }
  }
  return copy;
}

/** 归档、恢复或中断后统一内存态，避免 streaming/queued 残留与空占位。 */
export function normalizeInterruptedConversationState(
  state: ConversationState,
): ConversationState {
  const messages = stripTrailingEmptyAssistant(state.messages);
  let taskPhase = state.taskPhase;
  if (state.skillId && taskPhase === "running") {
    taskPhase = "input";
  }
  return {
    ...state,
    messages,
    taskPhase,
    streaming: false,
    queued: false,
    streamError: state.streamError === "已中断" ? null : state.streamError,
    pipelineSteps: [],
    pipelineWarnings: [],
  };
}
