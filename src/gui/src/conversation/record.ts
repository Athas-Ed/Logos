import type {

  ChatMessage,

  CitationItem,

  OperatingMode,

  PresentationMode,

} from "../types/chat";

import type { TaskPhase } from "./storeTypes";

import {

  CONVERSATION_SCHEMA_VERSION,

  LEGACY_CONVERSATION_SCHEMA_VERSION,

  LEGACY_V1_DEFAULT_SKILL_ID,

  type ConversationRecord,

  type ConversationStatus,

  type TaskInputRecord,

} from "./types";



export function deriveConversationTitle(messages: ChatMessage[]): string {

  const firstUser = messages.find((m) => m.role === "user" && m.content.trim());

  if (!firstUser) {

    return "新对话";

  }

  const t = firstUser.content.trim().replace(/\s+/g, " ");

  if (t.length <= 40) {

    return t;

  }

  return `${t.slice(0, 40)}…`;

}



function taskInputFromText(text: string | undefined): TaskInputRecord | undefined {

  const trimmed = text?.trim();

  if (!trimmed) {

    return undefined;

  }

  return { text: trimmed };

}



export function buildConversationRecord(args: {

  id: string;

  messages: ChatMessage[];

  citations: CitationItem[];

  toolTraceLog: string[];

  operatingMode: OperatingMode;

  presentation: PresentationMode;

  status?: ConversationStatus;

  title?: string;

  skillId?: string;

  taskPhase?: TaskPhase;

  taskInputText?: string;

}): ConversationRecord {

  const now = new Date().toISOString();

  const skill_id = args.skillId?.trim() || LEGACY_V1_DEFAULT_SKILL_ID;

  const task_input = taskInputFromText(args.taskInputText);

  const record: ConversationRecord = {

    schema_version: CONVERSATION_SCHEMA_VERSION,

    id: args.id,

    title: args.title ?? deriveConversationTitle(args.messages),

    status: args.status ?? "idle",

    updated_at: now,

    messages: args.messages,

    citations: args.citations,

    tool_trace_log: args.toolTraceLog,

    operating_mode: args.operatingMode,

    presentation: args.presentation,

    skill_id,

  };

  if (args.taskPhase) {

    record.task_phase = args.taskPhase;

  }

  if (task_input) {

    record.task_input = task_input;

  }

  return record;

}



function isChatMessage(raw: unknown): raw is ChatMessage {

  if (!raw || typeof raw !== "object") {

    return false;

  }

  const m = raw as ChatMessage;

  return (

    (m.role === "user" || m.role === "assistant" || m.role === "system") &&

    typeof m.content === "string" &&

    (m.reasoning === undefined || typeof m.reasoning === "string")

  );

}



function isCitation(raw: unknown): raw is CitationItem {

  if (!raw || typeof raw !== "object") {

    return false;

  }

  const c = raw as CitationItem;

  return (

    typeof c.path === "string" &&

    typeof c.snippet === "string" &&

    typeof c.score === "number"

  );

}



function isTaskPhase(raw: unknown): raw is TaskPhase {

  return raw === "input" || raw === "running" || raw === "done";

}



function isPlainObject(raw: unknown): raw is TaskInputRecord {

  return Boolean(raw) && typeof raw === "object" && !Array.isArray(raw);

}



function parseCoreFields(

  id: string,

  raw: Record<string, unknown>,

): Omit<

  ConversationRecord,

  "schema_version" | "skill_id" | "task_phase" | "task_input"

> | null {

  if (raw.id !== id) {

    return null;

  }

  const status = raw.status;

  if (status !== "idle" && status !== "archived") {

    return null;

  }

  if (!Array.isArray(raw.messages) || !raw.messages.every(isChatMessage)) {

    return null;

  }

  const citations = Array.isArray(raw.citations) ? raw.citations : [];

  if (!citations.every(isCitation)) {

    return null;

  }

  const toolLog = Array.isArray(raw.tool_trace_log)

    ? raw.tool_trace_log.filter((x): x is string => typeof x === "string")

    : [];

  const op = raw.operating_mode;

  const operating_mode: OperatingMode =

    op === "screenwriter" ? "screenwriter" : "author";

  const pres = raw.presentation;

  const presentation: PresentationMode =

    pres === "developer" ? "developer" : "work";

  const title =

    typeof raw.title === "string" && raw.title.trim() ? raw.title.trim() : id;

  const updated_at =

    typeof raw.updated_at === "string" && raw.updated_at.trim()

      ? raw.updated_at.trim()

      : new Date(0).toISOString();

  return {

    id,

    title,

    status,

    updated_at,

    messages: raw.messages as ChatMessage[],

    citations: citations as CitationItem[],

    tool_trace_log: toolLog,

    operating_mode,

    presentation,

  };

}



/** v1 → v2：补 `skill_id`（定案默认 `chat_inspire`） */

export function migrateConversationV1ToV2(

  core: Omit<

    ConversationRecord,

    "schema_version" | "skill_id" | "task_phase" | "task_input"

  >,

  raw: Record<string, unknown>,

): ConversationRecord {

  const skillRaw = raw.skill_id;

  const skill_id =

    typeof skillRaw === "string" && skillRaw.trim()

      ? skillRaw.trim()

      : LEGACY_V1_DEFAULT_SKILL_ID;

  const record: ConversationRecord = {

    schema_version: CONVERSATION_SCHEMA_VERSION,

    ...core,

    skill_id,

  };

  const phase = raw.task_phase;

  if (isTaskPhase(phase)) {

    record.task_phase = phase;

  }

  const taskIn = raw.task_input;

  if (isPlainObject(taskIn)) {

    record.task_input = taskIn;

  } else if (

    typeof raw.task_input_text === "string" &&

    raw.task_input_text.trim()

  ) {

    record.task_input = { text: raw.task_input_text.trim() };

  }

  return record;

}



export function parseConversationRecord(

  id: string,

  raw: Record<string, unknown>,

): ConversationRecord | null {

  const version = raw.schema_version;

  if (

    version !== CONVERSATION_SCHEMA_VERSION &&

    version !== LEGACY_CONVERSATION_SCHEMA_VERSION

  ) {

    return null;

  }

  const core = parseCoreFields(id, raw);

  if (!core) {

    return null;

  }

  if (version === LEGACY_CONVERSATION_SCHEMA_VERSION) {

    return migrateConversationV1ToV2(core, raw);

  }

  const skillRaw = raw.skill_id;

  if (typeof skillRaw !== "string" || !skillRaw.trim()) {

    return null;

  }

  const record: ConversationRecord = {

    schema_version: CONVERSATION_SCHEMA_VERSION,

    ...core,

    skill_id: skillRaw.trim(),

  };

  const phase = raw.task_phase;

  if (isTaskPhase(phase)) {

    record.task_phase = phase;

  }

  const taskIn = raw.task_input;

  if (isPlainObject(taskIn)) {

    record.task_input = taskIn;

  }

  return record;

}


