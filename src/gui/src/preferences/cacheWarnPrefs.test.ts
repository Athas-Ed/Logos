import { describe, expect, it, beforeEach } from "vitest";
import {
  clearCacheWarnSnooze,
  isCacheWarnSnoozed,
  persistCacheWarnThresholdBytes,
  readCacheWarnThresholdBytes,
  snoozeCacheWarnForSevenDays,
} from "./cacheWarnPrefs";

const THRESHOLD_KEY = "logos.ui.cache_warn_bytes.v0";
const SNOOZE_UNTIL_KEY = "logos.ui.cache_warn_snooze_until.v0";

beforeEach(() => {
  localStorage.removeItem(THRESHOLD_KEY);
  localStorage.removeItem(SNOOZE_UNTIL_KEY);
});

describe("cacheWarnPrefs", () => {
  it.skipIf(typeof localStorage === "undefined")(
    "persists threshold override",
    () => {
      persistCacheWarnThresholdBytes(4096);
      expect(readCacheWarnThresholdBytes(999)).toBe(4096);
    },
  );

  it.skipIf(typeof localStorage === "undefined")(
    "snooze blocks for seven days",
    () => {
      snoozeCacheWarnForSevenDays();
      expect(isCacheWarnSnoozed()).toBe(true);
      clearCacheWarnSnooze();
      expect(isCacheWarnSnoozed()).toBe(false);
    },
  );
});
