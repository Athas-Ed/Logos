import { app, BrowserWindow, dialog } from "electron";
import * as net from "net";
import * as path from "path";

const DEFAULT_GUI_HOST = "127.0.0.1";
const DEFAULT_GUI_PORT = 5173;

function readGuiDevTarget(): { host: string; port: number } {
  const host = (process.env.LOGOS_GUI_DEV_HOST ?? DEFAULT_GUI_HOST).trim();
  const rawPort = process.env.LOGOS_GUI_DEV_PORT ?? String(DEFAULT_GUI_PORT);
  const port = Number.parseInt(rawPort, 10);
  if (!Number.isFinite(port) || port <= 0 || port > 65535) {
    throw new Error(
      `无效端口 LOGOS_GUI_DEV_PORT=${JSON.stringify(rawPort)}，须为 1–65535 的整数。`,
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
  console.error(`[logos-electron] 未检测到 Vite 开发服务器（${host}:${port}）。\n${hint}`);
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

  void (async () => {
    await warnIfDevServerMissing(host, port);
    try {
      await win.loadURL(devUrl);
    } catch (err) {
      console.error("[logos-electron] loadURL 失败:", err);
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

app.whenReady().then(() => {
  createMainWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createMainWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
