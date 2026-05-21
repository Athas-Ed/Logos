import { describe, expect, it } from "vitest";
import { panelSkillsFromBootstrap } from "./bootstrap";

describe("panelSkillsFromBootstrap", () => {
describe("panelSkillsFromBootstrap", () => {
  it("补全 retrieve_qa 的 turn_policy 与 ui_instructions", () => {
    const cards = panelSkillsFromBootstrap([
      {
        skill_id: "retrieve_qa",
        display_name: "检索问答",
        description: "react 样例",
        ui_instructions: "先检索再读原文。",
        persistence_tier: "p2",
        paradigm: "react",
      },
    ]);
    expect(cards).toHaveLength(1);
    expect(cards[0].turn_policy).toBe("single");
    expect(cards[0].ui_instructions).toBe("先检索再读原文。");
  });
});