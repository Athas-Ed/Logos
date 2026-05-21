import type {

  ChatMessage,

  CitationItem,

  OperatingMode,

  PresentationMode,

} from "../types/chat";

import type { TaskPhase } from "./storeTypes";



/** 现行档 B 版本（F5-06） */

export const CONVERSATION_SCHEMA_VERSION = 2 as const;



/** 第四阶段遗留；读入时迁移为 v2 */

export const LEGACY_CONVERSATION_SCHEMA_VERSION = 1 as const;



/**

 * v1 档 B 无 `skill_id` 时的默认 Skill（与 API 缺省回退一致）。

 * 旧任务若已在内存绑定 Skill，下次写盘会以 v2 字段覆盖。

 */

export const LEGACY_V1_DEFAULT_SKILL_ID = "chat_inspire";



export type ConversationStatus = "idle" | "archived";



/** 落盘 `task_input`（结构依 Skill；当前任务向导仅用 `text`） */

export type TaskInputRecord = Record<string, unknown>;



/** 档 B 单会话 JSON（`userData/conversations/<id>.json`） */

export type ConversationRecord = {

  schema_version: typeof CONVERSATION_SCHEMA_VERSION;

  id: string;

  title: string;

  status: ConversationStatus;

  updated_at: string;

  messages: ChatMessage[];

  citations: CitationItem[];

  tool_trace_log: string[];

  operating_mode: OperatingMode;

  presentation: PresentationMode;

  /** 本任务绑定的产品 Skill（v2 必填） */

  skill_id: string;

  /** 任务向导阶段；无任务语义时可省略 */

  task_phase?: TaskPhase;

  /** 第二步结构化输入 */

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


