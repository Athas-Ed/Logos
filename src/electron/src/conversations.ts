import {

  existsSync,

  mkdirSync,

  readdirSync,

  readFileSync,

  renameSync,

  rmSync,

  statSync,

  writeFileSync,

} from "fs";

import { ipcMain } from "electron";

import * as path from "path";

import {
  readConversationsCacheSetting,
  resolveConversationsCacheAbs,
} from "./logosConfig";



/** 与 Renderer `conversation/types.ts` 的 `schema_version: 2` 对齐 */

export const CONVERSATION_SCHEMA_VERSION = 2;

export const LEGACY_CONVERSATION_SCHEMA_VERSION = 1;

export const LEGACY_V1_DEFAULT_SKILL_ID = "chat_inspire";



const ID_PATTERN = /^[a-zA-Z0-9_-]{1,64}$/;



export type ConversationStatus = "idle" | "archived";



export type ConversationMeta = {

  id: string;

  title: string;

  status: ConversationStatus;

  updated_at: string;

  byte_size: number;

};



export type ConversationReadOk = {

  ok: true;

  record: Record<string, unknown>;

};



export type ConversationReadErr = {

  ok: false;

  error: string;

  corrupt: boolean;

};



export type ConversationReadResult = ConversationReadOk | ConversationReadErr;



export type SimpleIpcResult = { ok: boolean; error?: string };

let conversationsRootPath: string | null = null;

function isPathInsideOrEqualRepo(repoRoot: string, candidateRaw: string): boolean {
  let root = path.resolve(repoRoot);
  let candidate = path.resolve(candidateRaw);
  if (process.platform === "win32") {
    root = root.toLowerCase();
    candidate = candidate.toLowerCase();
  }
  if (candidate === root) {
    return true;
  }
  const rel = path.relative(root, candidate);
  if (!rel) {
    return true;
  }
  if (path.isAbsolute(rel)) {
    return false;
  }
  const upper = rel.toUpperCase();
  return !upper.startsWith("..\\") && !upper.startsWith("../");
}

/** 在 Main 启动时调用：读取 ``paths.CONVERSATIONS_CACHE`` 并创建目录。 */
export function initConversationsStorage(repoRoot: string): string {
  const raw = readConversationsCacheSetting(repoRoot);
  const abs = resolveConversationsCacheAbs(repoRoot, raw);
  if (!isPathInsideOrEqualRepo(repoRoot, abs)) {
    throw new Error(
      `paths.CONVERSATIONS_CACHE 必须位于仓库根之下：${abs}（repo=${repoRoot}）`,
    );
  }
  mkdirSync(abs, { recursive: true });
  conversationsRootPath = abs;
  return abs;
}

export function getConversationsRoot(): string {
  if (!conversationsRootPath) {
    throw new Error("conversations storage not initialized");
  }
  return conversationsRootPath;
}

function conversationsRoot(): string {
  return getConversationsRoot();
}



export function sanitizeConversationId(raw: string): string | null {

  const id = raw.trim();

  if (!ID_PATTERN.test(id)) {

    return null;

  }

  if (id === "." || id === "..") {

    return null;

  }

  return id;

}



function filePathForId(id: string): string {

  const safe = sanitizeConversationId(id);

  if (!safe) {

    throw new Error("invalid_conversation_id");

  }

  return path.join(conversationsRoot(), `${safe}.json`);

}



function parseMetaFromRecord(

  id: string,

  byteSize: number,

  record: Record<string, unknown>,

): ConversationMeta | null {

  const status = record.status;

  if (status !== "idle" && status !== "archived") {

    return null;

  }

  const title =

    typeof record.title === "string" && record.title.trim()

      ? record.title.trim()

      : id;

  const updated =

    typeof record.updated_at === "string" && record.updated_at.trim()

      ? record.updated_at.trim()

      : new Date(0).toISOString();

  return {

    id,

    title,

    status,

    updated_at: updated,

    byte_size: byteSize,

  };

}



function validateCoreForId(

  id: string,

  record: Record<string, unknown>,

): string | null {

  if (record.id !== id) {

    return "id_mismatch";

  }

  if (!Array.isArray(record.messages)) {

    return "invalid_messages";

  }

  const status = record.status;

  if (status !== "idle" && status !== "archived") {

    return "invalid_status";

  }

  return null;

}



function validateRecordForRead(

  id: string,

  record: Record<string, unknown>,

): string | null {

  const version = record.schema_version;

  if (

    version !== CONVERSATION_SCHEMA_VERSION &&

    version !== LEGACY_CONVERSATION_SCHEMA_VERSION

  ) {

    return "schema_version_mismatch";

  }

  return validateCoreForId(id, record);

}



function validateRecordForWrite(

  id: string,

  record: Record<string, unknown>,

): string | null {

  if (record.schema_version !== CONVERSATION_SCHEMA_VERSION) {

    return "schema_version_mismatch";

  }

  const skill = record.skill_id;

  if (typeof skill !== "string" || !skill.trim()) {

    return "invalid_skill_id";

  }

  return validateCoreForId(id, record);

}



/** 读盘：v1 在 IPC 层补全 v2 字段，便于 Renderer 统一解析 */

export function normalizeConversationRecordForRead(

  record: Record<string, unknown>,

): Record<string, unknown> {

  if (record.schema_version === CONVERSATION_SCHEMA_VERSION) {

    return record;

  }

  if (record.schema_version !== LEGACY_CONVERSATION_SCHEMA_VERSION) {

    return record;

  }

  const skillRaw = record.skill_id;

  const skill_id =

    typeof skillRaw === "string" && skillRaw.trim()

      ? skillRaw.trim()

      : LEGACY_V1_DEFAULT_SKILL_ID;

  const next: Record<string, unknown> = {

    ...record,

    schema_version: CONVERSATION_SCHEMA_VERSION,

    skill_id,

  };

  return next;

}



export function listConversations(): ConversationMeta[] {

  const root = conversationsRoot();

  let names: string[] = [];

  try {

    names = readdirSync(root);

  } catch {

    return [];

  }

  const out: ConversationMeta[] = [];

  for (const name of names) {

    if (!name.endsWith(".json")) {

      continue;

    }

    const id = name.slice(0, -5);

    if (!sanitizeConversationId(id)) {

      continue;

    }

    const fp = path.join(root, name);

    let byteSize = 0;

    try {

      byteSize = statSync(fp).size;

    } catch {

      continue;

    }

    try {

      const raw = readFileSync(fp, "utf8");

      const parsed = JSON.parse(raw) as unknown;

      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {

        continue;

      }

      const meta = parseMetaFromRecord(

        id,

        byteSize,

        parsed as Record<string, unknown>,

      );

      if (meta) {

        out.push(meta);

      }

    } catch {

      /* 损坏文件：列表跳过，read 时单独报错 */

    }

  }

  out.sort((a, b) => b.updated_at.localeCompare(a.updated_at));

  return out;

}



export function readConversation(id: string): ConversationReadResult {

  const safe = sanitizeConversationId(id);

  if (!safe) {

    return { ok: false, error: "invalid_conversation_id", corrupt: false };

  }

  const fp = filePathForId(safe);

  if (!existsSync(fp)) {

    return { ok: false, error: "not_found", corrupt: false };

  }

  try {

    const raw = readFileSync(fp, "utf8");

    const parsed = JSON.parse(raw) as unknown;

    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {

      return { ok: false, error: "corrupt_json", corrupt: true };

    }

    const record = parsed as Record<string, unknown>;

    const err = validateRecordForRead(safe, record);

    if (err) {

      return { ok: false, error: err, corrupt: true };

    }

    return {

      ok: true,

      record: normalizeConversationRecordForRead(record),

    };

  } catch {

    return { ok: false, error: "corrupt_json", corrupt: true };

  }

}



export function writeConversation(

  id: string,

  payload: unknown,

): SimpleIpcResult {

  const safe = sanitizeConversationId(id);

  if (!safe) {

    return { ok: false, error: "invalid_conversation_id" };

  }

  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {

    return { ok: false, error: "invalid_payload" };

  }

  const record = payload as Record<string, unknown>;

  const err = validateRecordForWrite(safe, record);

  if (err) {

    return { ok: false, error: err };

  }

  const fp = filePathForId(safe);

  const tmp = `${fp}.${process.pid}.tmp`;

  const body = `${JSON.stringify(record, null, 2)}\n`;

  try {

    writeFileSync(tmp, body, "utf8");

    renameSync(tmp, fp);

    return { ok: true };

  } catch (e) {

    try {

      if (existsSync(tmp)) {

        rmSync(tmp, { force: true });

      }

    } catch {

      /* ignore */

    }

    return {

      ok: false,

      error: e instanceof Error ? e.message : String(e),

    };

  }

}



export function deleteConversation(id: string): SimpleIpcResult {

  const safe = sanitizeConversationId(id);

  if (!safe) {

    return { ok: false, error: "invalid_conversation_id" };

  }

  const fp = filePathForId(safe);

  try {

    if (existsSync(fp)) {

      rmSync(fp, { force: true });

    }

    return { ok: true };

  } catch (e) {

    return {

      ok: false,

      error: e instanceof Error ? e.message : String(e),

    };

  }

}



export function totalConversationBytes(): number {

  const root = conversationsRoot();

  let names: string[] = [];

  try {

    names = readdirSync(root);

  } catch {

    return 0;

  }

  let total = 0;

  for (const name of names) {

    if (!name.endsWith(".json")) {

      continue;

    }

    const fp = path.join(root, name);

    try {

      total += statSync(fp).size;

    } catch {

      /* skip */

    }

  }

  return total;

}



export function registerConversationIpcHandlers(): void {
  ipcMain.handle("logos:conversations-root", () => getConversationsRoot());

  ipcMain.handle("logos:conversations-list", () => listConversations());

  ipcMain.handle("logos:conversations-read", (_evt, id: string) =>

    readConversation(id),

  );

  ipcMain.handle(

    "logos:conversations-write",

    (_evt, id: string, payload: unknown) => writeConversation(id, payload),

  );

  ipcMain.handle("logos:conversations-delete", (_evt, id: string) =>

    deleteConversation(id),

  );

  ipcMain.handle("logos:conversations-total-bytes", () =>

    totalConversationBytes(),

  );

}


