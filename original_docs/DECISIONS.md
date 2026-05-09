# Logos — 已确认决策与备忘（`original_docs`，不上传 GitHub）

> 若与 `SPEC-V0.1.md` 冲突，**以 SPEC-V0.1 为准**。

---

## 1. 文档层级

| 文档 | 作用 |
|------|------|
| `ARCHITECTURE.md` | 全项目全流程；含分层、目录、DIP/I&I 约定。 |
| `SPEC-V0.1.md` | **V0.1 唯一执行依据**。 |
| `GLOSSARY.md` | 术语。 |
| `DECISIONS.md` | 本文件。 |
| `重要子系统开发文档/` | 实现级长文；含 **`API-V0.1.md`**。 |
| `DEVPLAN-V0.1-PARALLEL.md` | **多 Agent 并行**任务切分与契约。 |

---

## 2. 仓库布局（已定案）

- **`src/`**：Python 包 **`logos`**（`src/logos/`：agent、infrastructure、persistence、tools、harness、**ports**）+ **`src/gui/`** 前端。
- **`skills/`**：与 `src` 并列；MCP、注册表、渐进式披露。
- **`config/`**：人类可读默认配置 + **本机 `local.yaml`（不入库）**；示例见 **`config/local.example.yaml`**。不使用仓库根目录 `.env`；若部署需要，可由加载器支持**环境变量**覆盖个别键。
- **`resources/`**：图标、空模板等约定俗成资源（可上传）。
- **`example_ksfs/`**：当前阶段示例 KSFS（可上传）；KSFS 独立后可迁出。
- **`workspace/`**：**个人创作与可阅览内容**（默认 **`.gitignore`**，不上传 GitHub）。
- **`scripts/`**：一键启动脚本（**应上传** GitHub）。
- **`.index/`**：索引根；内含 **`.vector_index/`**（Chroma/SVS）、**`.high-speed_index`**（HSI/SQLite）；**不入库**。
- **`logs/`**：Obs 统一日志输出根；**不入库**。
- **GUI**：**非 monorepo**，源码在 **`src/gui/`**。
- **`original_docs/`**：内部文档，**根目录**，不上传 GitHub 的约定不变。

---

## 3. 分层与职责

- **基础设施层**：Retrieval、MS、`src/tools`；**内部 API**；非 MCP Skills。
- **能力层（Skills）**：MCP Server；可插拔、注册表、渐进式披露。
- **S&G**：含 **MCP 进程治理**（限额、回收、与 Shell 任务边界协作）。
- **I&I**：HTTP/GUI/CLI、**适配器与组合根**；详见 `ARCHITECTURE.md` §2.6。
- **端口**：`logos.ports`（`src/logos/ports/`），决策层依赖抽象，Infrastructure 实现。

---

## 4. 向量与嵌入（已定案）

- ChromaDB + 可配置嵌入；默认 bge-small-zh-v1.5；权重路径见 `models/README.md`。

---

## 5. 一键启动与 GitHub（澄清）

- **脚本（.bat/.sh）应提交**，便于他人部署。
- **可选不提交**：打包生成的大型 `.exe` 或无溯源二进制；若提交小启动器，需在 README 说明。

---

## 6. V0.1 待定项

- **无阻塞开工的待定项**；仅存在实现期**裁量**（日志滚动、chunk 参数、可选 `index/rebuild` 路由等），见 `SPEC-V0.1.md` §12 与 `DEVPLAN-V0.1-PARALLEL.md` §7。

---

## 7. 其余已定案条目

- SM V0.1：Config + Prompt；KSFS 实体 ID 归 KSFS；YAML 占位；草稿整文件；GUI 先 Web 等——仍以 SPEC 为准。
- **开工**：以 `DEVPLAN-V0.1-PARALLEL.md` §7 检查表为准。

---

*最后更新：纳入 `src/gui/`、`.index/`、`logs/`、SSE、`DEVPLAN-V0.1-PARALLEL.md` 与 `API-V0.1.md`。*

