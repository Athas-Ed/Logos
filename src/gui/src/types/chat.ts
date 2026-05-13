export type ChatRole = "system" | "user" | "assistant";

export interface ChatMessage {
  role: ChatRole;
  content: string;
  /** ReAct 中间流式输出（SSE reasoning_summary / reasoning_full 等），仅助手消息使用 */
  reasoning?: string;
}

/** 与 ``GET /api/v1/bootstrap``、``POST /api/v1/chat`` 的 presentation 对齐 */
export type PresentationMode = "work" | "developer";

export const PRESENTATION_STORAGE_KEY = "logos.presentation.v0";

/** 与 ``GET /api/v1/bootstrap`` 的 ``log_profile``、``obs.log_profile`` 对齐（只读展示） */
export type LogProfile = "minimal" | "standard" | "verbose" | "audit";

export interface CitationItem {
  path: string;
  snippet: string;
  score: number;
}

/** SPEC-V0.1：author | screenwriter；与请求体 operating_mode 对齐 */
export type OperatingMode = "author" | "screenwriter";

export const OPERATING_MODES: readonly OperatingMode[] = [
  "author",
  "screenwriter",
] as const;
