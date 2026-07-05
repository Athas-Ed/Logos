import type {
  ChatMessage,
  CitationItem,
  PresentationMode,
} from "../types/chat";
import type { SkillCardMeta } from "../skills/catalog";
import type { ConversationStatus } from "./types";
import type { ReactStepLimitTurnMeta } from "./reactStepLimit";

/** 任务向导阶段（单任务 Skill；F5-06 落盘） */
export type TaskPhase = "input" | "running";

/** pipeline SSE ``pipeline_step`` 条目（内存态，F6-07） */
export type PipelineStepEntry = {
  stepId: string;
  status: string;
  summary: string;
};

export type ParadigmOverride = SkillCardMeta["paradigm"];

export type ConversationState = {
  id: string;
  /** Vite 范式试验台（/lab/:id） */
  labMode?: boolean;
  /** 产品 Skill 标识（F5-04 起内存态；F5-06 落盘 schema v2） */
  skillId?: string;
  /** 开发者：强制 PR 范式（覆盖 manifest；须后端允许） */
  paradigmOverride?: ParadigmOverride;
  /** 任务向导阶段；仅 skill 任务使用 */
  taskPhase?: TaskPhase;
  /** 第二步结构化输入（当前为纯文本） */
  taskInputText?: string;
  /** 多字段结构化输入（来自动态表单，优先级高于 taskInputText） */
  taskInputFields?: Record<string, unknown>;
  title: string;
  status: ConversationStatus;
  messages: ChatMessage[];
  citations: CitationItem[];
  toolTraceLog: string[];
  /** schema v3：按轮次 citations（归档全量） */
  citationTurns: CitationItem[][];
  /** schema v3：按轮次 ReAct 工具轨迹（归档全量） */
  toolTraceTurns: string[][];
  /** 本轮 ReAct 是否因步数触顶结束 */
  reactHitStepLimit: boolean;
  /** 按轮 ReAct 步数触顶元数据（归档；ReAct 范式） */
  reactStepLimitTurns: ReactStepLimitTurnMeta[];
  pipelineSteps: PipelineStepEntry[];
  pipelineWarnings: string[];
  /** pipeline ``done`` 事件中的 ``written_paths``（F6-08 晋升用） */
  pipelineWrittenPaths: string[];
  /** 晋升 KSFS 结果摘要（Task 页展示） */
  promoteMessage: string | null;
  promoteBusy: boolean;
  operatingMode: string;
  presentation: PresentationMode;
  streaming: boolean;
  /** 页面类型：review = 审核晋升独立页面，缺省则走 chat/task 路由 */
  pageType?: "review";
  /** 已提交发送但等待 SSE 槽位 */
  queued: boolean;
  streamError: string | null;
  unread: boolean;
  hydrated: boolean;
  persistError: string | null;
};
