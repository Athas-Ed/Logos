import { afterEach, describe, expect, it } from "vitest";
import {
  clearSessionDismissed,
  isSessionDismissed,
  markSessionDismissed,
} from "./sessionDismissed";

const KEY = "logos.session.dismissedTabIds";

afterEach(() => {
  localStorage.removeItem(KEY);
});

describe("sessionDismissed", () => {
  it.skipIf(typeof localStorage === "undefined")(
    "marks and clears dismissed ids",
    () => {
    markSessionDismissed("task-a");
    expect(isSessionDismissed("task-a")).toBe(true);
    clearSessionDismissed("task-a");
    expect(isSessionDismissed("task-a")).toBe(false);
    },
  );
});
