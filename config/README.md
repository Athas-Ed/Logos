# 配置说明

- **`defaults.yaml`**：**可提交 Git** 的默认值，**不含**真实密钥。
- **`local.yaml`**：本机私有覆盖（含 API Key 等）。**不要提交**；从 **`local.example.yaml`** 复制一份后改名/填写。

加载顺序建议：`defaults.yaml` → `local.yaml`（后者覆盖前者）；若实现支持，可再允许**进程环境变量**覆盖个别键（便于容器部署），**不**使用仓库根目录的 `.env` 文件。

## 大模型（`llm`）

- **用途**：`scripts/run_backend_stub.py` 在检测到 `llm.api_key` 非空时，通过 **OpenAI 兼容** `POST …/chat/completions` 调用远程模型（如 DeepSeek）。
- **基础配置**：`defaults.yaml` 提供默认 `base_url` / `model`；密钥与覆盖写在 `local.yaml`，或使用 `LOGOS_LLM__API_KEY` 等环境变量。
- **TLS / 代理**（统一走配置合并，与 `paths` 等一致）：
  - `verify_ssl`：是否校验 HTTPS 证书（`false` / `0` 关闭，不推荐）。
  - `ca_bundle`：自定义 CA 证书包路径（`.pem` / `.cer` 等，供 `httpx` 的 `verify` 使用）。
  - `http_proxy` / `https_proxy`：仅作用于 **LLM 客户端**；若二者都为空，客户端仍 **`trust_env`**，可读系统里的 `HTTP_PROXY` / `HTTPS_PROXY`。
  - `no_proxy`：写入进程内 `NO_PROXY`（供 httpx/urllib 解析），便于本地直连不走代理。
- **环境变量覆盖**（与 `LOGOS_*` 规则一致）：`LOGOS_LLM__VERIFY_SSL`、`LOGOS_LLM__CA_BUNDLE`、`LOGOS_LLM__HTTP_PROXY`、`LOGOS_LLM__HTTPS_PROXY`、`LOGOS_LLM__NO_PROXY`。

## 可选 MCP 技能（`skills`）

- **`skills.amap_weather`**：挂载 `skills/amap-weather-mcp`（高德实况天气）。`defaults.yaml` 默认 `enabled: false`；在 **`local.yaml`** 填写 `web_api_key` 并置 `enabled: true`。
- **环境变量**：`LOGOS_SKILLS__AMAP_WEATHER__ENABLED`、`LOGOS_SKILLS__AMAP_WEATHER__WEB_API_KEY`。
- **说明**：后端将 Key 注入 MCP 子进程的环境变量 `AMAP_WEB_KEY`；勿把真实 Key 写入可提交 Git 的 YAML。细节见 `skills/amap-weather-mcp/README.md`。
- **MCP 与仓库路径**：若 Agent 对话里看不到 `query_weather`，请确认本机 `skills/amap-weather-mcp/server.py` 存在；从非仓库 cwd 启动或包在 site-packages 时，设置 **`LOGOS_REPO_ROOT`** 指向仓库根（`scripts/run_backend_stub.py` 已默认 `setdefault`）。

## 日志目录（`logs/`）

- **配置位置**：`defaults.yaml` → `paths.logs_root`（默认 `./logs`）；可用 `local.yaml` 覆盖，或用环境变量 `LOGOS_PATHS__LOGS_ROOT`。
- **生效方式**：在进程启动时调用 `logos.harness.obs.configure_logging`（会读取合并后的配置）；内部会**自动创建**该目录（含父路径）。
- **测试**：`pytest` 会在临时目录下创建 `…/logs/_pytest/` 子目录写入测试日志，避免污染你本机 `./logs`。
