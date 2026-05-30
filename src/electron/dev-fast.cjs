/**
 * 开发态快速启动 Electron：仅在 dist 缺失或源码比产物新时执行 tsc，再启动 electron .
 * 供 scripts/start_logos_electron.* 与 `npm run electron:dev:fast` 使用。
 */
const fs = require("fs");
const path = require("path");
const { execSync, spawn } = require("child_process");

const root = __dirname;
const distMain = path.join(root, "dist", "main.js");
const distPreload = path.join(root, "dist", "preload.js");
const srcFiles = [
  "src/main.ts",
  "src/conversations.ts",
  "src/logosConfig.ts",
  "src/preload.ts",
];

function needsBuild() {
  if (!fs.existsSync(distMain) || !fs.existsSync(distPreload)) {
    return true;
  }
  const distMtime = Math.min(
    fs.statSync(distMain).mtimeMs,
    fs.statSync(distPreload).mtimeMs,
  );
  for (const rel of srcFiles) {
    const p = path.join(root, rel);
    if (!fs.existsSync(p)) {
      continue;
    }
    if (fs.statSync(p).mtimeMs > distMtime) {
      return true;
    }
  }
  return false;
}

if (needsBuild()) {
  console.error("[logos-electron] dist 过期或缺失，正在编译 main/preload …");
  execSync("npm run build", { stdio: "inherit", cwd: root, env: process.env });
} else {
  console.error("[logos-electron] 复用已有 dist，跳过 tsc。");
}

const electronBin = path.join(
  root,
  "node_modules",
  ".bin",
  process.platform === "win32" ? "electron.cmd" : "electron",
);
if (!fs.existsSync(electronBin)) {
  console.error("[logos-electron] 未找到 electron 可执行文件，请在 src/electron 下执行 npm install。");
  process.exit(1);
}

const child = spawn(electronBin, ["."], {
  stdio: "inherit",
  cwd: root,
  env: process.env,
  shell: process.platform === "win32",
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 0);
});
