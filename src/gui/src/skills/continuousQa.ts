import { getSkillMeta } from "./registry";

/** 判断产品 Skill 是否支持任务页内的连续问答（追问/换题）。
 * 由 manifest 的 `qa_mode` 字段驱动——新增技能只需在 YAML 写 `qa_mode: continuous`。 */
export function skillSupportsContinuousQa(skillId: string | undefined): boolean {
  if (!skillId) return false;
  return getSkillMeta(skillId)?.qa_mode === "continuous";
}
