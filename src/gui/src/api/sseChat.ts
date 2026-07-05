import type {
  ChatMessage,
  CitationItem,
  PresentationMode,
} from "../types/chat";
import { apiUrl } from "./apiBase";
import { connectBackoffMs, delayWithSignal } from "./streamRetry";

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
  | {
      kind: "pipeline_step";
      stepId: string;
      status: string;
      summary: string;
    }
  | { kind: "pipeline_warning"; warnings: string[] }
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
      case "pipeline_step": {
        return {
          kind: "pipeline_step",
          stepId: String(payload.step_id ?? ""),
          status: String(payload.status ?? ""),
          summary: String(payload.summary ?? ""),
        };
      }
      case "pipeline_warning": {
        const raw = payload.warnings;
        const warnings = Array.isArray(raw)
          ? raw.map((w) => String(w))
          : [];
        return { kind: "pipeline_warning", warnings };
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
  operatingMode: string;
  /** 省略则服务端使用 ``ui.default_presentation`` */
  presentation?: PresentationMode;
  /** 产品 Skill（F5-02）；任务页必填 */
  skillId?: string;
  /** 任务向导第二步输入（F5-02） */
  taskInput?: Record<string, unknown>;
  /** 开发者试验台：强制 PR 范式 */
  paradigmOverride?: string;
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
  skillId,
  taskInput,
  paradigmOverride,
  signal,
  onEvent,
}: StreamChatOptions): Promise<void> {
  const requestBody: Record<string, unknown> = {
    messages,
    operating_mode: operatingMode,
  };
  if (presentation !== undefined) {
    requestBody.presentation = presentation;
  }
  if (skillId !== undefined && skillId !== "") {
    requestBody.skill_id = skillId;
  }
  if (taskInput !== undefined) {
    requestBody.task_input = taskInput;
  }
  if (paradigmOverride !== undefined && paradigmOverride !== "") {
    requestBody.paradigm_override = paradigmOverride;
  }

  const url = apiUrl(CHAT_PATH);
  const maxConnectAttempts = 4;
  let res: Response | undefined;
  for (let attempt = 0; attempt < maxConnectAttempts; attempt++) {
    if (attempt > 0) {
      try {
        await delayWithSignal(connectBackoffMs(attempt - 1), signal);
      } catch {
        onEvent({
          kind: "error",
          code: "aborted",
          message: "已中断",
        });
        return;
      }
    }
    try {
      res = await fetch(url, {
        method: "POST",
        headers: {
          Accept: "text/event-stream",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestBody),
        signal,
      });
    } catch (e) {
      if (signal?.aborted) {
        onEvent({
          kind: "error",
          code: "aborted",
          message: "已中断",
        });
        return;
      }
      if (attempt === maxConnectAttempts - 1) {
        onEvent({
          kind: "error",
          code: "network",
          message: e instanceof Error ? e.message : String(e),
        });
        return;
      }
      continue;
    }

    if (!res.ok) {
      const retryable =
        res.status >= 502 &&
        res.status <= 504 &&
        attempt < maxConnectAttempts - 1;
      if (retryable) {
        await res.text().catch(() => "");
        continue;
      }
      const text = await res.text().catch(() => "");
      onEvent({
        kind: "error",
        code: `http_${res.status}`,
        message: text || res.statusText || String(res.status),
      });
      return;
    }
    break;
  }

  if (!res || !res.ok) {
    onEvent({
      kind: "error",
      code: "no_response",
      message: "无法建立聊天连接",
    });
    return;
  }

  const responseBody = res.body;
  if (!responseBody) {
    onEvent({
      kind: "error",
      code: "no_body",
      message: "响应无 body",
    });
    return;
  }

  const reader = responseBody.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const dispatchBlock = (block: string) => {
    const trimmed = block.trim();
    if (!trimmed) {
      return false;
    }
    const ev = parseSseBlock(trimmed);
    if (!ev) {
      return false;
    }
    onEvent(ev);
    return ev.kind === "done" || ev.kind === "error";
  };

  try {
    while (true) {
      if (signal?.aborted) {
        onEvent({
          kind: "error",
          code: "aborted",
          message: "已中断",
        });
        return;
      }
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split(/\n\n+/);
      buffer = parts.pop() ?? "";
      for (const part of parts) {
        if (dispatchBlock(part)) {
          return;
        }
      }
    }
    if (buffer.trim()) {
      dispatchBlock(buffer);
    }
  } catch (e) {
    if (signal?.aborted) {
      onEvent({
        kind: "error",
        code: "aborted",
        message: "已中断",
      });
      return;
    }
    onEvent({
      kind: "error",
      code: "sse_read",
      message: e instanceof Error ? e.message : String(e),
    });
    return;
  } finally {
    reader.releaseLock();
  }
}
