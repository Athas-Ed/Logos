/** Manifest YAML 是技能元数据的唯一数据源。bootstrap API 将其送达前端。
 *  离线回退只保留最低标识（skill_id + display_name），无行为字段可漂移。 */

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

export const PARADIGM_LABELS: Record<SkillCardMeta["paradigm"], string> = {
  dialogue: "dialogue（自然语言 SSE）",
  react: "react（ReAct + 工具轨迹）",
  plan: "plan（Phase A）",
  pipeline: "HITL Plan-and-Execute（设定导入流水线）",
};

/* ==============================
 *  离线回退：bootstrap 不可用时最低标识
 *  ==============================
 *  仅含 skill_id + display_name，无行为字段。
 *  新增技能只需写 manifest YAML，bootstrap 在线时自动送达。
 *  如需在离线时可见，在此追加 `{ skill_id, display_name }`。
 */
export const OFFLINE_SKILL_NAMES: readonly Pick<SkillCardMeta, "skill_id" | "display_name">[] = [
  { skill_id: "lint_zh", display_name: "中文语病检查" },
  { skill_id: "chat_inspire", display_name: "创作启发对话" },
  { skill_id: "retrieve_qa", display_name: "检索问答" },
  { skill_id: "setting_write", display_name: "设定撰写" },
  { skill_id: "outline_plan", display_name: "大纲规划" },
  { skill_id: "import_setting", display_name: "导入设定" },
  { skill_id: "draft_review", display_name: "审核晋升" },
];

/** 离线回退：根据 skill_id 找 display_name */
export function getOfflineSkillName(skillId: string): string | undefined {
  return OFFLINE_SKILL_NAMES.find((c) => c.skill_id === skillId)?.display_name;
}
