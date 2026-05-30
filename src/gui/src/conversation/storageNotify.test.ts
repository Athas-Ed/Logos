import { describe, expect, it, vi } from "vitest";
import {
  notifyConversationsStorageChanged,
  subscribeConversationsStorageChanged,
} from "./storageNotify";

describe("storageNotify", () => {
  it.skipIf(typeof window === "undefined")("notifies subscribers", () => {
    const listener = vi.fn();
    const unsub = subscribeConversationsStorageChanged(listener);
    notifyConversationsStorageChanged();
    expect(listener).toHaveBeenCalledTimes(1);
    unsub();
    notifyConversationsStorageChanged();
    expect(listener).toHaveBeenCalledTimes(1);
  });
});
