# Logos — 已确认决策与备忘（`original_docs`）

> **现行依据**：以 **`ARCHITECTURE.md`**、**`重要子系统开发文档/KSFS开发.md`** 及后续版本 SPEC（如 **`SPEC-DISPLAY-AND-LOGGING-V0.1.md`**）为准。若与 **`已完成文档/SPEC-V0.1.md`**（归档）冲突，**以现行总纲与 KSFS 文档为准**；归档仅供对照。  
> **`original_docs/`** 约定：内部文档根目录；不上传 GitHub 的团队可自行保留本地副本（与仓库 `.gitignore` 策略一致）。

---

## 1. 文档层级

| 文档 | 作用 |
|------|------|
| `ARCHITECTURE.md` | 全项目全流程；分层、目录、DIP / I&I。 |
| `重要子系统开发文档/KSFS开发.md` | **KSFS / HDL 边界（现行权威）**。 |
| `GLOSSARY.md` | 术语索引。 |
| `DECISIONS.md` | 本文件：仓库布局、已定产品形态、KSFS 摄入与扩展策略摘要。 |
| `重要子系统开发文档/` | 实现级长文；含 **`API-V0.1.md`** 等。 |
| `SPEC-DISPLAY-AND-LOGGING-V0.1.md` | 展示与日志补充规格（与实现对齐迭代）。 |
| `已完成文档/SPEC-V0.1.md` | V0.1 规格（**归档**）。 |
| `已完成文档/DEVPLAN-V0.1-PARALLEL.md` | V0.1 多 Agent 并行计划（**归档**）。 |
| `下一阶段开发计划.md` | 当前阶段之后工作队列（草案）；与 **§10、§12** 及 `KSFS开发.md` 对齐。 |

---

## 2. 仓库布局（已定案）

- **`src/`**：可导入包 **`logos`**（`src/logos/`：agent、infrastructure、persistence、tools、harness、**ports**）+ **`src/gui/`**（Vite + React + TS）。物理路径见 `src/README.md`。
- **`skills/`**：与 `src` 并列；MCP Skill 包、注册元数据、渐进式披露。
- **`config/`**：`defaults.yaml` + **`local.example.yaml`**；本机覆盖 **`config/local.yaml`（不入库）**。
- **`resources/`**：约定资源（可提交）。含 **`resources/prompts/`**（CB）、**`resources/entity_template/`**（实体形态契约）、**`resources/ksfs/`**（默认 **`paths.ksfs_root`**，树内用户内容常 **`.gitignore`**）。根目录可保留 **`resources/.gitkeep`**。
- **`example_ksfs/`**：示例 KSFS 树（可提交）。
- **`workspace/`**：工作空间（草稿、工件、**待落户设定**等；**非** KSFS 事实源）。默认忽略内容，**例外**：可提交 **`workspace/README.md`** 与 **`workspace/setting_entry/README.md`** 说明目录用途（见 `.gitignore`）。
- **`scripts/`**：一键启动脚本（**应提交**）。
- **`.index/`**：向量索引与 HSI 等运行时数据（**不入库**）。
- **`logs/`**：Obs 日志根（**不入库**）。
- **`models/`**：说明可提交；tooling 权重目录常忽略。
- **`original_docs/`**：内部文档。
- **`docs/`**：对外精修版（可选与 `original_docs` 同步）。

---

## 3. 分层与职责（摘要）

- **基础设施层**：Retrieval、MS、**`src/logos/tools/`**（系统工具**实现原语**）；进程内内部 API；**非** MCP Skills。
- **能力层（Skills）**：MCP Server；注册表、渐进式披露。
- **S&G**：**`harness/sg_layer`** — 工具白名单、路径沙箱、输出过滤、**MCP 进程治理**（与 Shell 任务边界协作）。
- **I&I**：**`harness/ii_layer`** 等 — HTTP + **SSE**（V0.1 主路径）、GUI、CLI、组合根装配。
- **端口**：**`logos.ports`**（`src/logos/ports/`），DIP。

---

## 4. 向量与嵌入（已定案）

- ChromaDB + 可配置嵌入；默认 **bge-small-zh-v1.5**；权重路径见 **`models/README.md`**。集合名等以 `config/defaults.yaml` 与 **`KSFS开发.md`** 为准。

---

## 5. 一键启动与 GitHub

- **脚本（.bat / .sh / PowerShell）应提交**。
- **大型无溯源二进制**可不提交；若提交小启动器须在 README 说明。

---

## 6. V0.1 待定项（非阻塞）

- 实现期裁量：日志滚动、chunk 参数、可选 `index/rebuild` 路由等；历史列举见 **`已完成文档/SPEC-V0.1.md`** §12。

---

## 7. 系统工具与 S&G 边界（已定案）

- **实现**：确定性原语在 **`logos.tools`**；**治理**在 **`harness/sg_layer`**（白名单、沙箱闭包、输出长度、MCP 治理）。

---

## 8. I&I 传输：SSE 与 WebSocket（已定案）

- **V0.1 主对话**：**`POST /api/v1/chat` 以 SSE 为主**（契约见 **`重要子系统开发文档/API-V0.1.md`**）。
- **演进**：可并行增加 WebSocket；默认仍以 SSE 为主，除非产品规格明确要求切换。

---

## 9. CB、Prompt 与实体模板（已定案）

- **Prompt 模板**：**`resources/prompts/`**；由 **CB** 加载；Shell（或策略模块）做模板 / 预算 profile 路由。
- **KSFS 实体模板（契约）**：**`resources/entity_template/`**（**2026-05-11 定案**）。约束 **KSFS 实体 `.md` 的长期形态**（提取规格、JSON Schema、渲染规格、`manifest.yaml` 等）；**首要消费者**为设定导入，未来 **KSFS 修改** Skill 可复用。**勿**放入 **`paths.ksfs_root`**；**勿**与 `prompts/` 混目录。
- **版本**：资源侧 `manifest.yaml`、semver / 别名；S&G 仅在合规脱敏时介入，不承担模板版本业务。

---

## 10. 产品形态与 GUI（已定方向，2026-05-11）

- **定位**：**独立工作助手** — 独立桌面窗口或侧边栏形态；**不把内置正文编辑器**作为用户写「作品正文」的第一现场；通过 API 与受控路径操作 **KSFS、HDL** 与 **`workspace/`**。
- **交互优先级**：**优先侧边栏式**（多轮对话、长文生成与推敲）；**命令面板式**（全局快捷键、短查询）可**放缓或简化**。
- **壳层**：**独立桌面窗口** + **Electron**（相对 GB 级 Python/索引体量，壳体积差异为次要因素；生态与现有 Web GUI 衔接成本低）。HTTP+SSE 与 KSFS/HDL **不因壳而变**。

---

## 11. 其余已定案条目

- **作家 / 编剧双模式**：Prompt 与策略路由见 `resources/prompts/modes/` 与 CB；细节以总纲与 SPEC 为准。
- **历史开工检查表**：**`已完成文档/DEVPLAN-V0.1-PARALLEL.md`** §7（归档）。

---

## 12. KSFS 摄入策略与能力层扩展（已定方向，2026-05-11）

**流水线与 HDL 细则以 `重要子系统开发文档/KSFS开发.md`（§3.0、§3.5、§7.3）为准**；本节为**全局摘要**。

### 12.1 策略要点

- **事实源**：KSFS **仅 `.md`** 进入 HDL 核心扫描；**.docx / PDF 等不进入核心解析管线**。
- **设定类 SSOT**：**落户**到 `ksfs_root` 且经 HSI 登记的实体为设定类叙事知识的**权威依据**；外部 Word 可为创作稿或归档；**默认不维护** Word 节级映射。
- **导入流水线**：**Skill + 粘贴 → LLM 结构化 JSON → JSON Schema 校验 → 本地渲染 → `workspace/setting_entry/` 草稿 → 人审 → 晋升 `ksfs_root`**；**持久 `id` 仅在落户后**由 HSI 分配。
- **草稿与建议**：**必有**可晋升草稿；若有值得修改处，**另附** `suggestions[]`；md 中可呈现独立章节（如 `## 修改建议`）；**禁止**「仅建议、无草稿」为导入常态。
- **双模板 / 单契约**：**提取规格**（LLM，与 schema 同源）+ **渲染规格**（本地）；**Prompt 黑白名单**为软约束；**硬闸门**为 schema + 本地渲染 + 沙箱。
- **重叠与分流**：与**已落户实体**重叠时，导入流**不静默覆盖**；转交未来 **「KSFS 修改」** 能力或显式用户选择。

### 12.2 未来可扩展（非当前核心）

- **`.docx` 摄取 Skill（可选）**：抽取或辅助粘贴；**非** HDL 核心。
- **「KSFS 修改」Skill**：已落户实体的受控改写 / 合并 / 提案；与导入**分规格、分入口**。

---

*最后更新：2026-05-12 — 本会话定案汇总重写；与 `KSFS开发.md`、`ARCHITECTURE.md`、`GLOSSARY.md` 对齐。*
