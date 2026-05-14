import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, devices } from "@playwright/test";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "../..");

export default defineConfig({
  testDir: "./e2e",
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
      reuseExistingServer: !process.env.CI,
    },
    {
      command: "npm run dev",
      cwd: __dirname,
      url: "http://127.0.0.1:5173",
      reuseExistingServer: !process.env.CI,
    },
  ],
});
