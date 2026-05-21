import { parseConversationRecord } from "./record";
import type {
  ConversationIpcResult,
  ConversationMeta,
  ConversationReadResult,
  ConversationRecord,
} from "./types";

export function isConversationIpcAvailable(): boolean {
  return Boolean(window.logosElectron?.conversations);
}

export async function listConversationsIpc(): Promise<ConversationMeta[]> {
  const api = window.logosElectron?.conversations?.list;
  if (!api) {
    return [];
  }
  return api();
}

export async function readConversationIpc(
  id: string,
): Promise<ConversationReadResult> {
  const api = window.logosElectron?.conversations?.read;
  if (!api) {
    return { ok: false, error: "ipc_unavailable", corrupt: false };
  }
  const r = await api(id);
  if (!r.ok) {
    return r;
  }
  const parsed = parseConversationRecord(id, r.record);
  if (!parsed) {
    return { ok: false, error: "invalid_record", corrupt: true };
  }
  return { ok: true, record: parsed };
}

export async function writeConversationIpc(
  id: string,
  record: ConversationRecord,
): Promise<ConversationIpcResult> {
  const api = window.logosElectron?.conversations?.write;
  if (!api) {
    return { ok: false, error: "ipc_unavailable" };
  }
  return api(id, record as unknown as Record<string, unknown>);
}

export async function deleteConversationIpc(
  id: string,
): Promise<ConversationIpcResult> {
  const api = window.logosElectron?.conversations?.delete;
  if (!api) {
    return { ok: false, error: "ipc_unavailable" };
  }
  return api(id);
}

export async function totalConversationBytesIpc(): Promise<number> {
  const api = window.logosElectron?.conversations?.totalBytes;
  if (!api) {
    return 0;
  }
  return api();
}
