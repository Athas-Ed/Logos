import type { OperatingMode, PresentationMode } from "../types/chat";

export const OPERATING_MODE_STORAGE_KEY = "logos.operating_mode.v0";
export const PRESENTATION_STORAGE_KEY = "logos.presentation.v0";

const MODE_LABELS: Record<OperatingMode, string> = {
  author: "作者（author）",
  screenwriter: "编剧（screenwriter）",
};

const PRESENTATION_LABELS: Record<PresentationMode, string> = {
  work: "工作展示（摘要）",
  developer: "开发者展示（全文）",
};

export { MODE_LABELS, PRESENTATION_LABELS };

export function readStoredOperatingMode(): OperatingMode | null {
  try {
    const raw = localStorage.getItem(OPERATING_MODE_STORAGE_KEY);
    if (raw === "author" || raw === "screenwriter") return raw;
  } catch {
    /* localStorage 不可用 */
  }
  return null;
}

export function persistOperatingMode(mode: OperatingMode): void {
  try {
    localStorage.setItem(OPERATING_MODE_STORAGE_KEY, mode);
  } catch {
    /* ignore */
  }
}

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

export function normalizeOperatingFromServer(raw: string): OperatingMode {
  return raw.trim().toLowerCase() === "screenwriter" ? "screenwriter" : "author";
}
