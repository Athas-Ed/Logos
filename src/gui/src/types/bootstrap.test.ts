import { describe, expect, it } from "vitest";
import { panelSkillsFromBootstrap } from "./bootstrap";
import { hydrateSkillRegistry } from "../skills/registry";

describe("panelSkillsFromBootstrap", () => {
  it("正确解析 bootstrap skill 数据（不依赖回退）", () => {
    const cards = panelSkillsFromBootstrap([
      {
        skill_id: "retrieve_qa",
        display_name: "检索问答",
        description: "react 样例",
        ui_instructions: "先检索再读原文。",
        persistence_tier: "p2",
        paradigm: "react",
        turn_policy: "single",
        custom_page: "",
      },
    ]);
    expect(cards).toHaveLength(1);
    expect(cards[0].turn_policy).toBe("single");
    expect(cards[0].ui_instructions).toBe("先检索再读原文。");
    expect(cards[0].customPage).toBeUndefined();
  });

  it("custom_page 映射为 customPage", () => {
    const cards = panelSkillsFromBootstrap([
      {
        skill_id: "draft_review",
        display_name: "审核晋升",
        description: "test",
        persistence_tier: "p1",
        paradigm: "dialogue",
        custom_page: "review",
      },
    ]);
    expect(cards).toHaveLength(1);
    expect(cards[0].customPage).toBe("review");
  });

  it("bootstrap 数据直接填充注册表", () => {
    const cards = panelSkillsFromBootstrap([
      {
        skill_id: "chat_inspire",
        display_name: "创作启发对话",
        description: "多轮启发",
        ui_instructions: "多轮对话。",
        persistence_tier: "p2",
        paradigm: "dialogue",
        turn_policy: "multi",
      },
    ]);
    hydrateSkillRegistry(cards);
    // 后续组件通过 getSkillMeta 读取，无需回退
    expect(cards[0].turn_policy).toBe("multi");
  });
});
