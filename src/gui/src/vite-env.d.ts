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

declare global {
  interface Window {
    logosElectron?: {
      getApiBase?: () => Promise<string>;
      onBackendStatus?: (cb: (status: LogosBackendIpcStatus) => void) => () => void;
    };
  }
}

export {};
