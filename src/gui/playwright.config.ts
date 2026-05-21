import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, devices } from "@playwright/test";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "../..");

export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: [["list"]],
  use: {
    ...devices["Desktop Chrome"],
    baseURL: "http://127.0.0.1:5173",
  },
  webServer: [
    {
      command: "python scripts/run_backend_stub.py",
      cwd: repoRoot,
      url: "http://127.0.0.1:8000/api/v1/health",
      timeout: 120_000,
      reuseExistingServer: false,
      env: {
        ...process.env,
        LOGOS_REPO_ROOT: repoRoot,
        LOGOS_FORCE_STUB_LLM: "1",
      },
    },
    {
      command: "npm run dev",
      cwd: __dirname,
      url: "http://127.0.0.1:5173",
      reuseExistingServer: false,
      env: {
        ...process.env,
        /** 绕过 Vite 代理，避免 SSE 在浏览器侧 body 永不结束 */
        VITE_API_BASE: "http://127.0.0.1:8000",
      },
    },
  ],
});
