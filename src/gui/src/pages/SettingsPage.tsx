import { useCallback, useEffect, useId, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getApiOrigin } from "../api/apiBase";
import { fetchBootstrap } from "../api/bootstrap";
import {
  fetchDeveloperUi,
  putPromptEcho,
} from "../api/developer";
import { fetchHealth } from "../api/health";
import {
  useConversationActions,
  useConversationMeta,
  useConversationState,
} from "../conversation/ConversationProvider";
import { conversationNavPath } from "../skills/routing";
import {
  persistCacheWarnThresholdBytes,
  resolveEffectiveCacheWarnUi,
} from "../preferences/cacheWarnPrefs";
import {
  PRESENTATION_LABELS,
  persistPresentation,
  readStoredPresentation,
} from "../preferences/chatPrefs";
import {
  type LogProfile,
  type PresentationMode,
} from "../types/chat";
import {
  BOOTSTRAP_UI_DEFAULTS,
  resolveBootstrapUi,
  type BootstrapUi,
} from "../types/bootstrap";
import { applyGuiTheme, readThemeChoice, type GuiThemeChoice } from "../theme";
import {
  type LlmProvider,
  PROVIDER_TEMPLATES,
  detectProvider,
  putLlmApiKey,
} from "../api/config";
import styles from "./SettingsPage.module.css";

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

function normalizeLogProfile(raw: string): LogProfile | null {
  const s = raw.trim().toLowerCase();
  if (
    s === "minimal" ||
    s === "standard" ||
    s === "verbose" ||
    s === "audit"
  ) {
    return s;
  }
  return null;
}

const BYTES_PER_MB = 1024 * 1024;

export function SettingsPage() {
  const titleId = useId();
  const navigate = useNavigate();
  const convActions = useConversationActions();
  const convMeta = useConversationMeta();
  const lastOpenTabId =
    convMeta.openTabIds.length > 0
      ? convMeta.openTabIds[convMeta.openTabIds.length - 1]
      : undefined;
  const lastOpenConv = useConversationState(lastOpenTabId ?? "");
  const settingsBackPath = useMemo(() => {
    if (!convMeta.ready || convMeta.openTabIds.length === 0) {
      return "/";
    }
    if (lastOpenConv) {
      return conversationNavPath(lastOpenConv);
    }
    return `/chat/${lastOpenTabId}`;
  }, [
    convMeta.openTabIds.length,
    convMeta.ready,
    lastOpenConv,
    lastOpenTabId,
  ]);
  const [healthOk, setHealthOk] = useState<boolean | null>(null);
  const [logProfile, setLogProfile] = useState<LogProfile | null>(null);
  const [obsShowLogRootInGui, setObsShowLogRootInGui] = useState(false);
  const [obsLogsRoot, setObsLogsRoot] = useState<string | null>(null);
  const [theme, setTheme] = useState<GuiThemeChoice>(() => readThemeChoice());
  const [debugInfo, setDebugInfo] = useState<LogosDebugInfo | null>(null);
  const [workspace, setWorkspace] = useState("");
  const [targetKsfs, setTargetKsfs] = useState("");
  const [dryBusy, setDryBusy] = useState(false);
  const [dryOut, setDryOut] = useState<string | null>(null);
  const [dryErr, setDryErr] = useState<string | null>(null);
  const [copyHint, setCopyHint] = useState<string | null>(null);
  const [uiLimits, setUiLimits] = useState<BootstrapUi>(BOOTSTRAP_UI_DEFAULTS);
  const [presentation, setPresentation] = useState<PresentationMode>(
    () => readStoredPresentation() ?? "work",
  );
  const [devUi, setDevUi] = useState<{
    show: boolean;
    promptEcho: boolean;
  } | null>(null);
  const [devToggleBusy, setDevToggleBusy] = useState(false);

  // ── LLM 服务配置 ────────────────────────────────────────────────
  const [llmMode, setLlmMode] = useState<string>("");
  const [llmError, setLlmError] = useState<string>("");
  const [llmProvider, setLlmProvider] = useState<LlmProvider>("deepseek");
  const [llmApiKey, setLlmApiKey] = useState("");
  const [llmBaseUrl, setLlmBaseUrl] = useState(PROVIDER_TEMPLATES["deepseek"].base_url);
  const [llmModel, setLlmModel] = useState(PROVIDER_TEMPLATES["deepseek"].model);
  const [llmBusy, setLlmBusy] = useState(false);
  const [llmResult, setLlmResult] = useState<string | null>(null);
  const [llmResultOk, setLlmResultOk] = useState(false);

  const refreshHealth = useCallback(async () => {
    setHealthOk(await fetchHealth());
  }, []);

  useEffect(() => {
    applyGuiTheme(readThemeChoice());
    setTheme(readThemeChoice());
    void refreshHealth();
    void (async () => {
      const b = await fetchBootstrap();
      if (b) {
        setLlmMode(b.llm_mode ?? "");
        setLlmError(b.llm_error ?? "");
        const lp = normalizeLogProfile(b.log_profile);
        if (lp) setLogProfile(lp);
        setObsShowLogRootInGui(Boolean(b.obs_show_log_root_in_gui));
        setObsLogsRoot(
          b.obs_show_log_root_in_gui &&
            typeof b.obs_logs_root === "string" &&
            b.obs_logs_root.length > 0
            ? b.obs_logs_root
            : null,
        );
        setUiLimits(resolveEffectiveCacheWarnUi(resolveBootstrapUi(b.ui)));
        const storedPres = readStoredPresentation();
        const pres = storedPres ?? b.default_presentation;
        setPresentation(pres);
        if (!storedPres) persistPresentation(pres);
      }
    })();
    void (async () => {
      const s = await fetchDeveloperUi();
      if (!s?.show_dev_tools_ui) {
        setDevUi(null);
        return;
      }
      setDevUi({ show: true, promptEcho: s.prompt_echo });
    })();
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
  }, [refreshHealth]);

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

  const applyPresentation = useCallback(
    (mode: PresentationMode) => {
      setPresentation(mode);
      persistPresentation(mode);
      if (!convMeta.ready) {
        return;
      }
      for (const id of convMeta.openTabIds) {
        convActions.patchConversation(id, { presentation: mode });
      }
    },
    [convActions, convMeta.openTabIds, convMeta.ready],
  );

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

  /* ── LLM 服务：测试并保存 API Key ──────────────────────────── */
  const handleLlmTest = useCallback(async () => {
    const key = llmApiKey.trim();
    if (!key) {
      setLlmResult("请输入 API Key");
      setLlmResultOk(false);
      return;
    }
    setLlmBusy(true);
    setLlmResult(null);
    try {
      const resp = await putLlmApiKey(
        {
          provider: llmProvider,
          api_key: key,
          base_url: llmBaseUrl.trim() || PROVIDER_TEMPLATES[llmProvider].base_url,
          model: llmModel.trim() || PROVIDER_TEMPLATES[llmProvider].model,
        },
      );
      if (!resp) {
        setLlmResult("网络错误，无法连接到后端");
        setLlmResultOk(false);
        return;
      }
      if (resp.success) {
        setLlmMode("remote");
        setLlmError("");
        setLlmResult(resp.detail || "LLM 配置已更新");
        setLlmResultOk(true);
      } else {
        setLlmResult(resp.detail || "验证失败");
        setLlmResultOk(false);
      }
    } catch {
      setLlmResult("提交时发生异常");
      setLlmResultOk(false);
    } finally {
      setLlmBusy(false);
    }
  }, [llmApiKey, llmBaseUrl, llmModel, llmProvider]);

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 id={titleId} className={styles.title}>
          设置与诊断
        </h1>
        <Link className={styles.backLink} to={settingsBackPath}>
          返回
        </Link>
      </header>

      <div className={styles.body}>
        <section className={styles.section} aria-labelledby={`${titleId}-chat`}>
          <h2 id={`${titleId}-chat`} className={styles.sectionTitle}>
            对话与推理
          </h2>
          <p className={styles.muted}>
            写入本机偏好并同步到当前已打开的标签页；新会话默认沿用此处选项。展示档位控制
            SSE 中 LLM 推理过程为摘要或全文（见 SPEC-DISPLAY-AND-LOGGING）。
          </p>
          <div className={styles.field}>
            <span className={styles.fieldLabel}>运行模式</span>
            <span className={styles.fieldLabel}>作者模式</span>
          </div>
          <div className={styles.field}>
            <label className={styles.fieldLabel} htmlFor={`${titleId}-pres`}>
              展示档位（LLM 推理过程）
            </label>
            <select
              id={`${titleId}-pres`}
              className={styles.select}
              data-testid="settings-presentation"
              value={presentation}
              onChange={(e) =>
                applyPresentation(e.target.value as PresentationMode)
              }
            >
              {(Object.keys(PRESENTATION_LABELS) as PresentationMode[]).map(
                (m) => (
                  <option key={m} value={m}>
                    {PRESENTATION_LABELS[m]}
                  </option>
                ),
              )}
            </select>
          </div>
          {devUi?.show ? (
            <label
              className={styles.row}
              title="不调用 LLM，将完整 Prompt 作为助手答复（检视 CB 拼装）"
            >
              <input
                type="checkbox"
                data-testid="settings-prompt-echo"
                checked={devUi.promptEcho}
                disabled={devToggleBusy}
                onChange={(e) => {
                  const on = e.target.checked;
                  setDevToggleBusy(true);
                  void (async () => {
                    const ok = await putPromptEcho(on);
                    if (ok) {
                      setDevUi((prev) =>
                        prev ? { ...prev, promptEcho: on } : prev,
                      );
                    }
                    setDevToggleBusy(false);
                  })();
                }}
              />
              <span className={styles.fieldLabel}>Prompt 回显（开发者）</span>
            </label>
          ) : null}
        </section>

        <section className={styles.section} aria-labelledby={`${titleId}-llm`}>
          <h2 id={`${titleId}-llm`} className={styles.sectionTitle}>
            LLM 服务
          </h2>
          <p className={styles.muted}>
            当前模式：<strong>{llmMode === "remote" ? "远程" : "桩后端"}</strong>
            {llmError ? (
              <span style={{ color: "var(--err)" }}> · ⚠️ {llmError}</span>
            ) : null}
          </p>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>LLM 提供商</span>
            <select
              className={styles.select}
              value={llmProvider}
              onChange={(e) => {
                const p = e.target.value as LlmProvider;
                setLlmProvider(p);
                setLlmResult(null);
              }}
              disabled={llmBusy}
            >
              {(Object.keys(PROVIDER_TEMPLATES) as LlmProvider[]).map(
                (p) => (
                  <option key={p} value={p}>
                    {PROVIDER_TEMPLATES[p].label}
                  </option>
                ),
              )}
            </select>
          </label>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>API Key</span>
            <input
              className={styles.input}
              type="password"
              autoComplete="off"
              placeholder={llmProvider === "anthropic" ? "sk-ant-..." : "sk-..."}
              value={llmApiKey}
              onChange={(e) => {
                const val = e.target.value;
                setLlmApiKey(val);
                setLlmResult(null);
                const detected = detectProvider(val);
                if (detected && detected !== llmProvider) {
                  setLlmProvider(detected);
                }
              }}
              disabled={llmBusy}
            />
          </label>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Base URL</span>
            <input
              className={styles.input}
              type="url"
              autoComplete="off"
              value={llmBaseUrl}
              onChange={(e) => {
                setLlmBaseUrl(e.target.value);
                setLlmResult(null);
              }}
              disabled={llmBusy}
            />
          </label>
          <label className={styles.field}>
            <span className={styles.fieldLabel}>模型</span>
            <input
              className={styles.input}
              type="text"
              autoComplete="off"
              value={llmModel}
              onChange={(e) => {
                setLlmModel(e.target.value);
                setLlmResult(null);
              }}
              disabled={llmBusy}
            />
          </label>
          <div className={styles.row}>
            <button
              type="button"
              className={styles.primaryBtn}
              disabled={llmBusy || !llmApiKey.trim()}
              onClick={() => void handleLlmTest()}
            >
              {llmBusy ? "验证中…" : "检查并启用"}
            </button>
          </div>
          {llmResult ? (
            <p
              className={styles.muted}
              style={{ color: llmResultOk ? "var(--ok)" : "var(--err)" }}
            >
              {llmResult}
            </p>
          ) : null}
        </section>

        <section className={styles.section} aria-labelledby={`${titleId}-ui`}>
          <h2 id={`${titleId}-ui`} className={styles.sectionTitle}>
            GUI 限制（G2）
          </h2>
          <div className={styles.field}>
            <label className={styles.fieldLabel} htmlFor={`${titleId}-sse`}>
              SSE_maxNum（后台并发上限）
            </label>
            <input
              id={`${titleId}-sse`}
              className={styles.input}
              type="number"
              min={1}
              readOnly
              value={uiLimits.SSE_maxNum}
            />
          </div>
          <div className={styles.field}>
            <label className={styles.fieldLabel} htmlFor={`${titleId}-cache-mb`}>
              缓存告警阈值（MB）
            </label>
            <input
              id={`${titleId}-cache-mb`}
              className={styles.input}
              type="number"
              min={0}
              step={1}
              data-testid="cache-warn-mb-input"
              value={Math.round(uiLimits.cache_warn_bytes / BYTES_PER_MB)}
              onChange={(e) => {
                const mb = Number.parseFloat(e.target.value);
                if (!Number.isFinite(mb) || mb < 0) {
                  return;
                }
                const bytes = Math.round(mb * BYTES_PER_MB);
                setUiLimits((prev) => ({
                  ...prev,
                  cache_warn_bytes: bytes,
                }));
                persistCacheWarnThresholdBytes(bytes);
              }}
            />
          </div>
          <p className={styles.muted}>
            对应配置项 <code className={styles.mono}>ui.cache_warn_bytes</code>
            ，当前 {uiLimits.cache_warn_bytes.toLocaleString()} 字节。
          </p>
        </section>

        <section className={styles.section} aria-labelledby={`${titleId}-cache`}>
          <h2 id={`${titleId}-cache`} className={styles.sectionTitle}>
            会话缓存
          </h2>
          <p className={styles.muted}>
            归档任务保存在 Electron 用户数据目录；可在「已归档会话」页查看列表与路径说明。
          </p>
          <button
            type="button"
            className={styles.primaryBtn}
            data-testid="archived-sessions-btn"
            onClick={() => navigate("/cache")}
          >
            已归档会话
          </button>
        </section>
        <section className={styles.section} aria-labelledby={`${titleId}-g1`}>
          <h2 id={`${titleId}-g1`} className={styles.sectionTitle}>
            版本与健康（G1）
          </h2>
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
              {healthOk === null ? "未检测" : healthOk ? "正常" : "异常"}
            </span>
            <button
              type="button"
              className={styles.ghostBtn}
              onClick={() => void refreshHealth()}
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
            <p className={styles.muted}>覆盖系统偏好后写入本机 localStorage。</p>
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
  );
}
