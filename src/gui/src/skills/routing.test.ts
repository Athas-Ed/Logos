import { describe, expect, it, beforeEach } from "vitest";
import { hydrateSkillRegistry } from "./registry";
import { conversationNavPath, isInspireChatState, skillUsesTaskWizard } from "./routing";

/* 注册表初始为空，需先填充测试数据 */
function seedRegistry() {
  hydrateSkillRegistry([
    {
      skill_id: "lint_zh",
      display_name: "中文语病检查",
      description: "",
      ui_instructions: "",
      paradigm: "dialogue",
      persistence_tier: "p2",
      turn_policy: "single",
    },
    {
      skill_id: "outline_plan",
      display_name: "大纲规划",
      description: "",
      ui_instructions: "",
      paradigm: "plan",
      persistence_tier: "p1",
      turn_policy: "single",
    },
    {
      skill_id: "chat_inspire",
      display_name: "创作启发对话",
      description: "",
      ui_instructions: "",
      paradigm: "dialogue",
      persistence_tier: "p2",
      turn_policy: "multi",
    },
  ]);
}

describe("skill routing", () => {
  beforeEach(() => {
    seedRegistry();
  });

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
