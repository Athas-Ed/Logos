import { expect, test } from "@playwright/test";

test.describe("GUI smoke", () => {
  test("首屏健康检查最终为可用", async ({ page }) => {
    await page.goto("/");
    const indicator = page.getByTestId("health-indicator");
    await expect(indicator).toBeVisible({ timeout: 120_000 });
    await expect(indicator).toHaveAttribute("data-health", "ok", {
      timeout: 120_000,
    });
  });
});
