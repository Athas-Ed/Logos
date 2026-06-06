export type ChatRole = "system" | "user" | "assistant";

export interface ChatMessage {
  role: ChatRole;
  content: string;
  /** ReAct 中间流式输出（SSE reasoning_summary / reasoning_full 等），仅助手消息使用 */
  reasoning?: string;
}

/** 与 ``GET /api/v1/bootstrap``、``POST /api/v1/chat`` 的 presentation 对齐 */
export type PresentationMode = "work" | "developer";

/** 与 ``GET /api/v1/bootstrap`` 的 ``log_profile``、``obs.log_profile`` 对齐（只读展示） */
export type LogProfile = "minimal" | "standard" | "verbose" | "audit";

export interface CitationItem {
  path: string;
  snippet: string;
  score: number;
}

/** 运行模式（当前仅 author）；与请求体 operating_mode 对齐 */
export const OPERATING_MODE = "author" as const;
