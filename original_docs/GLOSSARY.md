# 术语表（Glossary）

> 快速索引。**现行权威**：**`ARCHITECTURE.md`**、**`重要子系统开发文档/KSFS开发.md`**、**`DECISIONS.md`**。归档 SPEC 仅供历史对照。

---

## 系统与模式

- **Logos** — 游戏叙事架构智能体；作家 / 编剧双运行模式（OM）按需切换。
- **OM** — 运行模式（Operating Mode）。顶层角色：**AM（作家）**、**SM（编剧）** 等。
- **Shell** — Agent 调度器：确定性路由、端口调用、任务边界。
- **CB（Context Builder）** — 对话历史、Prompt 模板、上下文预算；资产默认 **`resources/prompts/`**。
- **PR（Paradigm Router）** — Agent 范式路由：Skill manifest **预绑定** `dialogue` / `react` / `plan` / `pipeline`；现行代码仅实现 **react**（见 **`范式路由与PR定案.md`**）。
- **对话范式（`dialogue`）** — 自由文本 LLM，**非** ReAct JSON-only；语病、启发类 Skill。
- **Plan 范式（`plan`）** — 先产出计划再分步执行（雏形）；与 ReAct **并列**。
- **流水线范式（`pipeline`）** — 确定性阶段 + 局部 LLM；设定导入类；**不经** ReAct 循环。

---

## 分层

- **基础设施层** — 进程内内部 API：**Retrieval**、**MS**、**`logos.tools`** 等；**非** MCP Skills。
- **能力层（Skills）** — MCP Server；注册表、渐进式披露；位于 **`skills/`**。
- **I&I** — Interface & Integration：HTTP、**SSE**、GUI、CLI、**组合根**（`harness/ii_layer`）。
- **S&G** — Security & Governance：沙箱、工具白名单、输出治理、**MCP 进程治理**（`harness/sg_layer`）。
- **Obs** — 可观测性；统一日志，默认根目录 **`logs/`**，其下 **`daily/`**（按日切分的日常轨）与 **`maint/`**（按子系统的维护轨）；详见 **`logs/README.md`**。
- **Config** — **`config/defaults.yaml`** + 本机 **`config/local.yaml`**。

---

## 数据与持久

- **KSFS（Knowledge Source File System）** — **叙事知识唯一事实源**；默认根 **`paths.ksfs_root`**（常 **`resources/ksfs/`**）。核心扫描 **仅 `.md` 实体文件**；详见 **`KSFS开发.md`**。
- **HDL（Hybrid Data Layer）** — 混合数据层：**HSI** + **SVS**（+ 未来 **KG**），均由 KSFS 构建/对账。
- **HSI（High-Speed Index）** — SQLite 元数据索引；实体 **`id`**、路径、mtime、正文 body 哈希等。
- **SVS（Semantic Vector Store）** — 语义向量存储（V0.1 **ChromaDB**）。
- **KG** — 知识图谱（预留）。
- **落户** — 草稿经用户确认 **晋升** 至 **`ksfs_root`** 并完成 **HSI 登记**；此后实体拥有持久 **`id:`**（回写 front matter）。
- **Setting Entry** — **`workspace/setting_entry/`**：设定导入产生的 **待落户** `.md`；**非** KSFS 事实源，见 **`KSFS开发.md`** §2、§7。
- **Entity template（实体模板）** — **`resources/entity_template/<profile>/`**：JSON Schema、渲染规格、`manifest.yaml` 等；约束实体文件形态；与 **Prompt**、**KSFS 用户文件** 分离，见 **`DECISIONS.md` §9**。

---

## GUI 与产品（第五阶段）

- **任务（Task）** — 用户一次完整工作单元：选 Skill → 输入 → 执行 → 结束/归档；**对应**档 B 一个会话 JSON（`DECISIONS.md` §14）。
- **产品 Skill（Product Skill）** — 用户可选的任务配方：manifest、`persistence_tier`、Prompt 运行时键、工具白名单；**不等于** MCP Server。
- **工具 Skill（Tool Provider）** — 向注册表提供工具（`skills/*/server.py` 或 `logos.tools`）。
- **持久化档位 P0/P1/P2** — 产品 Skill 按对 KSFS/workspace/纯对话的依赖分类；见 **`Skill形态与Prompt工程.md` §4**。
- **Prompt Blueprint / Runtime Template** — L1 开发设计模板 vs L2 CB 拼装片段（L3 为 `messages[]`）。
- **单任务模式** — 默认产品路径；bounded 向导；**非**万能 Agent 聊天。
- **长对话 / 聊天启发** — 特殊 Skill（如 `chat_inspire`）；多轮但工具极少；启发语气。
- **技能面板** — GUI 默认首页（`/`）；列出可用 Skill。
- **档 B** — 任务本地缓存（`userData/conversations/*.json`）；`archived` / `disposed` 见 `DECISIONS.md` §13.7～§13.8。

---

## 子系统

- **Retrieval** — 统一检索；内部调度 HDL；属**基础设施层**。
- **MS（Model Serving）** — LLM 调用封装；属**基础设施层**。
- **MCP** — Model Context Protocol；Skills 与宿主进程通信的主要形态。
- **PL** — 偏好学习（远期）。

---

## 工作区与资源

- **`workspace/`** — 工作空间：草稿、工件、**`setting_entry/`** 等；**非** `ksfs_root`。
- **`example_ksfs/`** — 可提交的示例 KSFS 树。
- **`.index/`** — 向量索引与 HSI 等运行时数据（默认不入库）。

---

*最后更新：2026-05-16 — 增补任务、Skill、技能面板（第五阶段 GUI 定案）。*
