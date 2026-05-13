import type {
  ChatMessage,
  CitationItem,
  OperatingMode,
  PresentationMode,
} from "../types/chat";

const CHAT_PATH = "/api/v1/chat";

export type StreamChatEvent =
  | { kind: "delta"; text: string }
  /** work 档：服务端滚动摘要（整段替换展示，勿按增量拼接） */
  | { kind: "reasoning_summary"; text: string }
  /** developer 档：推理片段全文流式（按片段追加） */
  | { kind: "reasoning_full"; text: string }
  | { kind: "citations"; items: CitationItem[] }
  | {
      kind: "tool_trace_summary";
      tool: string;
      status: string;
      detail: string;
    }
  | {
      kind: "tool_trace_full";
      tool: string;
      arguments: Record<string, unknown>;
      result: string;
      error: string | null;
    }
  | { kind: "done"; payload: Record<string, unknown> }
  | { kind: "error"; code: string; message: string };

function parseCitationItems(raw: unknown): CitationItem[] {
  if (!Array.isArray(raw)) return [];
  return raw.map((it) => {
    const o = it as Record<string, unknown>;
    return {
      path: String(o.path ?? ""),
      snippet: String(o.snippet ?? ""),
      score: typeof o.score === "number" ? o.score : Number(o.score ?? 0),
    };
  });
}

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
      case "reasoning_summary": {
        const text =
          typeof payload.text === "string" ? payload.text : String(payload.text ?? "");
        return { kind: "reasoning_summary", text };
      }
      case "reasoning_full": {
        const text =
          typeof payload.text === "string" ? payload.text : String(payload.text ?? "");
        return { kind: "reasoning_full", text };
      }
      case "citations_partial":
      case "citations_full": {
        return { kind: "citations", items: parseCitationItems(payload.items) };
      }
      case "tool_trace_summary": {
        return {
          kind: "tool_trace_summary",
          tool: String(payload.tool ?? ""),
          status: String(payload.status ?? ""),
          detail: String(payload.detail ?? ""),
        };
      }
      case "tool_trace_full": {
        const args = payload.arguments;
        const argumentsObj =
          args !== null && typeof args === "object" && !Array.isArray(args)
            ? (args as Record<string, unknown>)
            : {};
        const err = payload.error;
        return {
          kind: "tool_trace_full",
          tool: String(payload.tool ?? ""),
          arguments: argumentsObj,
          result: String(payload.result ?? ""),
          error: err == null ? null : String(err),
        };
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
  /** 省略则服务端使用 ``ui.default_presentation`` */
  presentation?: PresentationMode;
  signal?: AbortSignal;
  onEvent: (ev: StreamChatEvent) => void;
}

/**
 * POST /api/v1/chat：SSE；契约见 original_docs/重要子系统开发文档/API-V0.2.md。
 */
export async function streamChat({
  messages,
  operatingMode,
  presentation,
  signal,
  onEvent,
}: StreamChatOptions): Promise<void> {
  const body: Record<string, unknown> = {
    messages,
    operating_mode: operatingMode,
  };
  if (presentation !== undefined) {
    body.presentation = presentation;
  }

  const res = await fetch(CHAT_PATH, {
    method: "POST",
    headers: {
      Accept: "text/event-stream",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
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

  const bodyStream = res.body;
  if (!bodyStream) {
    onEvent({
      kind: "error",
      code: "no_body",
      message: "响应无可读流",
    });
    return;
  }

  const reader = bodyStream.getReader();
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
