import type { LogProfile, PresentationMode } from "../types/chat";
import { apiUrl } from "./apiBase";

export type BootstrapPayload = {
  default_presentation: PresentationMode;
  log_profile: LogProfile;
  operating_mode: string;
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
