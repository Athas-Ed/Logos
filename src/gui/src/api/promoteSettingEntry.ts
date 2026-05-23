import { apiUrl } from "./apiBase";

export type PromoteSettingEntryResult = {
  ok: boolean;
  applied: string[];
  skipped: string[];
  notes: string;
};

export async function promoteSettingEntry(args?: {
  draftRelpaths?: string[];
}): Promise<PromoteSettingEntryResult> {
  const body: Record<string, unknown> = {};
  if (args?.draftRelpaths?.length) {
    body.draft_relpaths = args.draftRelpaths;
  }
  const res = await fetch(apiUrl("/api/v1/setting-entry/promote"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`晋升失败 HTTP ${res.status}: ${text}`);
  }
  return (await res.json()) as PromoteSettingEntryResult;
}
