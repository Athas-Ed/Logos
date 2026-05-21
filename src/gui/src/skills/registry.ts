import { FALLBACK_PANEL_SKILLS, type SkillCardMeta } from "./catalog";

const byId = new Map<string, SkillCardMeta>();

/** 启动时用回退列表填充，避免 bootstrap 到达前 getSkillMeta 为空。 */
export function initSkillRegistryFallback(): void {
  hydrateSkillRegistry([...FALLBACK_PANEL_SKILLS]);
}

export function hydrateSkillRegistry(cards: readonly SkillCardMeta[]): void {
  byId.clear();
  for (const c of cards) {
    byId.set(c.skill_id, c);
  }
}

/** 当前 Skill 元数据（bootstrap 优先，否则 catalog 回退）。 */
export function getSkillMeta(skillId: string): SkillCardMeta | undefined {
  return byId.get(skillId) ?? FALLBACK_PANEL_SKILLS.find((c) => c.skill_id === skillId);
}

initSkillRegistryFallback();
