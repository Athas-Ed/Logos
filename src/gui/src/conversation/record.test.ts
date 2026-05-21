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

describe("conversation record schema v2", () => {
  it("v1 读入迁移为 chat_inspire", () => {
    const parsed = parseConversationRecord("conv-legacy", BASE_V1);
    expect(parsed).not.toBeNull();
    expect(parsed?.schema_version).toBe(CONVERSATION_SCHEMA_VERSION);
    expect(parsed?.skill_id).toBe(LEGACY_V1_DEFAULT_SKILL_ID);
  });

  it("v2 lint 任务含 skill_id / task_phase / task_input", () => {
    const built = buildConversationRecord({
      id: "task-lint-1",
      messages: [],
      citations: [],
      toolTraceLog: [],
      operatingMode: "author",
      presentation: "work",
      title: "中文语病检查",
      skillId: "lint_zh",
      taskPhase: "input",
      taskInputText: "他跑的很快。",
    });
    expect(built.schema_version).toBe(2);
    expect(built.skill_id).toBe("lint_zh");
    expect(built.task_phase).toBe("input");
    expect(built.task_input).toEqual({ text: "他跑的很快。" });

    const round = parseConversationRecord("task-lint-1", built as unknown as Record<string, unknown>);
    expect(round?.skill_id).toBe("lint_zh");
    expect(round?.task_phase).toBe("input");
    expect(round?.task_input).toEqual({ text: "他跑的很快。" });
  });

  it("migrateConversationV1ToV2 保留 v1 已写入的 skill 字段", () => {
    const core = {
      id: "x",
      title: "t",
      status: "idle" as const,
      updated_at: "2026-01-01T00:00:00.000Z",
      messages: [],
      citations: [],
      tool_trace_log: [],
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
    expect(migrated.task_phase).toBe("done");
    expect(migrated.task_input).toEqual({ text: "样例" });
  });
});

