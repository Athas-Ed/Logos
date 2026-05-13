"use strict";

/**
 * 在子进程中为 `npm install` 设置 ELECTRON_MIRROR（npmmirror），避免 npm 10+
 * 对项目级 `.npmrc` 的 `electron_mirror` 报 Unknown project config，同时缓解直连 GitHub 的 ECONNRESET。
 *
 * 用法：在 `src/electron` 下执行 `npm run install:with-mirror`（可跟 npm install 的额外参数）。
 */

const { spawnSync } = require("node:child_process");
const process = require("node:process");

const env = { ...process.env };
if (!env.ELECTRON_MIRROR) {
  env.ELECTRON_MIRROR = "https://npmmirror.com/mirrors/electron/";
}

const npm = process.platform === "win32" ? "npm.cmd" : "npm";
const extra = process.argv.slice(2);
const args = ["install", ...extra];

const result = spawnSync(npm, args, {
  stdio: "inherit",
  env,
  shell: process.platform === "win32",
});
const code = result.status === null ? 1 : result.status;
process.exit(code);
