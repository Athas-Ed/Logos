/** 审核晋升页面专用 API（不走 Agent 工具，直接调 REST 端点）。 */

const API_BASE = "/api/v1";

export type DraftFileEntry = {
  name: string;
  path: string;
  size_bytes: number;
  mtime_ns: number;
};

export async function fetchDraftsList(dir = ""): Promise<DraftFileEntry[]> {
  const params = new URLSearchParams();
  if (dir) params.set("dir", dir);
  const res = await fetch(`${API_BASE}/drafts?${params}`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.files ?? [];
}

export async function fetchDraftRead(path: string): Promise<string> {
  const params = new URLSearchParams({ path });
  const res = await fetch(`${API_BASE}/drafts/read?${params}`);
  if (!res.ok) return "";
  const data = await res.json();
  return data.content ?? "";
}

export type PromoteResult = {
  ok: boolean;
  applied: string[];
  failed: string[];
  notes: string;
};

export async function promoteDrafts(paths: string[]): Promise<PromoteResult> {
  const res = await fetch(`${API_BASE}/drafts/promote`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ paths }),
  });
  return res.ok ? res.json() : { ok: false, applied: [], failed: paths, notes: "晋升请求失败" };
}

export async function deleteDrafts(paths: string[]): Promise<boolean> {
  const res = await fetch(`${API_BASE}/drafts/delete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ paths }),
  });
  if (!res.ok) return false;
  const data = await res.json();
  return data.ok === true;
}

export type WriteResult = {
  ok: boolean;
  path: string;
  result: string;
};

export async function writeDraft(path: string, content: string): Promise<WriteResult> {
  const res = await fetch(`${API_BASE}/drafts/write`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path, content }),
  });
  return res.ok ? res.json() : { ok: false, path, result: "写入失败" };
}

export type RewriteFileInput = {
  path: string;
  content: string;
};

export type RewriteResult = {
  ok: boolean;
  written: string[];
  failed: string[];
};

export async function rewriteDrafts(
  files: RewriteFileInput[],
  requirements: string,
  systemHint?: string,
): Promise<RewriteResult> {
  const res = await fetch(`${API_BASE}/drafts/rewrite`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      files,
      requirements,
      system_hint: systemHint ?? "你是设定审核助手。注意保留 YAML front matter 与正文结构。",
    }),
  });
  if (!res.ok) {
    return { ok: false, written: [], failed: files.map((f) => f.path) };
  }
  return res.json();
}
