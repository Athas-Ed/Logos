import type { ChatMessage, CitationItem, OperatingMode } from "../types/chat";

const CHAT_PATH = "/api/v1/chat";

export type StreamChatEvent =
  | { kind: "delta"; text: string }
  | { kind: "reasoning_delta"; text: string }
  | { kind: "citations"; items: CitationItem[] }
  | { kind: "done"; payload: Record<string, unknown> }
  | { kind: "error"; code: string; message: string };

function parseSseBlock(block: string): StreamChatEvent | null {
  const lines = block.split(/\r?\n/).filter((l) => l.length > 0);
  let eventName = "message";
  const dataLines: string[] = [];

  for (const line of lines) {
    if (line.startsWith("event:")) {
      eventName = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }

  if (dataLines.length === 0) return null;
  const dataRaw = dataLines.join("\n");

  try {
    const payload = JSON.parse(dataRaw) as Record<string, unknown>;
    switch (eventName) {
      case "delta": {
        const text =
          typeof payload.text === "string" ? payload.text : String(payload.text ?? "");
        return { kind: "delta", text };
      }
      case "reasoning_delta": {
        const text =
          typeof payload.text === "string" ? payload.text : String(payload.text ?? "");
        return { kind: "reasoning_delta", text };
      }
      case "citations": {
        const raw = payload.items;
        const items: CitationItem[] = Array.isArray(raw)
          ? raw.map((it) => {
              const o = it as Record<string, unknown>;
              return {
                path: String(o.path ?? ""),
                snippet: String(o.snippet ?? ""),
                score: typeof o.score === "number" ? o.score : Number(o.score ?? 0),
              };
            })
          : [];
        return { kind: "citations", items };
      }
      case "done":
        return { kind: "done", payload };
      case "error": {
        const code = String(payload.code ?? "error");
        const message = String(payload.message ?? "");
        return { kind: "error", code, message };
      }
      default:
        return null;
    }
  } catch {
    return null;
  }
}

export interface StreamChatOptions {
  messages: ChatMessage[];
  operatingMode: OperatingMode;
  signal?: AbortSignal;
  onEvent: (ev: StreamChatEvent) => void;
}

/**
 * POST /api/v1/chat：SSE；契约见 original_docs/重要子系统开发文档/API-V0.2.md。
 */
export async function streamChat({
  messages,
  operatingMode,
  signal,
  onEvent,
}: StreamChatOptions): Promise<void> {
  const res = await fetch(CHAT_PATH, {
    method: "POST",
    headers: {
      Accept: "text/event-stream",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      messages,
      operating_mode: operatingMode,
    }),
    signal,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    onEvent({
      kind: "error",
      code: `http_${res.status}`,
      message: text || res.statusText || String(res.status),
    });
    return;
  }

  const body = res.body;
  if (!body) {
    onEvent({
      kind: "error",
      code: "no_body",
      message: "响应无可读流",
    });
    return;
  }

  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const parts = buffer.split(/\n\n/);
      buffer = parts.pop() ?? "";

      for (const rawBlock of parts) {
        const block = rawBlock.trim();
        if (!block) continue;
        const ev = parseSseBlock(block);
        if (ev) onEvent(ev);
      }
    }

    const tail = buffer.trim();
    if (tail) {
      const ev = parseSseBlock(tail);
      if (ev) onEvent(ev);
    }
  } finally {
    reader.releaseLock();
  }
}
