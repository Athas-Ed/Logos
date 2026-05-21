import type {
  ChatMessage,
  CitationItem,
  OperatingMode,
  PresentationMode,
} from "../types/chat";
import type { SkillCardMeta } from "../skills/catalog";
import type { ConversationStatus } from "./types";

/** 任务向导阶段（单任务 Skill；F5-06 落盘） */
export type TaskPhase = "input" | "running" | "done";

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
  title: string;
  status: ConversationStatus;
  messages: ChatMessage[];
  citations: CitationItem[];
  toolTraceLog: string[];
  operatingMode: OperatingMode;
  presentation: PresentationMode;
  streaming: boolean;
  /** 已提交发送但等待 SSE 槽位 */
  queued: boolean;
  streamError: string | null;
  unread: boolean;
  hydrated: boolean;
  persistError: string | null;
};
