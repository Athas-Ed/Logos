/// <reference types="vite/client" />

type LogosBackendIpcStatus = {
  state: "recovering" | "ready" | "failed";
  attempt?: number;
  maxAttempts?: number;
  message?: string;
};

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

export type LogosPromoteDryRunResult = {
  ok: boolean;
  exitCode: number;
  stdout: string;
  stderr: string;
  error?: string;
};

export type LogosSimpleIpcResult = { ok: boolean; error?: string };

export type LogosConversationStatus = "idle" | "archived";

export type LogosConversationMeta = {
  id: string;
  title: string;
  status: LogosConversationStatus;
  updated_at: string;
  byte_size: number;
};

export type LogosConversationReadResult =
  | { ok: true; record: Record<string, unknown> }
  | { ok: false; error: string; corrupt: boolean };

declare global {
  // Vite `define` 注入；在模块文件中须通过 global 合并声明供 tsc 识别。
  var __LOGOS_GUI_VERSION__: string;

  interface Window {
    logosElectron?: {
      getApiBase?: () => Promise<string>;
      onBackendStatus?: (cb: (status: LogosBackendIpcStatus) => void) => () => void;
      getDebugInfo?: () => Promise<Record<string, unknown> | null>;
      revealMaintLogsDir?: () => Promise<LogosSimpleIpcResult>;
      openRepoReadme?: () => Promise<LogosSimpleIpcResult>;
      runPromoteDraftDryRun?: (args: {
        workspace: string;
        targetKsfs: string;
      }) => Promise<LogosPromoteDryRunResult>;
      conversations?: {
        list?: () => Promise<LogosConversationMeta[]>;
        read?: (id: string) => Promise<LogosConversationReadResult>;
        write?: (
          id: string,
          payload: Record<string, unknown>,
        ) => Promise<LogosSimpleIpcResult>;
        delete?: (id: string) => Promise<LogosSimpleIpcResult>;
        totalBytes?: () => Promise<number>;
        root?: () => Promise<string>;
      };
    };
  }
}

export {};
