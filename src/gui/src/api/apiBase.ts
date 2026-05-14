/** 在 `main.tsx` 中须先于 React 树调用一次 `initApiBase`。 */
let resolvedBase: string | null = null;

export async function initApiBase(): Promise<void> {
  if (resolvedBase !== null) {
    return;
  }
  const bridge = window.logosElectron?.getApiBase;
  if (bridge) {
    resolvedBase = (await bridge()).trim();
    return;
  }
  const envBase = import.meta.env.VITE_API_BASE?.trim();
  resolvedBase = envBase ?? "";
}

/** 空字符串表示使用相对路径（浏览器开发或 Electron 开发 + Vite 代理）。 */
export function getApiOrigin(): string {
  return resolvedBase ?? "";
}

export function apiUrl(path: string): string {
  const base = resolvedBase ?? "";
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  if (!base) {
    return normalizedPath;
  }
  return `${base.replace(/\/$/, "")}${normalizedPath}`;
}
