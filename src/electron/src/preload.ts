import { contextBridge, ipcRenderer } from "electron";

export type LogosBackendIpcStatus = {
  state: "recovering" | "ready" | "failed";
  attempt?: number;
  maxAttempts?: number;
  message?: string;
};

/**
 * 窄 IPC：与 `GUI开发文档.md` §2.3、第三阶段步 6 对齐；Renderer 仅订阅 Main 推送的状态。
 */
contextBridge.exposeInMainWorld("logosElectron", {
  onBackendStatus(cb: (status: LogosBackendIpcStatus) => void): () => void {
    const channel = "logos:backend-status";
    const handler = (_evt: unknown, payload: LogosBackendIpcStatus) => {
      cb(payload);
    };
    ipcRenderer.on(channel, handler);
    return () => {
      ipcRenderer.removeListener(channel, handler);
    };
  },
});
