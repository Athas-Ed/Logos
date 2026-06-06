import type { SkillCardMeta } from "./catalog";

const byId = new Map<string, SkillCardMeta>();

/** 用 bootstrap 数据填充注册表（完全替换）。 */
export function hydrateSkillRegistry(cards: readonly SkillCardMeta[]): void {
  byId.clear();
  for (const c of cards) {
    byId.set(c.skill_id, c);
  }
}

/** 当前 Skill 元数据（bootstrap 优先，无回退避免数据漂移）。 */
export function getSkillMeta(skillId: string): SkillCardMeta | undefined {
  return byId.get(skillId);
}
