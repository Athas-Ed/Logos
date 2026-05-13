import { appendFileSync, existsSync, mkdirSync } from "fs";
import { spawn, spawnSync, type ChildProcess } from "child_process";
import { app, BrowserWindow, dialog } from "electron";
import * as net from "net";
import * as path from "path";

const DEFAULT_GUI_HOST = "127.0.0.1";
const DEFAULT_GUI_PORT = 5173;
const DEFAULT_BACKEND_HEALTH_URL = "http://127.0.0.1:8000/api/v1/health";
const DEFAULT_BACKEND_READY_TIMEOUT_MS = 120_000;
const DEFAULT_BACKEND_HEALTH_POLL_MS = 400;
const DEFAULT_BACKEND_MAX_RESTARTS = 3;

let backendChild: ChildProcess | null = null;
/** Main 主动终止后端时为 true，子进程 exit 不应触发自动重启 */
let backendTerminateRequested = false;
/** 应用整体退出中，忽略子进程异常退出 */
let appShutdownRequested = false;
/** 当前「连续崩溃周期」内已执行的自动重启次数（健康恢复后清零） */
let backendCrashRestartCount = 0;
/** 防止退出事件在健康等待期间重入，触发并发 `recoverBackendAfterCrash` */
let backendRecoveryInFlight = false;
let primaryWindow: BrowserWindow | null = null;

type LogosBackendIpcStatus = {
  state: "recovering" | "ready" | "failed";
  attempt?: number;
  maxAttempts?: number;
  message?: string;
};

function dataUrlHtml(title: string, body: string): string {
  const html = `<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"/><title>${title}</title>
<style>body{font-family:system-ui,sans-serif;margin:2rem;line-height:1.5;color:#222;background:#fafafa}</style></head>
<body><h1 style="font-size:1.1rem">${title}</h1><p>${body}</p></body></html>`;
  return `data:text/html;charset=utf-8,${encodeURIComponent(html)}`;
}

function readBackendHealthUrl(): string {
  const fromEnv = process.env.LOGOS_BACKEND_HEALTH_URL?.trim();
  if (fromEnv) {
    return fromEnv;
  }
  const origin = process.env.LOGOS_BACKEND_API_ORIGIN?.trim();
  if (origin) {
    return `${origin.replace(/\/$/, "")}/api/v1/health`;
  }
  return DEFAULT_BACKEND_HEALTH_URL;
}

function readBackendReadyTimeoutMs(): number {
  const raw = process.env.LOGOS_ELECTRON_BACKEND_READY_TIMEOUT_MS?.trim();
  if (!raw) {
    return DEFAULT_BACKEND_READY_TIMEOUT_MS;
  }
  const n = Number.parseInt(raw, 10);
  if (!Number.isFinite(n) || n < 0) {
    throw new Error(
      `Invalid LOGOS_ELECTRON_BACKEND_READY_TIMEOUT_MS=${JSON.stringify(raw)}: expected non-negative integer.`,
    );
  }
  return n;
}

function readBackendHealthPollMs(): number {
  const raw = process.env.LOGOS_ELECTRON_BACKEND_HEALTH_POLL_MS?.trim();
  if (!raw) {
    return DEFAULT_BACKEND_HEALTH_POLL_MS;
  }
  const n = Number.parseInt(raw, 10);
  if (!Number.isFinite(n) || n < 100) {
    throw new Error(
      `Invalid LOGOS_ELECTRON_BACKEND_HEALTH_POLL_MS=${JSON.stringify(raw)}: expected integer >= 100.`,
    );
  }
  return n;
}

function readBackendMaxRestarts(): number {
  const raw = process.env.LOGOS_ELECTRON_BACKEND_MAX_RESTARTS?.trim();
  if (!raw) {
    return DEFAULT_BACKEND_MAX_RESTARTS;
  }
  const n = Number.parseInt(raw, 10);
  if (!Number.isFinite(n) || n < 0) {
    throw new Error(
      `Invalid LOGOS_ELECTRON_BACKEND_MAX_RESTARTS=${JSON.stringify(raw)}: expected non-negative integer.`,
    );
  }
  return n;
}

async function probeBackendHealthOnce(healthUrl: string): Promise<boolean> {
  const ac = new AbortController();
  const t = setTimeout(() => ac.abort(), 2500);
  try {
    const res = await fetch(healthUrl, { method: "GET", signal: ac.signal });
    return res.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(t);
  }
}

async function waitForBackendHealth(healthUrl: string): Promise<boolean> {
  const timeoutMs = readBackendReadyTimeoutMs();
  if (timeoutMs === 0) {
    return probeBackendHealthOnce(healthUrl);
  }
  const pollMs = readBackendHealthPollMs();
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await probeBackendHealthOnce(healthUrl)) {
      return true;
    }
    await new Promise((r) => setTimeout(r, pollMs));
  }
  return false;
}

function resolveRepoRoot(): string {
  // `electron .` 时 `app.getAppPath()` 为 `.../src/electron`（含 package.json 的目录）
  return path.resolve(app.getAppPath(), "..", "..");
}

function defaultPythonExecutable(repoRoot: string): string {
  const fromEnv = process.env.LOGOS_PYTHON?.trim();
  if (fromEnv) {
    return fromEnv;
  }
  const win = process.platform === "win32";
  const venvPy = path.join(repoRoot, win ? ".venv\\Scripts\\python.exe" : ".venv/bin/python");
  if (existsSync(venvPy)) {
    return venvPy;
  }
  return "python";
}

function wireBackendLogs(child: ChildProcess, mode: string): void {
  if (mode === "inherit" || mode === "ignore") {
    return;
  }
  const sink = (chunk: Buffer) => {
    for (const line of chunk.toString("utf8").split(/\r?\n/)) {
      if (line.length > 0) {
        console.error(`[backend] ${line}`);
      }
    }
  };
  child.stdout?.on("data", sink);
  child.stderr?.on("data", sink);
}

function resolveShellMaintLogPath(): string | null {
  const fromEnv = process.env.LOGOS_REPO_ROOT?.trim();
  if (fromEnv) {
    return path.join(fromEnv, "logs", "maint", "electron-shell.log");
  }
  if (!app.isReady()) {
    return null;
  }
  return path.join(resolveRepoRoot(), "logs", "maint", "electron-shell.log");
}

/** 与 Python Obs 同根：写入 ``<logs_root>/maint/electron-shell.log``，不落系统 userData。 */
function appendShellMaintLog(line: string): void {
  const logPath = resolveShellMaintLogPath();
  if (!logPath) {
    return;
  }
  try {
    mkdirSync(path.dirname(logPath), { recursive: true });
    appendFileSync(logPath, `[${new Date().toISOString()}] ${line}\n`, "utf8");
  } catch {
    // 可选观测：失败不影响主流程
  }
}

function notifyRendererBackendStatus(payload: LogosBackendIpcStatus): void {
  const wins = BrowserWindow.getAllWindows();
  if (wins.length === 0) {
    return;
  }
  for (const w of wins) {
    try {
      w.webContents.send("logos:backend-status", payload);
    } catch {
      // 窗口可能正在销毁
    }
  }
}

function focusPrimaryWindow(): void {
  const w = primaryWindow ?? BrowserWindow.getAllWindows()[0];
  if (!w || w.isDestroyed()) {
    return;
  }
  if (w.isMinimized()) {
    w.restore();
  }
  w.focus();
}

function restartBackoffMs(zeroBasedAttempt: number): number {
  const capped = Math.min(8000, 1000 * 2 ** Math.max(0, zeroBasedAttempt));
  return capped;
}

function isAbnormalBackendExit(code: number | null, signal: NodeJS.Signals | null): boolean {
  if (code === 0) {
    return false;
  }
  if (code !== null && code !== 0) {
    return true;
  }
  return signal != null;
}

async function recoverBackendAfterCrash(repoRoot: string): Promise<void> {
  if (backendRecoveryInFlight) {
    appendShellMaintLog("abnormal exit ignored: recovery already in progress");
    return;
  }
  backendRecoveryInFlight = true;
  try {
    await recoverBackendAfterCrashBody(repoRoot);
  } finally {
    backendRecoveryInFlight = false;
  }
}

async function recoverBackendAfterCrashBody(repoRoot: string): Promise<void> {
  const maxRestarts = readBackendMaxRestarts();
  if (maxRestarts === 0) {
    notifyRendererBackendStatus({
      state: "failed",
      maxAttempts: 0,
      message: "后端进程异常退出；已禁用自动重启（LOGOS_ELECTRON_BACKEND_MAX_RESTARTS=0）。",
    });
    appendShellMaintLog("abnormal exit: auto-restart disabled (MAX=0)");
    return;
  }
  if (backendCrashRestartCount >= maxRestarts) {
    notifyRendererBackendStatus({
      state: "failed",
      attempt: backendCrashRestartCount,
      maxAttempts: maxRestarts,
      message: `后端已连续异常退出超过自动重启上限（${maxRestarts} 次）。请检查日志或重启应用。`,
    });
    appendShellMaintLog(`abnormal exit: exceeded max restarts (${maxRestarts})`);
    return;
  }
  if (appShutdownRequested || backendTerminateRequested) {
    return;
  }

  backendCrashRestartCount += 1;
  const attempt = backendCrashRestartCount;
  notifyRendererBackendStatus({
    state: "recovering",
    attempt,
    maxAttempts: maxRestarts,
    message: "后端进程异常退出，正在按退避策略自动重启…",
  });
  appendShellMaintLog(`abnormal exit: scheduling restart attempt ${attempt}/${maxRestarts}`);

  await new Promise((r) => setTimeout(r, restartBackoffMs(attempt - 1)));
  if (appShutdownRequested || backendTerminateRequested) {
    return;
  }

  startPythonBackend(repoRoot);
  const healthUrl = readBackendHealthUrl();
  const ok = await waitForBackendHealth(healthUrl);
  if (!ok) {
    notifyRendererBackendStatus({
      state: "failed",
      attempt,
      maxAttempts: maxRestarts,
      message: "自动重启后，在约定时间内仍未通过健康检查。",
    });
    appendShellMaintLog(`restart attempt ${attempt}: health gate timed out`);
    backendCrashRestartCount = maxRestarts;
    return;
  }
  notifyRendererBackendStatus({ state: "ready", message: "后端已通过健康检查并恢复。" });
  appendShellMaintLog(`restart attempt ${attempt}: health OK`);
}


function startPythonBackend(repoRoot: string): void {
  if (process.env.LOGOS_ELECTRON_SKIP_BACKEND === "1") {
    console.error(
      "[logos-electron] Skipping embedded backend spawn (LOGOS_ELECTRON_SKIP_BACKEND=1).",
    );
    return;
  }
  if (backendChild !== null && backendChild.exitCode === null) {
    return;
  }

  const script = path.join(repoRoot, "scripts", "run_backend_stub.py");
  const env = { ...process.env, LOGOS_REPO_ROOT: repoRoot };
  const logMode = process.env.LOGOS_ELECTRON_BACKEND_STDIO ?? "prefix";

  const useUv = process.env.LOGOS_BACKEND_USE_UV === "1";
  const stdio =
    logMode === "inherit" ? ("inherit" as const) : logMode === "ignore" ? ("ignore" as const) : ("pipe" as const);

  const baseOpts = {
    cwd: repoRoot,
    env,
    windowsHide: true,
    stdio,
  } as const;

  if (useUv) {
    backendChild = spawn("uv", ["run", "python", script], { ...baseOpts, shell: false });
  } else {
    const py = defaultPythonExecutable(repoRoot);
    backendChild = spawn(py, [script], { ...baseOpts, shell: false });
  }

  const ch = backendChild;
  if (!ch.pid) {
    console.error("[logos-electron] Backend spawn returned no pid.");
    backendChild = null;
    return;
  }
  console.error(`[logos-electron] Backend subprocess started pid=${ch.pid} repoRoot=${repoRoot}`);

  if (stdio === "pipe") {
    wireBackendLogs(ch, logMode);
  }

  ch.on("error", (err) => {
    console.error("[logos-electron] Backend subprocess spawn error:", err);
  });

  ch.on("exit", (code, signal) => {
    console.error(`[logos-electron] Backend subprocess exited code=${code} signal=${signal ?? ""}`);
    if (backendChild === ch) {
      backendChild = null;
    }
    if (backendTerminateRequested) {
      backendTerminateRequested = false;
      return;
    }
    if (appShutdownRequested) {
      return;
    }
    if (!isAbnormalBackendExit(code, signal)) {
      return;
    }
    appendShellMaintLog(`subprocess exit code=${code} signal=${signal ?? ""}`);
    void recoverBackendAfterCrash(repoRoot);
  });
}

function stopPythonBackend(): void {
  const ch = backendChild;
  if (!ch || ch.exitCode !== null) {
    return;
  }
  const pid = ch.pid;
  if (!pid) {
    return;
  }
  backendTerminateRequested = true;
  try {
    if (process.platform === "win32") {
      const r = spawnSync("taskkill", ["/PID", String(pid), "/T", "/F"], {
        windowsHide: true,
        encoding: "utf8",
      });
      const status = r.status ?? -1;
      if (r.error) {
        console.error("[logos-electron] taskkill failed:", r.error);
      } else if (status !== 0 && status !== 128) {
        console.error(
          `[logos-electron] taskkill exited ${status}: ${(r.stderr as string)?.trim() ?? ""}`,
        );
      }
    } else {
      try {
        ch.kill("SIGTERM");
      } catch (killErr) {
        console.error("[logos-electron] SIGTERM on backend subprocess:", killErr);
      }
    }
  } catch (e) {
    console.error("[logos-electron] Failed to terminate backend subprocess:", e);
  }
}

function readGuiDevTarget(): { host: string; port: number } {
  const host = (process.env.LOGOS_GUI_DEV_HOST ?? DEFAULT_GUI_HOST).trim();
  const rawPort = process.env.LOGOS_GUI_DEV_PORT ?? String(DEFAULT_GUI_PORT);
  const port = Number.parseInt(rawPort, 10);
  if (!Number.isFinite(port) || port <= 0 || port > 65535) {
    throw new Error(
      `Invalid LOGOS_GUI_DEV_PORT=${JSON.stringify(rawPort)}: expected integer 1-65535.`,
    );
  }
  return { host, port };
}

function isTcpPortOpen(host: string, port: number, timeoutMs: number): Promise<boolean> {
  return new Promise((resolve) => {
    const socket = net.createConnection({ host, port, allowHalfOpen: true }, () => {
      socket.end();
      resolve(true);
    });
    socket.setTimeout(timeoutMs);
    socket.on("timeout", () => {
      socket.destroy();
      resolve(false);
    });
    socket.on("error", () => {
      resolve(false);
    });
  });
}

async function warnIfDevServerMissing(host: string, port: number): Promise<void> {
  const open = await isTcpPortOpen(host, port, 1200);
  if (open) {
    return;
  }
  const hint = `请先在其他终端运行：cd src/gui && npm run dev\n（默认 ${host}:${port}，与 Vite 一致；代理目标见 VITE_DEV_API_PROXY_TARGET）`;
  console.error(
    `[logos-electron] Vite dev server not reachable at ${host}:${port}. ` +
      `Run: cd src/gui && npm run dev (see VITE_DEV_API_PROXY_TARGET).`,
  );
  await dialog.showMessageBox({
    type: "warning",
    title: "Logos",
    message: "未检测到 Vite 开发服务器",
    detail: hint,
  });
}

function createMainWindow(): BrowserWindow {
  const { host, port } = readGuiDevTarget();
  const devUrl = `http://${host}:${port}/`;

  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    show: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  primaryWindow = win;
  win.on("closed", () => {
    if (primaryWindow === win) {
      primaryWindow = null;
    }
  });

  void (async () => {
    const skipEmbeddedBackend = process.env.LOGOS_ELECTRON_SKIP_BACKEND === "1";

    if (!skipEmbeddedBackend) {
      try {
        await win.loadURL(
          dataUrlHtml(
            "Logos",
            "正在等待后端就绪（轮询 <code>GET /api/v1/health</code>）…",
          ),
        );
      } catch (err) {
        console.error("[logos-electron] loadURL (loading page) failed:", err);
      }

      const healthUrl = readBackendHealthUrl();
      const readyMs = readBackendReadyTimeoutMs();
      console.error(`[logos-electron] Waiting for backend health (timeout ${readyMs} ms): ${healthUrl}`);
      const ok = await waitForBackendHealth(healthUrl);
      if (!ok) {
        const detail =
          `在 ${readyMs} ms 内未收到可用响应：\n${healthUrl}\n\n请查看终端中的 [backend] 日志，或核对端口与 config。`;
        console.error("[logos-electron] Backend health gate timed out.");
        try {
          await win.loadURL(
            dataUrlHtml("后端未就绪", "在约定时间内无法通过健康检查。详见随后弹窗中的说明。"),
          );
        } catch (e) {
          console.error("[logos-electron] loadURL (error page) failed:", e);
        }
        await dialog.showMessageBox(win, {
          type: "error",
          title: "Logos",
          message: "后端在超时内未变为可用",
          detail,
        });
        return;
      }
      backendCrashRestartCount = 0;
      console.error("[logos-electron] Backend health OK.");
    }

    await warnIfDevServerMissing(host, port);
    try {
      await win.loadURL(devUrl);
    } catch (err) {
      console.error("[logos-electron] loadURL failed:", err);
      await dialog.showMessageBox(win, {
        type: "error",
        title: "Logos",
        message: "无法加载开发态 GUI",
        detail: String(err),
      });
    }
  })();

  return win;
}

const hasSingleInstanceLock = app.requestSingleInstanceLock();

if (!hasSingleInstanceLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    focusPrimaryWindow();
  });

  app.whenReady().then(() => {
    const repoRoot = resolveRepoRoot();
    startPythonBackend(repoRoot);
    createMainWindow();
    app.on("activate", () => {
      if (BrowserWindow.getAllWindows().length === 0) {
        createMainWindow();
      }
    });
  });

  app.on("before-quit", () => {
    appShutdownRequested = true;
    stopPythonBackend();
  });

  app.on("will-quit", () => {
    appShutdownRequested = true;
    stopPythonBackend();
  });

  app.on("window-all-closed", () => {
    if (process.platform !== "darwin") {
      stopPythonBackend();
      app.quit();
    }
  });
}
