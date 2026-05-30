/** 支持任务页连续问答（追问/换题）的产品 Skill */
export const CONTINUOUS_QA_SKILL_IDS = new Set(["retrieve_qa"]);

export function skillSupportsContinuousQa(skillId: string | undefined): boolean {
  return Boolean(skillId && CONTINUOUS_QA_SKILL_IDS.has(skillId));
}
