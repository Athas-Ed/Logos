import { describe, expect, it } from "vitest";
import type { ChatMessage } from "../types/chat";
import type { ConversationState } from "./storeTypes";
import {
  normalizeInterruptedConversationState,
  stripTrailingEmptyAssistant,
} from "./streamLifecycle";

function baseState(
  patch: Partial<ConversationState> = {},
): ConversationState {
  return {
    id: "c1",
    skillId: "chat_inspire",
    taskPhase: "running",
    taskInputText: undefined,
    title: "t",
    status: "idle",
    messages: [],
    citations: [],
    toolTraceLog: [],
    citationTurns: [],
    toolTraceTurns: [],
    reactHitStepLimit: false,
    reactStepLimitTurns: [],
    pipelineSteps: [],
    pipelineWarnings: [],
    pipelineWrittenPaths: [],
    promoteMessage: null,
    promoteBusy: false,
    operatingMode: "author",
    presentation: "work",
    streaming: true,
    queued: true,
    streamError: "已中断",
    unread: false,
    hydrated: true,
    persistError: null,
    ...patch,
  };
}

describe("streamLifecycle", () => {
  it("stripTrailingEmptyAssistant removes trailing empty assistant only", () => {
    const messages: ChatMessage[] = [
      { role: "user", content: "hi" },
      { role: "assistant", content: "ok" },
      { role: "user", content: "again" },
      { role: "assistant", content: "", reasoning: "" },
    ];
    expect(stripTrailingEmptyAssistant(messages)).toHaveLength(3);
    expect(stripTrailingEmptyAssistant(messages)[2]?.role).toBe("user");
  });

  it("normalizeInterruptedConversationState clears flags and running phase", () => {
    const out = normalizeInterruptedConversationState(
      baseState({
        messages: [
          { role: "user", content: "x" },
          { role: "assistant", content: "" },
        ],
      }),
    );
    expect(out.messages).toHaveLength(1);
    expect(out.streaming).toBe(false);
    expect(out.queued).toBe(false);
    expect(out.streamError).toBeNull();
    expect(out.taskPhase).toBe("input");
  });
});
