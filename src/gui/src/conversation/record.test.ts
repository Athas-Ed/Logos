import { describe, expect, it } from "vitest";
import {
  buildConversationRecord,
  migrateConversationV1ToV2,
  parseConversationRecord,
} from "./record";
import { CONVERSATION_SCHEMA_VERSION, LEGACY_V1_DEFAULT_SKILL_ID } from "./types";

const BASE_V1 = {
  schema_version: 1,
  id: "conv-legacy",
  title: "旧会话",
  status: "idle" as const,
  updated_at: "2026-01-01T00:00:00.000Z",
  messages: [] as { role: "user"; content: string }[],
  citations: [],
  tool_trace_log: [],
  operating_mode: "author" as const,
  presentation: "work" as const,
};

describe("conversation record schema", () => {
  it("v1 读入迁移为 chat_inspire", () => {
    const parsed = parseConversationRecord("conv-legacy", BASE_V1);
    expect(parsed).not.toBeNull();
    expect(parsed?.schema_version).toBe(CONVERSATION_SCHEMA_VERSION);
    expect(parsed?.skill_id).toBe(LEGACY_V1_DEFAULT_SKILL_ID);
  });

  it("v3 retrieve_qa 含 citation_turns / tool_trace_turns", () => {
    const built = buildConversationRecord({
      id: "task-rq-1",
      messages: [
        { role: "user", content: "问题一" },
        { role: "assistant", content: "答案一" },
      ],
      citationTurns: [
        [{ path: "a.md", snippet: "s", score: 0.9 }],
      ],
      toolTraceTurns: [["[ok] retrieve: x"]],
      operatingMode: "author",
      presentation: "work",
      title: "检索问答",
      skillId: "retrieve_qa",
      taskPhase: "input",
    });
    expect(built.schema_version).toBe(3);
    expect(built.citation_turns).toHaveLength(1);
    expect(built.tool_trace_turns[0]).toHaveLength(1);

    const round = parseConversationRecord(
      "task-rq-1",
      built as unknown as Record<string, unknown>,
    );
    expect(round?.citation_turns[0]?.[0]?.path).toBe("a.md");
  });

  it("v2 citations 读入迁移为 citation_turns", () => {
    const raw = {
      schema_version: 2,
      id: "v2conv",
      title: "t",
      status: "idle",
      updated_at: "2026-01-01T00:00:00.000Z",
      messages: [],
      citations: [{ path: "p.md", snippet: "x", score: 1 }],
      tool_trace_log: ["trace"],
      operating_mode: "author",
      presentation: "work",
      skill_id: "retrieve_qa",
      task_phase: "done",
    };
    const parsed = parseConversationRecord("v2conv", raw);
    expect(parsed?.citation_turns).toEqual([
      [{ path: "p.md", snippet: "x", score: 1 }],
    ]);
    expect(parsed?.tool_trace_turns).toEqual([["trace"]]);
    expect(parsed?.task_phase).toBe("input");
  });

  it("migrateConversationV1ToV2 保留 v1 已写入的 skill 字段", () => {
    const core = {
      id: "x",
      title: "t",
      status: "idle" as const,
      updated_at: "2026-01-01T00:00:00.000Z",
      messages: [],
      citation_turns: [],
      tool_trace_turns: [],
      operating_mode: "author" as const,
      presentation: "work" as const,
    };
    const migrated = migrateConversationV1ToV2(core, {
      ...BASE_V1,
      skill_id: "lint_zh",
      task_phase: "done",
      task_input: { text: "样例" },
    });
    expect(migrated.skill_id).toBe("lint_zh");
    expect(migrated.task_phase).toBe("input");
    expect(migrated.task_input).toEqual({ text: "样例" });
  });
});
