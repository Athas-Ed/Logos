import type { LogProfile, PresentationMode } from "../types/chat";
import type { BootstrapSkill, BootstrapUi } from "../types/bootstrap";
import { apiUrl } from "./apiBase";

export type LlmMode = "stub" | "remote";

export type BootstrapPayload = {
  default_presentation: PresentationMode;
  log_profile: LogProfile;
  operating_mode: string;
  /** 桩 LLM 或远程 OpenAI 兼容 API */
  llm_mode?: LlmMode;
  /** 配置 `obs.show_log_root_in_gui`；默认 false（Obs O4） */
  obs_show_log_root_in_gui?: boolean;
  /** 仅当 `obs_show_log_root_in_gui` 为 true 时由后端给出绝对路径，否则 null/省略 */
  obs_logs_root?: string | null;
  /** 档 B 会话目录绝对路径（``paths.CONVERSATIONS_CACHE``） */
  conversations_cache_root?: string;
  ui?: BootstrapUi;
  /** 技能面板可渲染的产品 Skill 列表（F5-08） */
  skills?: BootstrapSkill[];
};

export async function fetchBootstrap(): Promise<BootstrapPayload | null> {
  try {
    const r = await fetch(apiUrl("/api/v1/bootstrap"));
    if (!r.ok) return null;
    return (await r.json()) as BootstrapPayload;
  } catch {
    return null;
  }
}
