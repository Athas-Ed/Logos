import type { LogProfile, PresentationMode } from "../types/chat";
import { apiUrl } from "./apiBase";

export type BootstrapPayload = {
  default_presentation: PresentationMode;
  log_profile: LogProfile;
  operating_mode: string;
  /** 配置 `obs.show_log_root_in_gui`；默认 false（Obs O4） */
  obs_show_log_root_in_gui?: boolean;
  /** 仅当 `obs_show_log_root_in_gui` 为 true 时由后端给出绝对路径，否则 null/省略 */
  obs_logs_root?: string | null;
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
