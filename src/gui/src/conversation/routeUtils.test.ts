import { describe, expect, it } from "vitest";
import { isConversationRoute } from "./routeUtils";

describe("isConversationRoute", () => {
  it("matches task/chat/lab paths exactly", () => {
    expect(isConversationRoute("/task/abc", "abc")).toBe(true);
    expect(isConversationRoute("/chat/abc", "abc")).toBe(true);
    expect(isConversationRoute("/lab/abc", "abc")).toBe(true);
  });

  it("does not match prefix-only or other ids", () => {
    expect(isConversationRoute("/task/abcd", "abc")).toBe(false);
    expect(isConversationRoute("/cache", "abc")).toBe(false);
    expect(isConversationRoute("/", "abc")).toBe(false);
  });
});
