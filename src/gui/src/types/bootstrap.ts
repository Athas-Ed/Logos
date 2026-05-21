import type { SkillCardMeta } from "../skills/catalog";

import { FALLBACK_PANEL_SKILLS } from "../skills/catalog";

/** 与 `GET /api/v1/bootstrap` 的 `ui` 段对齐（`config/ui.*`） */
export type BootstrapUi = {
  SSE_maxNum: number;
  cache_warn_bytes: number;
};

export const BOOTSTRAP_UI_DEFAULTS: BootstrapUi = {
  SSE_maxNum: 3,
  cache_warn_bytes: 524288000,
};

/** F5-08：`bootstrap.skills[]` 项 */
export type BootstrapSkill = {
  skill_id: string;
  display_name: string;
  description: string;
  ui_instructions?: string;
  persistence_tier: SkillCardMeta["persistence_tier"];
  paradigm: SkillCardMeta["paradigm"];
};

export function resolveBootstrapUi(
  raw: Partial<BootstrapUi> | null | undefined,
): BootstrapUi {
  const sse = raw?.SSE_maxNum;
  const cache = raw?.cache_warn_bytes;
  return {
    SSE_maxNum:
      typeof sse === "number" && Number.isFinite(sse) && sse >= 1
        ? Math.floor(sse)
        : BOOTSTRAP_UI_DEFAULTS.SSE_maxNum,
    cache_warn_bytes:
      typeof cache === "number" && Number.isFinite(cache) && cache >= 0
        ? Math.floor(cache)
        : BOOTSTRAP_UI_DEFAULTS.cache_warn_bytes,
  };
}

function isBootstrapSkill(raw: unknown): raw is BootstrapSkill {
  if (!raw || typeof raw !== "object") {
    return false;
  }
  const s = raw as BootstrapSkill;
  return (
    typeof s.skill_id === "string" &&
    s.skill_id.trim() !== "" &&
    typeof s.display_name === "string" &&
    typeof s.description === "string" &&
    (s.persistence_tier === "p0" ||
      s.persistence_tier === "p1" ||
      s.persistence_tier === "p2") &&
    (s.paradigm === "dialogue" ||
      s.paradigm === "react" ||
      s.paradigm === "plan" ||
      s.paradigm === "pipeline")
  );
}

/** 将 bootstrap.skills 转为面板/页面元数据（补全 `turn_policy`） */
export function panelSkillsFromBootstrap(
  raw: unknown[] | null | undefined,
): SkillCardMeta[] {
  if (!Array.isArray(raw)) {
    return [];
  }
  const out: SkillCardMeta[] = [];
  for (const item of raw) {
    if (!isBootstrapSkill(item)) {
      continue;
    }
    const fallback = FALLBACK_PANEL_SKILLS.find((c) => c.skill_id === item.skill_id);
    const ui =
      typeof item.ui_instructions === "string" && item.ui_instructions.trim()
        ? item.ui_instructions.trim()
        : (fallback?.ui_instructions ?? "");
    out.push({
      skill_id: item.skill_id,
      display_name: item.display_name,
      description: item.description,
      ui_instructions: ui,
      persistence_tier: item.persistence_tier,
      paradigm: item.paradigm,
      turn_policy: fallback?.turn_policy ?? "single",
    });
  }
  return out;
}
