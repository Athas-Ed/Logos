export type ChatRole = "system" | "user" | "assistant";

export interface ChatMessage {
  role: ChatRole;
  content: string;
  /** ReAct 中间流式输出（SSE event: reasoning_delta），仅助手消息使用 */
  reasoning?: string;
}

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
