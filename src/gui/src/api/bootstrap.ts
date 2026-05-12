import type { PresentationMode } from "../types/chat";

export type BootstrapPayload = {
  default_presentation: PresentationMode;
  log_profile: string;
  operating_mode: string;
};

export async function fetchBootstrap(): Promise<BootstrapPayload | null> {
  try {
    const r = await fetch("/api/v1/bootstrap");
    if (!r.ok) return null;
    return (await r.json()) as BootstrapPayload;
  } catch {
    return null;
  }
}
