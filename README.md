# Logos

游戏叙事向双模式 Agent（作家 / 编剧）。

**现行开发入口（仓库内）**

| 内容 | 路径 |
|------|------|
| **现行缺口 / 广义队列** | [`original_docs/下一阶段开发计划.md`](original_docs/下一阶段开发计划.md)（第五阶段主排期未定稿前，以此为候选与顺延入口） |
| **第四阶段（已归档）** | [`original_docs/已完成/第四阶段开发计划.md`](original_docs/已完成/第四阶段开发计划.md) |
| **第三阶段（已归档）** | [`original_docs/已完成/第三阶段开发计划.md`](original_docs/已完成/第三阶段开发计划.md) |
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
- **软件性能（Profiling 基线）**：可选复现 **`GET /api/v1/bootstrap`** 热路径压测：`python scripts/perf_baseline_bootstrap.py 500`；详见 **`original_docs/DEVLOG.md`**（S12～S14）与 **`original_docs/ARCHITECTURE.md`** §4.1。

## 前后端联调（V0.1）

- **桩后端**：`python scripts/run_backend_stub.py`（读 `config/`，SSE 与 GUI 契约一致）。
- **GUI**：`cd src/gui && npm install && npm run dev`（默认代理 `/api` → `http://127.0.0.1:8000`）。
- **Electron 壳（开发态）**：**先**在同一仓库另开终端运行上述 GUI（默认 `http://127.0.0.1:5173`），再在 `src/electron` 安装依赖并启动：`npm install` 后 `npm run electron:dev`。Main 会默认在仓库根拉起 **`scripts/run_backend_stub.py`**（设置 `LOGOS_REPO_ROOT`；若存在 `.venv` 则优先使用该解释器，否则可用 `LOGOS_PYTHON` 或 `LOGOS_BACKEND_USE_UV=1` 覆盖）。若后端已由其他终端或一键脚本启动，请对 Electron 进程设置 **`LOGOS_ELECTRON_SKIP_BACKEND=1`** 以免双开占用 8000 端口（`scripts/start_logos.*` 已对 Electron 自动设置）。若从 GitHub 拉取 Electron 不稳定，请改用 **`npm run install:with-mirror`**（脚本会设置 `ELECTRON_MIRROR` 指向 npmmirror，且不触发 npm 10+ 对项目级 `electron_mirror` 的警告）。可选环境变量：`LOGOS_GUI_DEV_HOST`、`LOGOS_GUI_DEV_PORT`（默认 `127.0.0.1`、`5173`）；后端日志：`LOGOS_ELECTRON_BACKEND_STDIO`（`prefix` / `inherit` / `ignore`，默认 `prefix`）。**打包 Windows**：在仓库根准备好 Python 与 `pip install -e ".[dev]"` 后，执行 `cd src/gui && npm install && npm run build`，再 `cd ../electron && npm install && npm run package:win`。成功时 `src/electron/release/` 下应有 **`Logos-<version>-portable.exe`** 与 **`win-unpacked/`**（后者内 `Logos.exe` 可直接运行；便携 exe 若因网络/NSIS 未生成，仍可用解包目录调试）。若 **`electron-builder` 下载 Electron 失败**，请用 **`npm run package:win:with-mirror`**，或手动：`$env:ELECTRON_MIRROR='https://npmmirror.com/mirrors/electron/'; npm run package:win`。**打包态仓库根**：壳会从便携 exe 所在目录、`PORTABLE_EXECUTABLE_DIR`（便携运行时由 builder 注入）及 `win-unpacked` 等起点**向上查找**含 `scripts/run_backend_stub.py` 的目录；在源码树内默认可解析到克隆根。若仅拷贝 exe 到无仓库的机器，请设置 **`LOGOS_REPO_ROOT`**。生产包默认关闭 DevTools；调试可设 **`LOGOS_ELECTRON_ALLOW_DEVTOOLS=1`**。权威约定见 [`original_docs/重要子系统开发文档/GUI开发文档.md`](original_docs/重要子系统开发文档/GUI开发文档.md)。阶段沿革见 [`original_docs/第四阶段开发计划.md`](original_docs/第四阶段开发计划.md)（**重定向 stub**）或 [`original_docs/已完成/第四阶段开发计划.md`](original_docs/已完成/第四阶段开发计划.md)（**归档全文**）。
  - **若 `npm install` 报 `read ECONNRESET`（下载 Electron 失败）**：先删除不完整的 `src/electron/node_modules`，再在 `src/electron` 执行 **`npm run install:with-mirror`**。也可手动设置环境变量后照常安装，例如 PowerShell：`$env:ELECTRON_MIRROR='https://npmmirror.com/mirrors/electron/'; npm install`。若你**必须**始终走 GitHub 官方源，请只用 `npm install`，勿设 `ELECTRON_MIRROR`。
  - **若报错 `Electron failed to install correctly`**：`node_modules/electron/path.txt` 未生成，多为安装中断或目录被占用。请关闭已运行的 Electron、本 IDE 内可能占用该路径的终端/预览后，删除 `src/electron/node_modules/electron`（仍失败则整删 `src/electron/node_modules`），再在 `src/electron` 执行 `npm install`。若出现 `EBUSY`，可换本机普通 CMD/PowerShell（非嵌套终端）或重启后再删。
- **一键**：推荐 `scripts/start_logos.ps1`（或双击 `scripts/start_logos.cmd`）：**新窗口**依次拉起后端（:8000）、Vite（:5173）、Electron 壳（短暂等待后加载 Vite）；macOS/Linux 用 `chmod +x scripts/start_logos.sh && ./scripts/start_logos.sh`（后端与双前端在后台，Ctrl+C 结束脚本时会清理子进程）。`scripts/run_dev.*` 为兼容别名，行为相同。
- **GUI E2E（Playwright）**：在已 `pip install -e ".[dev]"` 的前提下，`cd src/gui && npm install && npx playwright install chromium && npm run test:e2e`（脚本会按需拉起桩后端与 Vite，断言首屏健康检查为可用；首次 CI 机器需下载浏览器二进制）。
- 更细的步骤见 [`docs/V0.1-QUICKSTART.md`](docs/V0.1-QUICKSTART.md)。

## 配置与隐私

- 默认配置：`config/defaults.yaml`；本机密钥与覆盖：`config/local.yaml`（从 `config/local.example.yaml` 复制，勿提交）。
- 个人创作目录：`workspace/`（默认已 `.gitignore`）。
- 面向本机阅读的**日志行、JSON 日志字段名、常见异常提示**等以**简体中文**为主（便于日常使用）；API 路径、配置键名、代码标识符仍保持英文以便与文档/生态对齐。

## 草稿晋升至 KSFS（CLI，第四阶段 A7）

将 `workspace` 下 **`setting_entry/`**（可调 `--drafts-relative`）内的 Markdown 草稿**复制**到 **`paths.ksfs_root`** 语义下的目录，并在 **`--apply`** 成功后触发 **HSI** 同步；**`--dry-run`** 仅列出候选与拟路径，**不写盘**。语义、mtime 与禁止静默覆盖见 **[`original_docs/重要子系统开发文档/KSFS开发.md`](original_docs/重要子系统开发文档/KSFS开发.md)** §3.2、§7。

在仓库根、已 `pip install -e ".[dev]"` 且激活 venv 的前提下：

```bash
# 只读预览（不写 KSFS、不写 HSI）
python -m logos.tools.promote_draft --workspace ./workspace --target-ksfs <KSFS根目录> --dry-run

# 实际晋升（默认 HSI 库为当前目录下 .index/.high-speed_index，可用 --hsi-db 指定）
python -m logos.tools.promote_draft --workspace ./workspace --target-ksfs <KSFS根目录> --apply
```

**说明**：晋升逻辑以 Python 模块 **`logos.ports.draft_promotion`** / **`logos.tools.draft_promotion_fs`** 为单一事实源；若将来在 Electron / GUI 暴露入口，应**仅**通过 Main 进程拉起上述 CLI 或等价 API 调用，**不得**在渲染进程重复业务规则（见 **[`original_docs/重要子系统开发文档/GUI开发文档.md`](original_docs/重要子系统开发文档/GUI开发文档.md)** §2、§3 与 **[`original_docs/已完成/第四阶段开发计划.md`](original_docs/已完成/第四阶段开发计划.md)** §9.2 **G4**）。

## 大模型（主依赖）

- **`httpx`**：OpenAI 兼容对话 API（如 DeepSeek）已接入 `logos.infrastructure.llm`；在 `config/local.yaml` 配置 `llm.api_key` 后，`python scripts/run_backend_stub.py` 即走真实模型。

## 向量与 HTTP（开发依赖）

- **`chromadb`**：Chroma 持久化客户端（`ChromaSemanticStore`），`pip install -e ".[dev]"` 已包含。
- **`sentence-transformers` + PyTorch**：本地 `BgeSmallZhEmbedder` 加载 `models/tooling/embeddings/bge-small-zh-v1.5` 时需要（体积较大，首次会自动下载相关 wheel）。
- **`fastapi` / `uvicorn` / `httpx`**：`/api/v1` 与 SSE 测试用，同上在 `[dev]` 中。

## 许可证

本项目采用 [MIT License](LICENSE)。
