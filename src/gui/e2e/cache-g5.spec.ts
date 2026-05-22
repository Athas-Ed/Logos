import { expect, test } from "@playwright/test";
import { installMockConversationsIpc } from "./mockConversationsIpc";

const NOW = "2026-05-22T10:00:00.000Z";

function archivedRecord(id: string, title: string) {
  return {
    schema_version: 2,
    id,
    title,
    status: "archived",
    updated_at: NOW,
    messages: [{ role: "user", content: "archived input" }],
    citations: [],
    tool_trace_log: [],
    operating_mode: "author",
    presentation: "work",
    skill_id: "lint_zh",
    task_phase: "done",
    task_input: { text: "archived input" },
  };
}

test.describe("G5 /cache", () => {
  test("归档 2 条 → 恢复 1 → 销毁 1", async ({ page }) => {
    await installMockConversationsIpc(page, {
      "task-a": archivedRecord("task-a", "任务 A"),
      "task-b": archivedRecord("task-b", "任务 B"),
    });

    await page.goto("/#/cache");
    await expect(page.getByTestId("archived-session-list")).toBeVisible();
    await expect(page.getByTestId("cache-total-bytes")).toContainText("占用");

    await expect(page.getByTestId("cache-select-task-a")).toBeVisible();
    await expect(page.getByTestId("cache-select-task-b")).toBeVisible();

    page.once("dialog", (d) => d.accept());
    await page.getByTestId("cache-select-task-b").check();
    await page.getByTestId("cache-destroy-selected").click();

    await expect(page.getByTestId("cache-select-task-b")).toHaveCount(0);
    await expect(page.getByTestId("cache-select-task-a")).toBeVisible();

    await page.getByTestId("cache-select-task-a").check();
    await page.getByTestId("cache-restore-selected").click();

    await expect(page).toHaveURL(/#\/task\/task-a/, { timeout: 10_000 });

    await page.goto("/#/cache");
    await expect(page.getByTestId("cache-empty")).toBeVisible();
  });
});
