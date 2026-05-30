import type {
  ChatMessage,
  CitationItem,
  OperatingMode,
  PresentationMode,
} from "../types/chat";
import type { TaskPhase } from "./storeTypes";

/** 现行档 B 版本（连续问答 citation_turns） */
export const CONVERSATION_SCHEMA_VERSION = 3 as const;

/** F5-06 schema v2 */
export const LEGACY_CONVERSATION_SCHEMA_VERSION_V2 = 2 as const;

/** 第四阶段遗留；读入时迁移 */
export const LEGACY_CONVERSATION_SCHEMA_VERSION = 1 as const;

export const LEGACY_V1_DEFAULT_SKILL_ID = "chat_inspire";

export type ConversationStatus = "idle" | "archived";

export type TaskInputRecord = Record<string, unknown>;

/** 档 B 单会话 JSON */
export type ConversationRecord = {
  schema_version: typeof CONVERSATION_SCHEMA_VERSION;
  id: string;
  title: string;
  status: ConversationStatus;
  updated_at: string;
  messages: ChatMessage[];
  citation_turns: CitationItem[][];
  tool_trace_turns: string[][];
  /** ReAct 范式：按轮步数触顶（可选；schema v3+） */
  react_step_limit_turns?: { hit: boolean }[];
  operating_mode: OperatingMode;
  presentation: PresentationMode;
  skill_id: string;
  task_phase?: TaskPhase;
  task_input?: TaskInputRecord;
};

export type ConversationMeta = {
  id: string;
  title: string;
  status: ConversationStatus;
  updated_at: string;
  byte_size: number;
};

export type ConversationReadResult =
  | { ok: true; record: ConversationRecord }
  | { ok: false; error: string; corrupt: boolean };

export type ConversationIpcResult = { ok: boolean; error?: string };
