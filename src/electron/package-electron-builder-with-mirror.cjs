"use strict";

/**
 * 为 `electron-builder` 下载 Electron 运行时设置 ELECTRON_MIRROR（与 `install-with-electron-mirror.cjs` 一致），
 * 缓解直连 GitHub releases 超时 / ECONNRESET，便于 `npm run package:win:with-mirror` 完成便携包。
 */

const { spawnSync } = require("node:child_process");
const process = require("node:process");

const env = { ...process.env };
if (!env.ELECTRON_MIRROR) {
  env.ELECTRON_MIRROR = "https://npmmirror.com/mirrors/electron/";
}

const npx = process.platform === "win32" ? "npx.cmd" : "npx";
const result = spawnSync(
  npx,
  ["electron-builder", "--win", "portable", "dir"],
  {
    stdio: "inherit",
    env,
    shell: process.platform === "win32",
    cwd: __dirname,
  },
);
const code = result.status === null ? 1 : result.status;
process.exit(code);
