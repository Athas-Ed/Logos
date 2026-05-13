# Logos

游戏叙事向双模式 Agent（作家 / 编剧）。

**现行开发入口（仓库内）**

| 内容 | 路径 |
|------|------|
| **下一阶段排期与任务块（A1～A8）** | [`original_docs/下一阶段开发计划.md`](original_docs/下一阶段开发计划.md) |
| **目录结构与分层** | [`original_docs/ARCHITECTURE.md`](original_docs/ARCHITECTURE.md)（见 **§3 项目目录结构**） |
| **已定案决策备忘** | [`original_docs/DECISIONS.md`](original_docs/DECISIONS.md) |
| **KSFS / HDL 权威** | [`original_docs/重要子系统开发文档/KSFS开发.md`](original_docs/重要子系统开发文档/KSFS开发.md) |

**V0.1 历史规格（归档对照）**：[`original_docs/已完成文档/SPEC-V0.1.md`](original_docs/已完成文档/SPEC-V0.1.md)；并行计划归档：[`original_docs/已完成文档/DEVPLAN-V0.1-PARALLEL.md`](original_docs/已完成文档/DEVPLAN-V0.1-PARALLEL.md)。若根目录下仍有同名拷贝，以 **`已完成文档/`** 内为归档主本。

## Stream 0 本地环境

```bash
cd g:\GithubProject\Logos
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
pytest
# 跳过需本机 BGE 权重的慢测：pytest -m "not slow"
```

- Python **3.11+**
- 包根：`import logos`（源码在 `src/logos/`，说明见 `src/README.md`）

## 前后端联调（V0.1）

- **桩后端**：`python scripts/run_backend_stub.py`（读 `config/`，SSE 与 GUI 契约一致）。
- **GUI**：`cd src/gui && npm install && npm run dev`（默认代理 `/api` → `http://127.0.0.1:8000`）。
- **Electron 壳（开发态，第三阶段 M-A）**：**先**在同一仓库另开终端运行上述 GUI（默认 `http://127.0.0.1:5173`），再在 `src/electron` 安装依赖并启动：`npm install` 后 `npm run electron:dev`。若从 GitHub 拉取 Electron 不稳定，请改用 **`npm run install:with-mirror`**（脚本会设置 `ELECTRON_MIRROR` 指向 npmmirror，且不触发 npm 10+ 对项目级 `electron_mirror` 的警告）。可选环境变量：`LOGOS_GUI_DEV_HOST`、`LOGOS_GUI_DEV_PORT`（默认 `127.0.0.1`、`5173`）。权威约定见 [`original_docs/重要子系统开发文档/GUI开发文档.md`](original_docs/重要子系统开发文档/GUI开发文档.md)。
  - **若 `npm install` 报 `read ECONNRESET`（下载 Electron 失败）**：先删除不完整的 `src/electron/node_modules`，再在 `src/electron` 执行 **`npm run install:with-mirror`**。也可手动设置环境变量后照常安装，例如 PowerShell：`$env:ELECTRON_MIRROR='https://npmmirror.com/mirrors/electron/'; npm install`。若你**必须**始终走 GitHub 官方源，请只用 `npm install`，勿设 `ELECTRON_MIRROR`。
  - **若报错 `Electron failed to install correctly`**：`node_modules/electron/path.txt` 未生成，多为安装中断或目录被占用。请关闭已运行的 Electron、本 IDE 内可能占用该路径的终端/预览后，删除 `src/electron/node_modules/electron`（仍失败则整删 `src/electron/node_modules`），再在 `src/electron` 执行 `npm install`。若出现 `EBUSY`，可换本机普通 CMD/PowerShell（非嵌套终端）或重启后再删。
- **一键**：推荐 `scripts/start_logos.ps1`（或双击 `scripts/start_logos.cmd`）：**新窗口**依次拉起后端（:8000）、Vite（:5173）、Electron 壳（短暂等待后加载 Vite）；macOS/Linux 用 `chmod +x scripts/start_logos.sh && ./scripts/start_logos.sh`（后端与双前端在后台，Ctrl+C 结束脚本时会清理子进程）。`scripts/run_dev.*` 为兼容别名，行为相同。
- 更细的步骤见 [`docs/V0.1-QUICKSTART.md`](docs/V0.1-QUICKSTART.md)。

## 配置与隐私

- 默认配置：`config/defaults.yaml`；本机密钥与覆盖：`config/local.yaml`（从 `config/local.example.yaml` 复制，勿提交）。
- 个人创作目录：`workspace/`（默认已 `.gitignore`）。
- 面向本机阅读的**日志行、JSON 日志字段名、常见异常提示**等以**简体中文**为主（便于日常使用）；API 路径、配置键名、代码标识符仍保持英文以便与文档/生态对齐。

## 大模型（主依赖）

- **`httpx`**：OpenAI 兼容对话 API（如 DeepSeek）已接入 `logos.infrastructure.llm`；在 `config/local.yaml` 配置 `llm.api_key` 后，`python scripts/run_backend_stub.py` 即走真实模型。

## 向量与 HTTP（开发依赖）

- **`chromadb`**：Chroma 持久化客户端（`ChromaSemanticStore`），`pip install -e ".[dev]"` 已包含。
- **`sentence-transformers` + PyTorch**：本地 `BgeSmallZhEmbedder` 加载 `models/tooling/embeddings/bge-small-zh-v1.5` 时需要（体积较大，首次会自动下载相关 wheel）。
- **`fastapi` / `uvicorn` / `httpx`**：`/api/v1` 与 SSE 测试用，同上在 `[dev]` 中。
