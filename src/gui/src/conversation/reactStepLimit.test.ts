import { describe, expect, it } from "vitest";

import {

  finalizeStreamAssistantMessage,

  inferReactStepLimitTurns,

  stripStepLimitSuffix,

} from "./reactStepLimit";



describe("reactStepLimit", () => {

  it("stripStepLimitSuffix removes legacy inline notice", () => {

    const raw =

      "正文内容。\n\n本次 ReAct 步数已达本轮上限。点击「继续检索」可在本会话续跑下一轮，继续检索同一主题的内容，但可能会影响性能。";

    expect(stripStepLimitSuffix(raw)).toBe("正文内容。");

  });



  it("inferReactStepLimitTurns aligns with user turns", () => {

    const turns = inferReactStepLimitTurns([

      { role: "user", content: "q1" },

      {

        role: "assistant",

        content: "a1\n\n本次 ReAct 步数已达本轮上限。点击「继续检索」可在本会话续跑下一轮，继续检索同一主题的内容，但可能会影响性能。",

      },

      { role: "user", content: "q2" },

      { role: "assistant", content: "a2" },

    ]);

    expect(turns).toHaveLength(2);

    expect(turns[0]?.hit).toBe(true);

    expect(turns[1]?.hit).toBe(false);

  });



  it("finalizeStreamAssistantMessage dedupes mirrored reasoning", () => {

    const messages = [

      { role: "user" as const, content: "q" },

      { role: "assistant" as const, content: "", reasoning: "" },

    ];

    const dup = "y".repeat(100);

    const out = finalizeStreamAssistantMessage(

      messages,

      { assistantText: "答", reasoningText: dup + dup },

      { stripSuffix: false },

    );

    expect(out[1]?.reasoning).toBe(dup);

    expect(out[1]?.content).toBe("答");

  });

});

