export type ChatRole = "system" | "user" | "assistant";

export interface ChatMessage {
  role: ChatRole;
  content: string;
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
