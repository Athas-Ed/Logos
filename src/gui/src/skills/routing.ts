import type { ConversationState } from "../conversation/storeTypes";
import { getSkillMeta } from "./registry";
/** 单任务向导（input → running → done），非多轮 Chat */
export function skillUsesTaskWizard(skillId: string): boolean {
  const card = getSkillMeta(skillId);
  if (!card) {
    return true;
  }
  return card.turn_policy !== "multi";
}

export function conversationNavPath(
  state: Pick<ConversationState, "id" | "labMode" | "skillId" | "taskPhase" | "pageType">,
): string {
  const { id, labMode, skillId, taskPhase, pageType } = state;
  if (pageType === "review") {
    return `/review/${id}`;
  }
  if (labMode) {
    return `/lab/${id}`;
  }
  if (skillId && taskPhase !== undefined) {
    return `/task/${id}`;
  }
  return `/chat/${id}`;
}

export function isInspireChatState(
  state: Pick<ConversationState, "skillId" | "taskPhase" | "labMode">,
): boolean {
  if (state.labMode || state.taskPhase !== undefined) {
    return false;
  }
  if (!state.skillId) {
    return false;
  }
  const card = getSkillMeta(state.skillId);
  return card?.turn_policy === "multi";
}
