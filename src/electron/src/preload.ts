import { contextBridge, ipcRenderer } from "electron";

export type LogosBackendIpcStatus = {
  state: "recovering" | "ready" | "failed";
  attempt?: number;
  maxAttempts?: number;
  message?: string;
};

/**
 * 窄 IPC：与 `GUI开发文档.md` §2.3、§3 对齐；Renderer 通过 `getApiBase`（打包态）与 `onBackendStatus` 与 Main 协同。
 */
contextBridge.exposeInMainWorld("logosElectron", {
  getApiBase(): Promise<string> {
    return ipcRenderer.invoke("logos:get-api-base");
  },
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
