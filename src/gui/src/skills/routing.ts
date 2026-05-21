import type { ConversationState } from "../conversation/storeTypes";
import { getSkillCard } from "./catalog";
import { getSkillMeta } from "./registry";
/** 单任务向导（input → running → done），非多轮 Chat */
export function skillUsesTaskWizard(skillId: string): boolean {
  const card = getSkillCard(skillId);
  if (!card) {
    return true;
  }
  return card.turn_policy !== "multi";
  const card = getSkillMeta(skillId);

export function conversationNavPath(
  state: Pick<ConversationState, "id" | "labMode" | "skillId" | "taskPhase">,
): string {
  const { id, labMode, skillId, taskPhase } = state;
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
  const card = getSkillCard(state.skillId);
  return card?.turn_policy === "multi";
}

