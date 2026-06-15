import { useCallback, useEffect, useId, useRef, useState } from "react";
import type { LlmMode } from "../api/bootstrap";
import { fetchBootstrap } from "../api/bootstrap";
import {
  type LlmProvider,
  PROVIDER_TEMPLATES,
  detectProvider,
  putLlmApiKey,
} from "../api/config";
import styles from "./LlmSetupDialog.module.css";

/**
 * 启动时检测 LLM 配置。
 *
 * 若 ``GET /api/v1/bootstrap`` 返回 ``llm_mode === "stub"``，
 * 弹出对话框引导用户输入 API Key 体验完整功能，或跳过使用桩模式。
 */
export function LlmSetupDialog() {
  const titleId = useId();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  // llmMode 不直接用于渲染，setLlmMode 用于提交成功后标记状态
  const setLlmMode = useState<LlmMode | null>(null)[1];
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [bootstrapError, setBootstrapError] = useState<string | null>(null);

  // 表单字段
  const [provider, setProvider] = useState<LlmProvider>("deepseek");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState(
    PROVIDER_TEMPLATES["deepseek"].base_url,
  );
  const [model, setModel] = useState(PROVIDER_TEMPLATES["deepseek"].model);

  const inputRef = useRef<HTMLInputElement>(null);
  const successTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  /* 切换提供商：自动填入 base_url + model */
  const changeProvider = useCallback((p: LlmProvider) => {
    setProvider(p);
    const tpl = PROVIDER_TEMPLATES[p];
    setBaseUrl(tpl.base_url);
    setModel(tpl.model);
    setError(null);
  }, []);

  /* 输入 API Key 时自动识别提供商 */
  const handleKeyChange = useCallback(
    (value: string) => {
      setApiKey(value);
      const detected = detectProvider(value);
      if (detected && detected !== provider) {
        // sk-ant- → Anthropic, sk-proj- → OpenAI
        changeProvider(detected);
      }
    },
    [provider, changeProvider],
  );

  /* 初始检查：bootstrap 返回 stub 则弹窗 */
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const b = await fetchBootstrap();
      if (cancelled) return;
      if (b?.llm_mode === "stub") {
        setLlmMode("stub");
        if (b.llm_error) setBootstrapError(b.llm_error);
        setOpen(true);
        /* 自动聚焦输入框 */
        requestAnimationFrame(() => inputRef.current?.focus());
      } else if (b?.llm_mode) {
        setLlmMode(b.llm_mode);
      }
    })();
    return () => {
      cancelled = true;
      if (successTimer.current) clearTimeout(successTimer.current);
      if (abortRef.current) abortRef.current.abort();
    };
  }, []);

  /* 关闭对话框 */
  const dismiss = useCallback(() => {
    if (busy) return; // 提交中不可关闭
    setOpen(false);
    setError(null);
    setSuccessMsg(null);
    setBootstrapError(null);
  }, [busy]);

  /* 提交 API Key */
  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      const key = apiKey.trim();
      if (!key) {
        setError("请输入 API Key");
        return;
      }
      setBusy(true);
      setError(null);
      setSuccessMsg(null);

      // 前端 15s 超时保护（后端验证已有 10s 超时）
      const controller = new AbortController();
      abortRef.current = controller;
      const timeoutId = setTimeout(() => controller.abort(), 15_000);

      try {
        const resp = await putLlmApiKey(
          {
            provider,
            api_key: key,
            base_url: baseUrl.trim() || "https://api.deepseek.com/v1",
            model: model.trim() || "deepseek-chat",
          },
          controller.signal,
        );
        clearTimeout(timeoutId);
        if (abortRef.current === controller) abortRef.current = null;

        if (!resp) {
          setError("网络错误，无法连接到后端");
          return;
        }
        if (resp.success) {
          setSuccessMsg(resp.detail || "LLM 配置已生效");
          setLlmMode("remote");
          // 短暂展示成功状态后关闭
          successTimer.current = setTimeout(() => setOpen(false), 1200);
        } else {
          setError(resp.detail || "配置失败，请检查输入");
        }
      } catch (err) {
        clearTimeout(timeoutId);
        if (abortRef.current === controller) abortRef.current = null;
        if (err instanceof DOMException && err.name === "AbortError") {
          setError("连接超时，请检查网络或 Base URL 是否正确");
        } else {
          setError("提交时发生异常");
        }
      } finally {
        setBusy(false);
      }
    },
    [apiKey, baseUrl, model, provider],
  );

  if (!open) return null;

  return (
    <div
      className={styles.backdrop}
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      data-testid="llm-setup-dialog"
      onClick={busy ? undefined : dismiss}
      onKeyDown={(e) => {
        if (e.key === "Escape" && !busy) dismiss();
      }}
    >
      <div
        className={styles.panel}
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => e.stopPropagation()}
      >
        <h2 id={titleId} className={styles.title}>
          {successMsg ? "🎉 配置成功" : "🔑 LLM 未配置"}
        </h2>

        {successMsg ? (
          <>
            <p className={styles.body}>{successMsg}</p>
            <div className={styles.actions}>
              <button
                type="button"
                className={styles.primaryBtn}
                onClick={() => setOpen(false)}
              >
                开始体验
              </button>
            </div>
          </>
        ) : (
          <form onSubmit={handleSubmit}>
            <p className={styles.body}>
              当前为<strong>桩后端模式</strong>（Prompt 回显），可浏览界面但
              LLM 不会真正推理。输入 API Key 以启用完整功能：
            </p>

            {bootstrapError ? (
              <p className={styles.error} role="alert">
                ⚠️ 当前 Key 无效：{bootstrapError}
              </p>
            ) : null}

            <p className={styles.body}>
              💡 如现在跳过，可在<strong>设置页面</strong>填写 API Key 并验证可用性。
            </p>

            {error ? (
              <p className={styles.error} role="alert">
                {error}
              </p>
            ) : null}

            <label className={styles.field}>
              <span className={styles.fieldLabel}>LLM 提供商</span>
              <select
                className={styles.input}
                value={provider}
                onChange={(e) =>
                  changeProvider(e.target.value as LlmProvider)
                }
                disabled={busy}
              >
                {(Object.keys(PROVIDER_TEMPLATES) as LlmProvider[]).map(
                  (p) => (
                    <option key={p} value={p}>
                      {PROVIDER_TEMPLATES[p].label}
                    </option>
                  ),
                )}
              </select>
              <span className={styles.fieldHint}>
                {PROVIDER_TEMPLATES[provider].hint}
              </span>
            </label>

            <label className={styles.field}>
              <span className={styles.fieldLabel}>API Key *</span>
              <input
                ref={inputRef}
                className={styles.input}
                type="password"
                autoComplete="off"
                placeholder={
                  provider === "anthropic"
                    ? "sk-ant-..."
                    : "sk-..."
                }
                value={apiKey}
                onChange={(e) => handleKeyChange(e.target.value)}
                disabled={busy}
                required
              />
            </label>

            <label className={styles.field}>
              <span className={styles.fieldLabel}>Base URL</span>
              <input
                className={styles.input}
                type="url"
                autoComplete="off"
                placeholder="https://api.deepseek.com/v1"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                disabled={busy}
              />
            </label>

            <label className={styles.field}>
              <span className={styles.fieldLabel}>模型</span>
              <input
                className={styles.input}
                type="text"
                autoComplete="off"
                placeholder={provider === "anthropic" ? "claude-sonnet-4-20250514" : "deepseek-chat"}
                value={model}
                onChange={(e) => setModel(e.target.value)}
                disabled={busy}
              />
            </label>

            <div className={styles.actions}>
              <button
                type="submit"
                className={styles.primaryBtn}
                disabled={busy || !apiKey.trim()}
              >
                {busy ? "验证中…" : "确认并启用"}
              </button>
              <button
                type="button"
                className={styles.secondaryBtn}
                onClick={dismiss}
                disabled={busy}
              >
                跳过，使用桩模式
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
