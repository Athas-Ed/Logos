import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ConversationState } from "./storeTypes";
import {
  bindConversationPersistGuard,
  bindConversationPersistSource,
  cancelConversationPersist,
  flushConversationPersist,
  scheduleConversationPersist,
} from "./persistScheduler";

const writeMock = vi.fn(async (_id: string, _record: unknown) => ({ ok: true }));

vi.mock("./ipc", () => ({
  isConversationIpcAvailable: () => true,
  writeConversationIpc: (id: string, record: unknown) => writeMock(id, record),
}));

vi.mock("./sessionDismissed", () => ({
  isSessionDismissed: (id: string) => id === "dismissed",
}));

function makeState(
  id: string,
  patch: Partial<ConversationState> = {},
): ConversationState {
  return {
    id,
    skillId: "retrieve_qa",
    taskPhase: "running",
    taskInputText: "问题",
    title: "检索问答",
    status: "idle",
    messages: [{ role: "user", content: "hello" }],
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
    streaming: false,
    queued: false,
    streamError: null,
    unread: false,
    hydrated: true,
    persistError: null,
    ...patch,
  };
}

describe("persistScheduler", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    writeMock.mockClear();
    bindConversationPersistSource(() => undefined);
    bindConversationPersistGuard(() => true);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("writes latest in-memory state when debounce fires", async () => {
    const states: Record<string, ConversationState> = {
      c1: makeState("c1", {
        messages: [{ role: "user", content: "old" }],
      }),
    };
    bindConversationPersistSource((id) => states[id]);

    scheduleConversationPersist("c1", states.c1);
    states.c1 = makeState("c1", {
      messages: [{ role: "user", content: "new" }],
    });

    await vi.advanceTimersByTimeAsync(700);

    expect(writeMock).toHaveBeenCalledTimes(1);
    const record = writeMock.mock.calls[0]![1] as {
      messages: { content: string }[];
      skill_id: string;
    };
    expect(record.messages[0].content).toBe("new");
    expect(record.skill_id).toBe("retrieve_qa");
  });

  it("skips stale flush when a newer schedule supersedes it", async () => {
    const states: Record<string, ConversationState> = {
      c1: makeState("c1", {
        messages: [{ role: "user", content: "flush" }],
      }),
    };
    bindConversationPersistSource((id) => states[id]);

    flushConversationPersist("c1", states.c1);
    states.c1 = makeState("c1", {
      messages: [{ role: "user", content: "scheduled" }],
    });
    scheduleConversationPersist("c1", states.c1);

    await Promise.resolve();
    await vi.advanceTimersByTimeAsync(700);

    expect(writeMock).toHaveBeenCalledTimes(1);
    const record = writeMock.mock.calls[0]![1] as {
      messages: { content: string }[];
      skill_id: string;
    };
    expect(record.messages[0].content).toBe("scheduled");
  });

  it("does not persist dismissed sessions", async () => {
    bindConversationPersistSource(() => makeState("dismissed"));
    scheduleConversationPersist("dismissed", makeState("dismissed"));
    await vi.advanceTimersByTimeAsync(700);
    expect(writeMock).not.toHaveBeenCalled();
  });

  it("cancel invalidates pending debounced writes", async () => {
    bindConversationPersistSource(() => makeState("c1"));
    scheduleConversationPersist("c1", makeState("c1"));
    cancelConversationPersist("c1");
    await vi.advanceTimersByTimeAsync(700);
    expect(writeMock).not.toHaveBeenCalled();
  });
});
