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
  /** 任务页是否支持在同一会话内连续追问/换题 */
  qa_mode?: "normal" | "continuous";
  /** 是否在技能面板展示（默认展示） */
  panel_visible?: boolean;
  /** 自定义独立页面路由（不走通用 TaskPage/ChatPage） */
  customPage?: "review";
};

const LINT_UI = `粘贴或输入一段中文正文；助手将指出语病与表达问题（单轮，无工具调用）。
示例：他跑的很快，我们要加快进度。`;

const RETRIEVE_UI = `用自然语言提问；助手会先检索 KSFS，再按需 read_ksfs 读原文，最后作答。
执行阶段可在页面查看 ReAct 工具轨迹与检索引用。
**追问**：同一主题继续问 → 点「追问」。**换题**：不同主题 → 点「换题（新会话）」；不会自动归档当前标签，误点可切回原标签。
顶栏关闭标签 = 归档。示例：有罪者的大道怎么去藏骨堂？需要哪些步骤？`;

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

const IMPORT_UI = `将 Word 等来源的设定正文粘贴到下方；流水线会产出 JSON、校验并写入 workspace/setting_entry/ 草稿。
完成后请查看结果摘要与右侧阶段进度；确认无误后点击「晋升至 KSFS」。`;

export const PARADIGM_LABELS: Record<SkillCardMeta["paradigm"], string> = {
  dialogue: "dialogue（自然语言 SSE）",
  react: "react（ReAct + 工具轨迹）",
  plan: "plan（Phase A）",
  pipeline: "pipeline（设定导入）",
};

/** bootstrap 请求失败时的面板 Skill 回退列表（只含核心技能；新增技能只需写 manifest YAML）。 */
export const FALLBACK_PANEL_SKILLS: readonly SkillCardMeta[] = [
  {
    skill_id: "lint_zh",
    display_name: "中文语病检查",
    description: "对输入段落做语病与表达问题提示（单轮对话，无工具）。",
    ui_instructions: LINT_UI,
    paradigm: "dialogue",
    persistence_tier: "p2",
    turn_policy: "single",
    qa_mode: "normal",
    panel_visible: true,
  },
  {
    skill_id: "chat_inspire",
    display_name: "创作启发对话",
    description: "多轮启发式创作对话；非默认万能 Chat 入口。",
    ui_instructions: INSPIRE_UI,
    paradigm: "dialogue",
    persistence_tier: "p2",
    turn_policy: "multi",
    qa_mode: "normal",
    panel_visible: true,
  },
  {
    skill_id: "retrieve_qa",
    display_name: "检索问答",
    description: "react · retrieve + read_ksfs + ReAct",
    ui_instructions: RETRIEVE_UI,
    paradigm: "react",
    persistence_tier: "p2",
    turn_policy: "single",
    qa_mode: "continuous",
    panel_visible: true,
  },
  {
    skill_id: "import_setting",
    display_name: "导入设定",
    description: "粘贴设定 → 结构化 JSON → setting_entry 草稿（pipeline）。",
    ui_instructions: IMPORT_UI,
    paradigm: "pipeline",
    persistence_tier: "p0",
    turn_policy: "single",
    qa_mode: "normal",
    panel_visible: true,
  },
  {
    skill_id: "draft_review",
    display_name: "审核晋升",
    description: "审阅 pending_review 下草稿，晋升至 KSFS 或打回 LLM 重写。",
    ui_instructions: "审阅 pending_review 目录下的草稿文件。勾选文件后可以晋升至 KSFS 或打回要求 LLM 重写。",
    paradigm: "dialogue",
    persistence_tier: "p1",
    turn_policy: "single",
    qa_mode: "normal",
    panel_visible: true,
    customPage: "review",
  },
] as const;

/** @deprecated 使用 {@link getSkillMeta}（registry） */
export function getSkillCard(skillId: string): SkillCardMeta | undefined {
  return (
    FALLBACK_PANEL_SKILLS.find((c) => c.skill_id === skillId) ??
    LAB_SKILL_CARDS.find((c) => c.skill_id === skillId)
  );
}
