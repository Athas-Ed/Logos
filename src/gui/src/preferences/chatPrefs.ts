import type { PresentationMode } from "../types/chat";

export const PRESENTATION_STORAGE_KEY = "logos.presentation.v0";

const PRESENTATION_LABELS: Record<PresentationMode, string> = {
  work: "工作展示（摘要）",
  developer: "开发者展示（全文）",
};

export { PRESENTATION_LABELS };

export function readStoredPresentation(): PresentationMode | null {
  try {
    const raw = localStorage.getItem(PRESENTATION_STORAGE_KEY);
    if (raw === "work" || raw === "developer") return raw;
  } catch {
    /* ignore */
  }
  return null;
}

export function persistPresentation(mode: PresentationMode): void {
  try {
    localStorage.setItem(PRESENTATION_STORAGE_KEY, mode);
  } catch {
    /* ignore */
  }
}
