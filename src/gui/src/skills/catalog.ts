/** bootstrap 不可用时的面板与页面回退元数据（须与 manifest 的 ui_instructions 保持同步）。 */

export type TurnPolicy = "single" | "multi";

export type SkillCardMeta = {
  skill_id: string;
  display_name: string;
  /** 技能面板卡片一句话摘要 */
  description: string;
  /** 任务页 / 对话页「技能说明」区块正文 */
  ui_instructions: string;
  paradigm: "dialogue" | "react" | "plan" | "pipeline";
  persistence_tier: "p0" | "p1" | "p2";
  turn_policy: TurnPolicy;
};

const LINT_UI = `粘贴或输入一段中文正文；助手将指出语病与表达问题（单轮，无工具调用）。
示例：他跑的很快，我们要加快进度。`;

const RETRIEVE_UI = `用自然语言提问；助手会先检索 KSFS，再按需 read_ksfs 读原文，最后作答。
执行阶段可在页面查看 ReAct 工具轨迹与检索引用。
示例：有罪者的大道怎么去藏骨堂？需要哪些步骤？`;

const INSPIRE_UI = `多轮创作启发对话：在下方输入创作相关问题，按 Enter 发送。
切换顶栏标签不会中断后台 SSE；超额请求将排队。`;

/** 范式试验台可选 Skill（含 react 样例） */
export const LAB_SKILL_CARDS: readonly SkillCardMeta[] = [
  {
    skill_id: "lint_zh",
    display_name: "中文语病检查",
    description: "dialogue · 语病检查 Prompt",
    ui_instructions: LINT_UI,
    paradigm: "dialogue",
    persistence_tier: "p2",
    turn_policy: "single",
  },
  {
    skill_id: "chat_inspire",
    display_name: "创作启发对话",
    description: "dialogue · 多轮启发 Prompt",
    ui_instructions: INSPIRE_UI,
    paradigm: "dialogue",
    persistence_tier: "p2",
    turn_policy: "multi",
  },
  {
    skill_id: "retrieve_qa",
    display_name: "检索问答",
    description: "react · retrieve + read_ksfs + ReAct",
    ui_instructions: RETRIEVE_UI,
    paradigm: "react",
    persistence_tier: "p2",
    turn_policy: "single",
  },
] as const;

export const PARADIGM_LABELS: Record<SkillCardMeta["paradigm"], string> = {
  dialogue: "dialogue（自然语言 SSE）",
  react: "react（ReAct + 工具轨迹）",
  plan: "plan（未实现）",
  pipeline: "pipeline（未实现）",
};

export const BUILTIN_SKILL_CARDS: readonly SkillCardMeta[] = [
  {
    skill_id: "lint_zh",
    display_name: "中文语病检查",
    description: "对输入段落做语病与表达问题提示（单轮对话，无工具）。",
    ui_instructions: LINT_UI,
    paradigm: "dialogue",
    persistence_tier: "p2",
    turn_policy: "single",
  },
  {
    skill_id: "chat_inspire",
    display_name: "创作启发对话",
    description: "多轮启发式创作对话；非默认万能 Chat 入口。",
    ui_instructions: INSPIRE_UI,
    paradigm: "dialogue",
    persistence_tier: "p2",
    turn_policy: "multi",
  },
] as const;

const RETRIEVE_QA_CARD = LAB_SKILL_CARDS.find((c) => c.skill_id === "retrieve_qa")!;

/** bootstrap 请求失败时的面板 Skill 列表 */
export const FALLBACK_PANEL_SKILLS: readonly SkillCardMeta[] = [
  ...BUILTIN_SKILL_CARDS,
  RETRIEVE_QA_CARD,
] as const;

/** @deprecated 使用 {@link getSkillMeta}（registry） */
export function getSkillCard(skillId: string): SkillCardMeta | undefined {
  return (
    BUILTIN_SKILL_CARDS.find((c) => c.skill_id === skillId) ??
    LAB_SKILL_CARDS.find((c) => c.skill_id === skillId)
  );
}
