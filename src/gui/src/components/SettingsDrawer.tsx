import { useCallback, useEffect, useId, useRef, useState } from "react";
import { getApiOrigin } from "../api/apiBase";
import { fetchHealth } from "../api/health";
import type { LogProfile } from "../types/chat";
import styles from "./SettingsDrawer.module.css";

const THEME_KEY = "logos_gui_theme";
export type GuiThemeChoice = "system" | "light" | "dark";

export function readThemeChoice(): GuiThemeChoice {
  try {
    const raw = localStorage.getItem(THEME_KEY);
    if (raw === "light" || raw === "dark" || raw === "system") {
      return raw;
    }
  } catch {
    /* ignore */
  }
  return "system";
}

export function applyGuiTheme(choice: GuiThemeChoice): void {
  const root = document.documentElement;
  if (choice === "system") {
    root.removeAttribute("data-theme");
  } else {
    root.setAttribute("data-theme", choice);
  }
  try {
    localStorage.setItem(THEME_KEY, choice);
  } catch {
    /* ignore */
  }
}

export type LogosDebugInfo = {
  logos_electron: string;
  logos_gui: string;
  electron: string;
  chrome: string;
  node: string;
  packaged: boolean;
  repo_root: string;
  shell_maint_log: string | null;
  api_base: string;
  backend_health_url: string;
  platform: string;
};

type Props = {
  open: boolean;
  onClose: () => void;
  healthOk: boolean | null;
  onRefreshHealth: () => void;
  logProfile: LogProfile | null;
  /** 配置 `obs.show_log_root_in_gui`；默认 false */
  obsShowLogRootInGui: boolean;
  /** 仅当上一项为 true 且后端给出路径时非 null */
  obsLogsRoot: string | null;
};

export function SettingsDrawer({
  open,
  onClose,
  healthOk,
  onRefreshHealth,
  logProfile,
  obsShowLogRootInGui,
  obsLogsRoot,
}: Props) {
  const titleId = useId();
  const closeBtnRef = useRef<HTMLButtonElement | null>(null);
  const [theme, setTheme] = useState<GuiThemeChoice>(() => readThemeChoice());
  const [debugInfo, setDebugInfo] = useState<LogosDebugInfo | null>(null);
  const [workspace, setWorkspace] = useState("");
  const [targetKsfs, setTargetKsfs] = useState("");
  const [dryBusy, setDryBusy] = useState(false);
  const [dryOut, setDryOut] = useState<string | null>(null);
  const [dryErr, setDryErr] = useState<string | null>(null);
  const [copyHint, setCopyHint] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    applyGuiTheme(readThemeChoice());
    setTheme(readThemeChoice());
    setDryOut(null);
    setDryErr(null);
    setCopyHint(null);
    void (async () => {
      const bridge = window.logosElectron?.getDebugInfo;
      if (!bridge) {
        setDebugInfo(null);
        return;
      }
      try {
        const j = (await bridge()) as LogosDebugInfo | null;
        setDebugInfo(j);
        if (j?.repo_root) {
          setWorkspace((w) => (w.trim() ? w : j.repo_root));
        }
      } catch {
        setDebugInfo(null);
      }
    })();
    const t = window.setTimeout(() => closeBtnRef.current?.focus(), 0);
    return () => window.clearTimeout(t);
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const copyText = useCallback(async (label: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopyHint(`已复制：${label}`);
      window.setTimeout(() => setCopyHint(null), 2400);
    } catch {
      setCopyHint("复制失败（浏览器权限）");
      window.setTimeout(() => setCopyHint(null), 2400);
    }
  }, []);

  const buildCliCommand = useCallback(
    (dryRun: boolean) => {
      const ws = workspace.trim() || "<WORKSPACE>";
      const ks = targetKsfs.trim() || "<KSFS_ROOT>";
      const flag = dryRun ? "--dry-run" : "--apply";
      return `python -m logos.tools.promote_draft --workspace "${ws}" --target-ksfs "${ks}" ${flag}`;
    },
    [workspace, targetKsfs],
  );

  const copyDebugBundle = useCallback(async () => {
    const api = getApiOrigin() || "(相对 /api，走 Vite 代理或同源)";
    const healthProbe = await fetchHealth();
    const lines = [
      `logos-gui ${__LOGOS_GUI_VERSION__}`,
      `health_probe: ${healthProbe ? "ok" : "fail"}`,
      `health_indicator: ${healthOk === null ? "unknown" : healthOk ? "ok" : "bad"}`,
      `log_profile: ${logProfile ?? "unknown"}`,
      `api_origin: ${api}`,
      `userAgent: ${navigator.userAgent}`,
    ];
    if (obsShowLogRootInGui && obsLogsRoot) {
      lines.push(`obs_logs_root: ${obsLogsRoot}`);
    }
    if (debugInfo) {
      lines.push(
        "--- electron ---",
        `logos-electron ${debugInfo.logos_electron}`,
        `packaged: ${String(debugInfo.packaged)}`,
        `repo_root: ${debugInfo.repo_root}`,
        `shell_maint_log: ${debugInfo.shell_maint_log ?? "(未就绪)"}`,
        `api_base: ${debugInfo.api_base || "(dev 代理)"}`,
        `backend_health_url: ${debugInfo.backend_health_url}`,
        `platform: ${debugInfo.platform}`,
        `electron: ${debugInfo.electron} chrome: ${debugInfo.chrome} node: ${debugInfo.node}`,
      );
    }
    await copyText("调试摘要", lines.join("\n"));
  }, [copyText, debugInfo, healthOk, logProfile, obsLogsRoot, obsShowLogRootInGui]);

  const runDryRun = useCallback(async () => {
    const bridge = window.logosElectron?.runPromoteDraftDryRun;
    if (!bridge) {
      setDryErr("当前为浏览器模式：请在桌面壳内使用 dry-run，或于终端执行下方命令。");
      setDryOut(null);
      return;
    }
    setDryBusy(true);
    setDryErr(null);
    setDryOut(null);
    try {
      const r = await bridge({
        workspace: workspace.trim(),
        targetKsfs: targetKsfs.trim(),
      });
      if (r.stdout) {
        setDryOut(r.stdout);
      }
      const errParts = [r.stderr, r.error].filter(Boolean).join("\n");
      if (!r.ok) {
        setDryErr(errParts || `进程退出码 ${r.exitCode}`);
      } else if (errParts.trim()) {
        setDryErr(errParts);
      }
    } catch (e) {
      setDryErr(e instanceof Error ? e.message : String(e));
    } finally {
      setDryBusy(false);
    }
  }, [targetKsfs, workspace]);

  const revealLogs = useCallback(async () => {
    const fn = window.logosElectron?.revealMaintLogsDir;
    if (!fn) {
      setCopyHint("浏览器环境请手动打开仓库下 logs/maint/");
      window.setTimeout(() => setCopyHint(null), 2800);
      return;
    }
    const r = await fn();
    if (!r.ok) {
      setCopyHint(r.error ?? "无法打开目录");
      window.setTimeout(() => setCopyHint(null), 2800);
    }
  }, []);

  const openReadme = useCallback(async () => {
    const fn = window.logosElectron?.openRepoReadme;
    if (!fn) {
      setCopyHint("请在仓库根目录用编辑器打开 README.md");
      window.setTimeout(() => setCopyHint(null), 2800);
      return;
    }
    const r = await fn();
    if (!r.ok) {
      setCopyHint(r.error ?? "无法打开 README");
      window.setTimeout(() => setCopyHint(null), 2800);
    }
  }, []);

  if (!open) {
    return null;
  }

  return (
    <div
      className={styles.backdrop}
      role="presentation"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) {
          onClose();
        }
      }}
    >
      <div
        className={styles.panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className={styles.header}>
          <h2 id={titleId} className={styles.title}>
            设置与诊断
          </h2>
          <button
            ref={closeBtnRef}
            type="button"
            className={styles.closeBtn}
            onClick={onClose}
          >
            关闭
          </button>
        </div>
        <div className={styles.body}>
          <section className={styles.section} aria-labelledby={`${titleId}-g1`}>
            <h3 id={`${titleId}-g1`} className={styles.sectionTitle}>
              版本与健康（G1）
            </h3>
            <p className={styles.muted}>
              前端包版本{" "}
              <span className={styles.mono}>{__LOGOS_GUI_VERSION__}</span>
              {debugInfo ? (
                <>
                  {" "}
                  · 壳{" "}
                  <span className={styles.mono}>{debugInfo.logos_electron}</span>
                </>
              ) : null}
            </p>
            <div className={styles.row}>
              <span className={styles.muted}>
                健康指示：{" "}
                {healthOk === null
                  ? "未检测"
                  : healthOk
                    ? "正常"
                    : "异常"}
              </span>
              <button
                type="button"
                className={styles.ghostBtn}
                onClick={() => void onRefreshHealth()}
              >
                重新检测
              </button>
            </div>
            <p className={styles.muted}>
              Python 观测日志与壳层维护日志约定见{" "}
              <code className={styles.mono}>logs/maint/</code>（与{" "}
              <code className={styles.mono}>electron-shell.log</code> 同目录树，详
              GUI/Obs 文档）。是否展示**解析后的日志根绝对路径**由配置{" "}
              <code className={styles.mono}>obs.show_log_root_in_gui</code>{" "}
              控制（默认关闭，Obs O4）。
            </p>
            {obsShowLogRootInGui && obsLogsRoot ? (
              <div
                className={styles.o4Block}
                role="group"
                aria-labelledby={`${titleId}-o4`}
              >
                <h3 id={`${titleId}-o4`} className={styles.sectionTitle}>
                  Obs 日志根（O4）
                </h3>
                <p className={styles.mono}>{obsLogsRoot}</p>
                <div className={styles.row}>
                  <button
                    type="button"
                    className={styles.ghostBtn}
                    onClick={() =>
                      void copyText("obs_logs_root", obsLogsRoot)
                    }
                  >
                    复制日志根路径
                  </button>
                </div>
              </div>
            ) : null}
            <div className={styles.row}>
              <button
                type="button"
                className={styles.primaryBtn}
                onClick={() => void copyDebugBundle()}
              >
                复制调试信息
              </button>
              <button
                type="button"
                className={styles.ghostBtn}
                onClick={() => void revealLogs()}
              >
                打开 maint 日志目录
              </button>
              <button
                type="button"
                className={styles.ghostBtn}
                onClick={() => void openReadme()}
              >
                打开仓库 README
              </button>
            </div>
            {copyHint ? <p className={styles.muted}>{copyHint}</p> : null}
          </section>

          <section className={styles.section} aria-labelledby={`${titleId}-g2`}>
            <h3 id={`${titleId}-g2`} className={styles.sectionTitle}>
              内容安全策略（G2）
            </h3>
            <p className={styles.muted}>
              打包态 Electron 为 file:// 加载的 GUI 注入 CSP：script-src
              &apos;self&apos;、connect-src 仅允许当前配置的后端 origin（与 preload
              getApiBase 对齐）。开发态 Vite 不注入该头，以免阻碍 HMR。
            </p>
          </section>

          <section className={styles.section} aria-labelledby={`${titleId}-g3`}>
            <h3 id={`${titleId}-g3`} className={styles.sectionTitle}>
              外观（G3）
            </h3>
            <div className={styles.row}>
              <label className={styles.fieldLabel} htmlFor={`${titleId}-theme`}>
                主题
              </label>
              <select
                id={`${titleId}-theme`}
                className={styles.select}
                value={theme}
                onChange={(e) => {
                  const v = e.target.value as GuiThemeChoice;
                  setTheme(v);
                  applyGuiTheme(v);
                }}
              >
                <option value="system">跟随系统</option>
                <option value="light">浅色</option>
                <option value="dark">深色</option>
              </select>
            </div>
            <p className={styles.muted}>
              覆盖系统偏好后写入本机 localStorage；键盘可用 Tab
              聚焦关闭按钮与各控件。
            </p>
          </section>

          <section className={styles.section} aria-labelledby={`${titleId}-g4`}>
            <h3 id={`${titleId}-g4`} className={styles.sectionTitle}>
              草稿晋升 CLI（G4）
            </h3>
            <p className={styles.muted}>
              业务仍以{" "}
              <code className={styles.mono}>python -m logos.tools.promote_draft</code>{" "}
              为真源；此处仅组装参数或经壳层 IPC 执行 dry-run。
            </p>
            <div className={styles.field}>
              <label className={styles.fieldLabel} htmlFor={`${titleId}-ws`}>
                --workspace
              </label>
              <input
                id={`${titleId}-ws`}
                className={styles.input}
                autoComplete="off"
                value={workspace}
                onChange={(e) => setWorkspace(e.target.value)}
                placeholder="工作空间根目录"
              />
            </div>
            <div className={styles.field}>
              <label className={styles.fieldLabel} htmlFor={`${titleId}-ks`}>
                --target-ksfs
              </label>
              <input
                id={`${titleId}-ks`}
                className={styles.input}
                autoComplete="off"
                value={targetKsfs}
                onChange={(e) => setTargetKsfs(e.target.value)}
                placeholder="KSFS 根目录（paths.ksfs_root）"
              />
            </div>
            <div className={styles.row}>
              <button
                type="button"
                className={styles.ghostBtn}
                onClick={() => void copyText("dry-run 命令", buildCliCommand(true))}
              >
                复制 dry-run 命令
              </button>
              <button
                type="button"
                className={styles.ghostBtn}
                onClick={() => void copyText("apply 命令", buildCliCommand(false))}
              >
                复制 apply 命令
              </button>
              <button
                type="button"
                className={styles.primaryBtn}
                disabled={dryBusy || !workspace.trim() || !targetKsfs.trim()}
                onClick={() => void runDryRun()}
              >
                {dryBusy ? "执行中…" : "在壳内 dry-run"}
              </button>
            </div>
            {dryErr ? <p className={styles.err}>{dryErr}</p> : null}
            {dryOut ? <pre className={styles.output}>{dryOut}</pre> : null}
          </section>
        </div>
      </div>
    </div>
  );
}
