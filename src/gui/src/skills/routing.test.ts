import { describe, expect, it } from "vitest";
import { conversationNavPath, isInspireChatState, skillUsesTaskWizard } from "./routing";

describe("skill routing", () => {
  it("lint_zh 走任务向导", () => {
    expect(skillUsesTaskWizard("lint_zh")).toBe(true);
    const path = conversationNavPath({
      id: "a",
      skillId: "lint_zh",
      taskPhase: "input",
    });
    expect(path).toBe("/task/a");
  });

  it("outline_plan 走任务向导", () => {
    expect(skillUsesTaskWizard("outline_plan")).toBe(true);
  });

  it("chat_inspire 走多轮 Chat", () => {
    expect(skillUsesTaskWizard("chat_inspire")).toBe(false);
    const state = { id: "b", skillId: "chat_inspire" as const };
    expect(conversationNavPath(state)).toBe("/chat/b");
    expect(isInspireChatState(state)).toBe(true);
  });
});

