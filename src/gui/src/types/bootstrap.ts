import type { SkillCardMeta } from "../skills/catalog";



import { FALLBACK_PANEL_SKILLS } from "../skills/catalog";



/** 与 `GET /api/v1/bootstrap` 的 `ui` 段对齐（`config/ui.*`） */

export type BootstrapUi = {

  SSE_maxNum: number;

  cache_warn_bytes: number;

  max_history_full_text: number;

  react_max_steps: number;

  react_max_qa_steps: number;

};



export const BOOTSTRAP_UI_DEFAULTS: BootstrapUi = {

  SSE_maxNum: 3,

  cache_warn_bytes: 524288000,

  max_history_full_text: 5,

  react_max_steps: 16,

  react_max_qa_steps: 20,

};



/** F5-08：`bootstrap.skills[]` 项 */

export type BootstrapSkill = {

  skill_id: string;

  display_name: string;

  description: string;

  ui_instructions?: string;

  persistence_tier: SkillCardMeta["persistence_tier"];

  paradigm: SkillCardMeta["paradigm"];

  turn_policy?: SkillCardMeta["turn_policy"];

  qa_mode?: SkillCardMeta["qa_mode"];

  panel_visible?: SkillCardMeta["panel_visible"];

};



export function resolveBootstrapUi(

  raw: Partial<BootstrapUi> | null | undefined,

): BootstrapUi {

  const sse = raw?.SSE_maxNum;

  const cache = raw?.cache_warn_bytes;

  const hist = raw?.max_history_full_text;

  const rSteps = raw?.react_max_steps;

  const rQa = raw?.react_max_qa_steps;

  return {

    SSE_maxNum:

      typeof sse === "number" && Number.isFinite(sse) && sse >= 1

        ? Math.floor(sse)

        : BOOTSTRAP_UI_DEFAULTS.SSE_maxNum,

    cache_warn_bytes:

      typeof cache === "number" && Number.isFinite(cache) && cache >= 0

        ? Math.floor(cache)

        : BOOTSTRAP_UI_DEFAULTS.cache_warn_bytes,

    max_history_full_text:

      typeof hist === "number" && Number.isFinite(hist) && hist >= 1

        ? Math.floor(hist)

        : BOOTSTRAP_UI_DEFAULTS.max_history_full_text,

    react_max_steps:

      typeof rSteps === "number" && Number.isFinite(rSteps) && rSteps >= 1

        ? Math.floor(rSteps)

        : BOOTSTRAP_UI_DEFAULTS.react_max_steps,

    react_max_qa_steps:

      typeof rQa === "number" && Number.isFinite(rQa) && rQa >= 1

        ? Math.floor(rQa)

        : BOOTSTRAP_UI_DEFAULTS.react_max_qa_steps,

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



/** 将 bootstrap.skills 转为面板/页面元数据 */

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

    const safe = item as BootstrapSkill;

    const fallback = FALLBACK_PANEL_SKILLS.find((c) => c.skill_id === safe.skill_id);

    const ui =

      typeof safe.ui_instructions === "string" && safe.ui_instructions.trim()

        ? safe.ui_instructions.trim()

        : (fallback?.ui_instructions ?? "");

    out.push({

      skill_id: safe.skill_id,

      display_name: safe.display_name,

      description: safe.description,

      ui_instructions: ui,

      persistence_tier: safe.persistence_tier,

      paradigm: safe.paradigm,

      turn_policy: safe.turn_policy ?? fallback?.turn_policy ?? "single",

      qa_mode: safe.qa_mode ?? fallback?.qa_mode ?? "normal",

      panel_visible: safe.panel_visible ?? fallback?.panel_visible ?? true,

    });

  }

  return out;

}

