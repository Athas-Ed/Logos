# Logos SPEC — V0.1

> **文档地位**：V0.1 的开发范围、行为约定与交付标准**以本文件为准**。`ARCHITECTURE.md` 描述全项目全流程愿景，会随开发演进；实施时若与本规格冲突，**V0.1 以本规格为准**，架构文档可作为后续里程碑的对照与纠偏参考。

---

## 1. V0.1 目标

- 交付一个**可本地运行、全开源栈**的双模式叙事 Agent 最小可用产品（MVP），面向**游戏作家（AM）**日常可用；**游戏编剧（SM）**在 V0.1 仅体现为**配置 + 差异化 System Prompt**，由 Config 层开关控制。
- 建立 **KSFS → KSS → LKC →（HSI ∥ SVS）** 的数据管线：知识以 KSFS 为唯一事实源；LKC 为 Logos 侧规范化副本与构建输入；**HSI**（结构化/精确索引）与 **SVS**（语义向量）**同源、相互独立、互为补充**，由 Retrieval 统一编排。
- 决策层：**Shell + CB + PR**，范式 **仅 ReAct**；工具调用协议 **JSON-only**。
- 交互：**网页 GUI**，开发与个人使用以 **localhost** 为主。
- **能力层（Skills）**：可插拔、**注册表**、**渐进式披露**，经 **本地 MCP Server** 暴露；V0.1 至少一个示例 Skill。**基础设施层（Retrieval 等）**为进程内内部 API，见 `ARCHITECTURE.md`。
- 能在 Agent 外确定性完成的逻辑不依赖 LLM。

---

## 2. 非目标（V0.1 明确不做）

| 项 | 说明 |
|----|------|
| **KG** | 不实现；可在 KSFS 的 YAML 头预留字段供未来使用。 |
| **MS** | 不接入本地部署大模型；仅调用可配置的远程兼容 API（如 OpenAI 兼容）。 |
| **工厂层** | 不实现。 |
| **SM 独立工具集** | 不做；需在架构上**预留接口与配置挂载点**（见 §5）。 |
| **PL 学习算法** | 不做自动学习；允许 **静态用户偏好文件**（如 `user_profile.yaml`）供 CB 注入。 |
| **多租户 / 权限分级 / KSFS 审核流** | 不实现；保留术语与扩展点。 |

---

## 3. 数据与存储约定

### 3.1 术语与数据流

- **LKC（本地知识缓存）**：内容为自 KSFS 经 **KSS** 读取并规范化后的副本，是 HSI / SVS 构建的**唯一基准**，不是第二套事实源。
- **KSS（V0.1）**：进程内接口，从 KSFS 根目录扫描/读取；未来 KSFS 独立后可替换为远程 API，**Retrieval / Shell 只依赖 KSS 抽象，不直接绑死磁盘布局细节**（布局细节由 KSS 实现与文档约定）。
- **HSI**：建议 SQLite 单库（路径可配置），字段至少覆盖：`实体 id`、名称、`type`/`tags`、文件路径、面包屑、摘要、**文件哈希与 mtime**（用于增量重建 SVS/HSI 条目的判断）。具体列可与 `备用.md` 及后续实现微调，**增量与可追溯**为硬要求。
- **SVS**：**ChromaDB** 持久化，默认目录为仓库根 **`.index/.vector_index/`**（与 HSI 分离）；由 LKC 内容切块、嵌入、写入；与 HSI **不共享同一物理表**，检索时由 Retrieval 策略组合结果。
- **嵌入**：默认对接 **BAAI/bge-small-zh-v1.5**（权重路径由 `config` 指定，默认 `models/tooling/embeddings/bge-small-zh-v1.5/`）；**必须通过可替换的嵌入驱动接口 + Config** 指定实现与路径，**禁止**在业务代码中写死唯一模型。接口类名约定见 **`original_docs/DEVPLAN-V0.1-PARALLEL.md` §1**。

### 3.2 目录建议（可实现时调整，但需在 Config 中可配）

- **KSFS 根**：用户内容区，**默认不纳入 Git**（见 §9）。
- **LKC 根**：可由同步/导出任务从 KSS 写入的规范化树或快照目录（亦建议 `.gitignore`）。
- **索引根目录**：默认 **`.index/`**（**不入库**）。其下：**`.index/.vector_index/`** 存 Chroma（SVS）；**`.index/.high-speed_index`** 为 HSI 默认 SQLite 文件名；路径均可由 Config 覆盖。
- **KG 持久化目录**：V0.1 仅占位；与 SVS 目录分离（见 `ARCHITECTURE.md` 目录结构）。
- **YAML 与实体 ID（现阶段）**：KSFS 为独立系统，**实体 ID 以 KSFS 侧分配为准**，分配规则在 KSFS 侧设计；Logos V0.1 为跑通管线，Markdown 头 **YAML 仅保留提示性占位文字**即可。测试用实体集使用**互不重复的数字型 ID** 占位，不与最终 KSFS 规则耦合。

### 3.3 重建与一致性

- 提供显式或启动时的 **「自 KSFS 同步 → 刷新 LKC → 增量更新 HSI/SVS」** 流程；以文件哈希 + mtime 判定变更，避免全量重嵌入成本失控（全量可作为兜底命令保留）。

---

## 4. 模式（OM）行为 — V0.1

### 4.1 AM（作家模式）

- 完整能力：对话、检索、（受控）读写与创作辅助工具集、CB 模板与上下文预算策略。
- 为个人长期使用优化：日志级别、成本统计、草稿区路径可在 Config 指定。

### 4.2 SM（编剧模式）— V0.1 裁剪

- **仅**：在 Config 中由**明确开关或枚举变量**（例如 `operating_mode: author | screenwriter`）切换；切换后加载 **SM 专用 System Prompt / 模板集**，与 AM 共用同一套工具与 HDL（除非未来扩展）。
- **预留**：`modes/screenwriter_mode.yaml`（或等价）中保留 `tools:` / `tool_groups:` / `future_extensions` 等占位结构；代码侧为「按模式加载工具列表」保留**空实现或 no-op 插件点**，避免 SM 加工具时大改 Shell。

---

## 5. 模块交付清单（对照架构分层）

| 分层 | V0.1 交付 |
|------|-----------|
| **决策层** | `Shell` 主循环；`CB` 历史 + 模板 + 预算；`PR` 固定走 ReAct（接口保留供后续 Plan）；依赖 **`logos.ports`** 抽象。 |
| **能力层（Skills）** | MCP Skill 包、注册表、渐进式披露；至少一个 **stdio MCP Server** 示例。 |
| **基础设施层** | `Retrieval` 统一入口（HSI + SVS 策略路由与融合）；**MS**（远程 API）；`src/tools`；进程内内部 API。 |
| **持久层（HDL）** | KSFS 约定 + KSS；LKC；HSI（SQLite）；SVS（Chroma）；KG 无；**实现代码**在 `src/persistence/`（见架构总纲）。 |
| **支撑层** | **Config**（根 `config/` + `src/harness/config` 加载器）；**I&I**（Web + API + **装配**）；**S&G**（过滤、白名单、沙箱、**MCP 进程治理/回收**）；**Obs**（**统一日志**：全库 logger 由 Obs 配置，文件写入根目录 **`logs/`**）；**PL** 可选静态文件。 |
| **工厂层** | 无。 |

---

## 6. Agent 与工具

- **范式**：ReAct；模型返回 **仅 JSON** 的工具调用与最终回复约定（字段名与错误处理在实现阶段写死一版 schema，并写测试样例）。
- **工具（V0.1 建议最小集）**：`retrieve`（走 Retrieval）、`read_ksfs` / `read_lkc`（只读、路径校验）、`write_draft`（**整文件**写入/覆盖，仅允许落在 Config 指定的**草稿区**根路径下，禁止未授权写入 KSFS 源树）。
- **确定性优先**：索引构建、路径解析、模式切换、检索路由在 Python 侧完成，不把「该不该检索」完全交给模型臆测（可提示模型先 `retrieve`）。

---

## 7. GUI 与 API

- **V0.1 优先**：以 **Web**（技术栈保持简单，如 Vite + React + TypeScript）跑通对话、模式切换、检索引用展示；**不采用 monorepo**：前端工程放在 **`src/gui/`**。
- **工作空间 / 文件管理**：长期目标为类 Cursor、IDEA 的便捷工件管理。若纯 Web 实现成本过高，后续以**桌面应用规格**演进，**后端 API 与 HDL 约定保持不变**。
- **localhost**：前后端默认绑定本机；CORS 与 API 基址可配置，便于后续改为内网部署。
- **HTTP**：`chat` 采用 **SSE（Server-Sent Events）**；事件名与 JSON 字段以 **`重要子系统开发文档/API-V0.1.md`** 为准。

---

## 8. MCP

- **Skills（能力层）**经 MCP 暴露；至少一个 **stdio MCP Server** 示例；**启停与资源回收**由 **S&G** 与 Shell 任务边界协作（见 `ARCHITECTURE.md` §2.5）。
- 主进程可 **spawn** 或文档说明手动启动；协议与工具 schema 与内置 JSON 工具尽量**同源定义**，避免两套真理。

---

## 9. 开源边界与隐私（硬约束）

- **仓库与依赖**：项目代码与构建方式全开源可复现；文档中的 `docs/` 等对外展示版本遵循仓库策略。
- **用户创作与知识库内容**：凡个人小说、设定稿、剧本片段等，**不得**作为开源内容提交。默认做法：
  - 人类可读写的创作与阅览根目录使用仓库根 **`workspace/`**（默认 **`.gitignore`**），或由 Config 指向仓库外任意路径；**示例 KSFS** 使用 **`example_ksfs/`**（可入库）跑通管线。
  - Chroma/SQLite 等**索引类文件**默认在 **`.index/`**（或 Config 指定路径），与 `workspace/` 分离。

---

## 10. 部署（V0.1）

- **开发与个人使用**：以 **localhost** 为第一目标；README 写清单机启动步骤与 **`config/local.yaml`**（或等价本地覆盖）中的敏感项；可选支持**环境变量**覆盖，不依赖根目录 `.env`。
- **未来 Linux 虚拟机 / 内网模拟**：不阻塞 V0.1；实施建议见同目录 **`DECISIONS.md`**（防火墙、进程管理、反向代理、数据卷与密钥分离等）。

---

## 11. 开发计划（阶段式，不按周）

阶段顺序体现依赖关系；同一阶段内部分任务可并行。**多 Agent 并行分工、目录所有权、HTTP/工具契约**见 **`original_docs/DEVPLAN-V0.1-PARALLEL.md`**。**开工按该文档 §7 检查表执行**；技术定案总表见 **§12**。

1. **基础骨架**：仓库目录与 `ARCHITECTURE.md` 对齐（含 **`src/gui/`**、**`.index/`**、**`logs/`**）；Config 加载（**`config/*.yaml` 分层合并**，可选环境变量覆盖）；**Obs 统一日志**落盘 `logs/`。
2. **KSFS + KSS + LKC**：目录与文件规范（YAML 头现阶段占位即可）；同步到 LKC；单元测试覆盖路径与哈希；测试实体使用不重复数字 ID。
3. **HSI + SVS + 增量**：HSI 默认文件 **`.index/.high-speed_index`**；**ChromaDB** 默认 **`.index/.vector_index/`** + **可配置嵌入驱动**（默认 bge-small-zh-v1.5）；变更检测与增量更新；必要时全量重建命令。
4. **Retrieval**：统一 API、融合策略、返回结构稳定（供 CB 与前端展示）。
5. **Agent 核心**：ReAct 循环、JSON tool schema、与 Retrieval/只读工具 wired；Obs 记录请求与粗算 token。
6. **S&G 最小**：白名单 + 路径沙箱 + 基础输出过滤。
7. **Web GUI**：在 **`src/gui/`** 内建前端工程；对话、模式开关、引用展示；消费 **SSE**（见 `API-V0.1.md`）。
8. **MCP**：本地 Server + 与 Retrieval 同源能力。
9. **收尾**：`docs/` 与 README 的对外叙述；示例数据与录屏脚本；已知限制列表。

**验收（V0.1 完成判据）**：干净 clone + 配置 API 与路径后，可在本机完成「导入/放置示例 KSFS → 同步 LKC → 提问 → 模型调用 `retrieve` → 回答带可核对引用」；AM/SM 可通过 Config 切换且 Prompt 可区分；个人 KSFS 路径在默认 `.gitignore` 策略下不会误提交。

---

## 12. V0.1 技术定案清单（无阻塞待定项）

以下条目已足以开工；**不再**将 monorepo、Chroma 路径、SSE 字段、HSI 文件名等列为「待定」。实现期若需微调，以 PR 更新 `API-V0.1.md` / `defaults.yaml` 并注明破坏性为准。

| 域 | 定案 |
|----|------|
| 仓库布局 | `src/logos/`（包 **`logos`**）、`src/gui/`、`skills/`、`config/`、`resources/`、`example_ksfs/`、`workspace/`（忽略）、`.index/`（忽略）、`logs/`（忽略）、`scripts/`、`tests/` |
| 索引 | **`.index/.vector_index/`** = Chroma；**`.index/.high-speed_index`** = HSI SQLite |
| 嵌入 | **BAAI bge-small-zh-v1.5**；路径 `embeddings.model_path`；协议名 **`TextEmbedder`**（见 `DEVPLAN-V0.1-PARALLEL.md`） |
| HTTP | **`POST /api/v1/chat`** 仅 **SSE**；事件见 **`重要子系统开发文档/API-V0.1.md`** |
| 配置 | `config/defaults.yaml` + `config/local.yaml`（忽略）；可选环境变量覆盖由加载器实现 |
| GUI | **非 monorepo**，源码 **`src/gui/`**（Vite + React + TS） |
| 日志 | **Obs** 统一，`logs/` 根目录 |
| 数据与隐私 | `workspace/` 个人内容不入库；示例用 `example_ksfs/` |
| KSFS / YAML / ID | YAML 占位；实体 ID 归 KSFS；测试用数字 ID |
| 草稿 | **整文件** `write_draft`，路径受 S&G 约束 |

**非阻塞裁量项**（不挡首版合并，实现时自行决定即可）：`logs/` 下按日滚动还是单文件；嵌入 **chunk 大小与 overlap**；是否实现 **`POST /api/v1/index/rebuild`**；是否增加 **`/chat/debug`** 非流式调试路由。

**执行顺序与多 Agent 分工**：**`DEVPLAN-V0.1-PARALLEL.md`**（含 §7 开工检查表）。

重要子系统长文见 **`original_docs/重要子系统开发文档/`**。
