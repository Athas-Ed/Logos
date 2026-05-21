import { expect, test } from "@playwright/test";







test.describe("GUI smoke", () => {



  test("冷启动首屏为技能面板（不要求 health）", async ({ page }) => {



    await page.goto("/");



    await expect(page.getByTestId("skill-panel-page")).toBeVisible();

    expect(page.url()).not.toMatch(/\/chat\//);



    await expect(



      page.getByRole("heading", { name: "技能面板" }),



    ).toBeVisible();



    await expect(page.getByTestId("skill-card-lint_zh")).toBeVisible();



    await expect(page.getByTestId("skill-card-chat_inspire")).toBeVisible();

    await expect(page.getByTestId("skill-card-retrieve_qa")).toBeVisible();



  });







  test("lint_zh 竖切片：输入并收到助手回复", async ({ page }) => {

    const sample = "他跑的很快。";



    await page.goto("/");

    await page.getByTestId("skill-card-lint_zh").click();

    await expect(page.getByTestId("task-page")).toBeVisible();

    await expect(page.getByTestId("task-input-textarea")).toBeVisible();



    await page.getByTestId("task-input-textarea").fill(sample);

    const responseDone = page.waitForResponse(

      (r) =>

        r.url().includes("/api/v1/chat") &&

        r.request().method() === "POST",

      { timeout: 30_000 },

    );

    await page.getByTestId("task-submit").click();

    const resp = await responseDone;

    expect(resp.ok()).toBeTruthy();



    const assistant = page.getByTestId("task-assistant-content");

    await expect(assistant).toContainText("桩后端", { timeout: 30_000 });

    await expect(page.getByTestId("task-archive")).toBeVisible({

      timeout: 15_000,

    });

  });



  test("chat_inspire 多轮：面板进入 Chat 并保留两轮历史", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("skill-card-chat_inspire").click();
    await expect(page).toHaveURL(/#\/chat\//);
    await expect(page.getByTestId("inspire-chat-page")).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "创作启发对话" }),
    ).toBeVisible();

    const sendAndWait = async (text: string) => {
      await page.getByTestId("chat-composer-textarea").fill(text);
      const responseDone = page.waitForResponse(
        (r) =>
          r.url().includes("/api/v1/chat") && r.request().method() === "POST",
        { timeout: 30_000 },
      );
      await page.getByTestId("chat-send").click();
      const resp = await responseDone;
      expect(resp.ok()).toBeTruthy();
      await expect(
        page.getByTestId("chat-message-assistant").last(),
      ).toContainText("桩后端", { timeout: 30_000 });
    };

    await sendAndWait("第一句启发");
    await expect(page.getByTestId("chat-message-user")).toHaveCount(1);

    let lastBody: { skill_id?: string; messages?: unknown[] } = {};
    await page.getByTestId("chat-composer-textarea").fill("第二句追问");
    const responseDone2 = page.waitForResponse(
      (r) =>
        r.url().includes("/api/v1/chat") && r.request().method() === "POST",
      { timeout: 30_000 },
    );
    await page.getByTestId("chat-send").click();
    const resp2 = await responseDone2;
    expect(resp2.ok()).toBeTruthy();
    lastBody = resp2.request().postDataJSON() as typeof lastBody;
    await expect(
      page.getByTestId("chat-message-assistant").last(),
    ).toContainText("桩后端", { timeout: 30_000 });

    await expect(page.getByTestId("chat-message-user")).toHaveCount(2);
    await expect(page.getByTestId("chat-message-assistant")).toHaveCount(2);
    expect(lastBody.skill_id).toBe("chat_inspire");
    expect(lastBody.messages?.length).toBeGreaterThanOrEqual(3);
  });

  test("点击 lint_zh 卡片进入任务页", async ({ page }) => {



    await page.goto("/");



    await page.getByTestId("skill-card-lint_zh").click();



    await expect(page).toHaveURL(/#\/task\//);



    await expect(page.getByTestId("task-page")).toBeVisible();



    await expect(



      page.getByRole("heading", { name: "中文语病检查" }),



    ).toBeVisible();



  });







  test("聊天页健康检查最终为可用", async ({ page }) => {



    await page.goto("/#/chat/default");



    const indicator = page.getByTestId("health-indicator");



    await expect(indicator).toBeVisible({ timeout: 120_000 });



    await expect(indicator).toHaveAttribute("data-health", "ok", {



      timeout: 120_000,



    });



  });







  test("设置 → 已归档会话 → 返回设置", async ({ page }) => {



    await page.goto("/#/chat/default");



    const indicator = page.getByTestId("health-indicator");



    await expect(indicator).toHaveAttribute("data-health", "ok", {



      timeout: 120_000,



    });







    await page.getByTestId("open-settings").click();



    await expect(page).toHaveURL(/#\/settings/);



    await expect(



      page.getByRole("heading", { name: "设置与诊断" }),



    ).toBeVisible();







    await page.getByTestId("archived-sessions-btn").click();



    await expect(page).toHaveURL(/#\/cache/);



    await expect(



      page.getByRole("heading", { name: "已归档会话" }),



    ).toBeVisible();







    await page.getByTestId("cache-back-to-settings").click();



    await expect(page).toHaveURL(/#\/settings/);



  });



});


