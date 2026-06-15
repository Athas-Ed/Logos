import { apiUrl } from "./apiBase";

/** LLM 提供商标识。与后端 ``LlmProvider`` 对齐。 */
export type LlmProvider = "openai" | "deepseek" | "anthropic" | "custom";

export type LlmApiKeyBody = {
  api_key: string;
  provider: LlmProvider;
  base_url?: string;
  model?: string;
};

export type LlmApiKeyResponse = {
  success: boolean;
  llm_mode: string;
  detail: string;
};

/** 各提供商模板默认值（与后端 PROVIDER_DEFAULTS 同步）。 */
export const PROVIDER_TEMPLATES: Record<
  LlmProvider,
  { label: string; base_url: string; model: string; hint: string }
> = {
  openai: {
    label: "OpenAI（ChatGPT）",
    base_url: "https://api.openai.com/v1",
    model: "gpt-4o",
    hint: "API Key 以 sk-proj- 开头",
  },
  deepseek: {
    label: "DeepSeek",
    base_url: "https://api.deepseek.com/v1",
    model: "deepseek-chat",
    hint: "API Key 以 sk- 开头",
  },
  anthropic: {
    label: "Anthropic Claude",
    base_url: "https://api.anthropic.com",
    model: "claude-sonnet-4-20250514",
    hint: "API Key 以 sk-ant- 开头",
  },
  custom: {
    label: "自定义（OpenAI 兼容）",
    base_url: "",
    model: "",
    hint: "Ollama / vLLM / 内网代理等",
  },
};

/**
 * 根据 API Key 前缀自动推断提供商（无法推断时返回 null）。
 */
export function detectProvider(apiKey: string): LlmProvider | null {
  const key = apiKey.trim();
  if (key.startsWith("sk-ant-")) return "anthropic";
  if (key.startsWith("sk-proj-")) return "openai";
  // sk- 前缀既可能是 OpenAI 也可能是 DeepSeek，无法确定，不自动切换
  return null;
}

/**
 * 向后端提交 LLM API Key。
 * 后端会校验 Key 有效性、持久化到 config/local.yaml，并热替换 LLM 实现。
 */
export async function putLlmApiKey(
  body: LlmApiKeyBody,
  signal?: AbortSignal,
): Promise<LlmApiKeyResponse | null> {
  try {
    const r = await fetch(apiUrl("/api/v1/config/llm-api-key"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
    if (!r.ok) return null;
    return (await r.json()) as LlmApiKeyResponse;
  } catch {
    return null;
  }
}
