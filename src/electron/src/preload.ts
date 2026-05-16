import { contextBridge, ipcRenderer } from "electron";

export type LogosBackendIpcStatus = {
  state: "recovering" | "ready" | "failed";
  attempt?: number;
  maxAttempts?: number;
  message?: string;
};

export type LogosSimpleIpcResult = { ok: boolean; error?: string };

export type LogosPromoteDryRunResult = {
  ok: boolean;
  exitCode: number;
  stdout: string;
  stderr: string;
  error?: string;
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
  getDebugInfo(): Promise<Record<string, unknown> | null> {
    return ipcRenderer.invoke("logos:get-debug-info");
  },
  revealMaintLogsDir(): Promise<LogosSimpleIpcResult> {
    return ipcRenderer.invoke("logos:reveal-maint-logs-dir");
  },
  openRepoReadme(): Promise<LogosSimpleIpcResult> {
    return ipcRenderer.invoke("logos:open-repo-readme");
  },
  runPromoteDraftDryRun(args: {
    workspace: string;
    targetKsfs: string;
  }): Promise<LogosPromoteDryRunResult> {
    return ipcRenderer.invoke("logos:run-promote-draft-dry-run", args);
  },
});
