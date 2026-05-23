import {
  BOOTSTRAP_UI_DEFAULTS,
  type BootstrapUi,
} from "../types/bootstrap";

const THRESHOLD_KEY = "logos.ui.cache_warn_bytes.v0";
const SNOOZE_UNTIL_KEY = "logos.ui.cache_warn_snooze_until.v0";

const SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000;

function storageAvailable(): boolean {
  try {
    return typeof localStorage !== "undefined";
  } catch {
    return false;
  }
}

export function readCacheWarnThresholdBytes(fallback?: number): number {
  const base = fallback ?? BOOTSTRAP_UI_DEFAULTS.cache_warn_bytes;
  if (!storageAvailable()) {
    return base;
  }
  try {
    const raw = localStorage.getItem(THRESHOLD_KEY);
    if (raw == null) {
      return base;
    }
    const n = Number.parseInt(raw, 10);
    if (!Number.isFinite(n) || n < 0) {
      return base;
    }
    return n;
  } catch {
    return base;
  }
}

export function persistCacheWarnThresholdBytes(bytes: number): void {
  if (!storageAvailable() || !Number.isFinite(bytes) || bytes < 0) {
    return;
  }
  try {
    localStorage.setItem(THRESHOLD_KEY, String(Math.round(bytes)));
  } catch {
    /* ignore */
  }
}

export function isCacheWarnSnoozed(nowMs: number = Date.now()): boolean {
  if (!storageAvailable()) {
    return false;
  }
  try {
    const raw = localStorage.getItem(SNOOZE_UNTIL_KEY);
    if (raw == null) {
      return false;
    }
    const until = Number.parseInt(raw, 10);
    return Number.isFinite(until) && nowMs < until;
  } catch {
    return false;
  }
}

export function snoozeCacheWarnForDays(days: number = 7): void {
  if (!storageAvailable() || days <= 0) {
    return;
  }
  try {
    const until = Date.now() + days * 24 * 60 * 60 * 1000;
    localStorage.setItem(SNOOZE_UNTIL_KEY, String(until));
  } catch {
    /* ignore */
  }
}

export function snoozeCacheWarnForSevenDays(): void {
  snoozeCacheWarnForDays(7);
}

export function clearCacheWarnSnooze(): void {
  if (!storageAvailable()) {
    return;
  }
  try {
    localStorage.removeItem(SNOOZE_UNTIL_KEY);
  } catch {
    /* ignore */
  }
}

/** 设置页展示：本地覆盖优先，否则 bootstrap。 */
export function resolveEffectiveCacheWarnUi(
  bootstrapUi: BootstrapUi | null | undefined,
): BootstrapUi {
  const fromServer = bootstrapUi ?? BOOTSTRAP_UI_DEFAULTS;
  return {
    ...fromServer,
    cache_warn_bytes: readCacheWarnThresholdBytes(fromServer.cache_warn_bytes),
  };
}

export { SEVEN_DAYS_MS };
