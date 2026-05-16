# 配置说明

- **`defaults.yaml`**：**可提交 Git** 的默认值，**不含**真实密钥。
- **`local.yaml`**：本机私有覆盖（含 API Key 等）。**不要提交**；从 **`local.example.yaml`** 复制一份后改名/填写。

加载顺序建议：`defaults.yaml` → `local.yaml`（后者覆盖前者）；若实现支持，可再允许**进程环境变量**覆盖个别键（便于容器部署），**不**使用仓库根目录的 `.env` 文件。

## 展示与日志（`ui` / `obs`）

- **`ui.default_presentation`**：`work` \| `developer`；新建 GUI 会话的默认展示档位（浏览器内可覆盖，见 `SPEC-DISPLAY-AND-LOGGING-V0.1.md`）。
- **`obs.log_profile`**：`minimal` \| `standard` \| `verbose` \| `audit`；影响 **维护侧** `maint/*.log` 与**控制台**的最低级别；**日常** `daily/…` 固定为 `>= INFO`，与此项解耦。
- **环境变量覆盖**：`LOGOS_UI__DEFAULT_PRESENTATION`、`LOGOS_OBS__LOG_PROFILE`（规则同其他 `LOGOS_*` 段）。

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

- **`skills.mcp_servers`**：声明式挂载多个 stdio MCP（`id`、`enabled`、`entrypoint`、`strip_http_proxy`、`env`）。**必须为 YAML 列表**（可为 `[]`）；误写成字符串/映射时进程启动读配置将 **`ValueError` fail-fast**（见 **`MCP开发.md`** §8.3）。权威说明见 **`original_docs/重要子系统开发文档/MCP开发.md`**；`defaults.yaml` 中默认为空列表。
- **高德实况天气**：仓库内 **`skills/amap-weather-mcp/`**（工具 `query_weather`）；**不写入** `defaults.yaml`，在 **`local.yaml`** 的 `mcp_servers` 中自行增加一条，并在 `env` 中提供 **`AMAP_WEB_KEY`**（勿提交真实 Key）。细节见 `skills/amap-weather-mcp/README.md`。
- **MCP 与仓库路径**：若看不到某 MCP 工具，请确认 `entrypoint` 路径存在；从非仓库 cwd 启动或包在 site-packages 时，设置 **`LOGOS_REPO_ROOT`** 指向仓库根（`scripts/run_backend_stub.py` 已默认 `setdefault`）。

## 日志目录（`logs/`）

- **配置位置**：`defaults.yaml` → `paths.logs_root`（默认 `./logs`）；可用 `local.yaml` 覆盖，或用环境变量 `LOGOS_PATHS__LOGS_ROOT`。
- **生效方式**：在进程启动时调用 `logos.harness.obs.configure_logging`（会读取合并后的配置）；内部会**自动创建** `logs_root`、`daily/`、`maint/`。
- **落盘约定**：**日常**为 `daily/YYYY-MM/YYYY-MM-DD.log`（固定 `>= INFO`，与 `obs.log_profile` 解耦）；**维护**为 `maint/<子系统>.log`（级别随 `obs.log_profile`），子系统路由见 `src/logos/harness/obs/path_handlers.py`。`config/logging.yaml` 的 `logging.format` 同时作用于控制台与上述文件；`logging.file_name` 已废弃。
- **Electron 壳**：后端崩溃/重启审计写入 **`maint/electron-shell.log`**（与 `paths.logs_root` 同根，优先 `LOGOS_REPO_ROOT`）。
- **测试**：`pytest` 会在临时目录下创建 `…/logs/_pytest/` 子目录写入测试日志，避免污染你本机 `./logs`。
