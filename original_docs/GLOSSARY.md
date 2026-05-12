# 术语表（Glossary）

> 快速索引。**现行权威**：**`ARCHITECTURE.md`**、**`重要子系统开发文档/KSFS开发.md`**、**`DECISIONS.md`**。归档 SPEC 仅供历史对照。

---

## 系统与模式

- **Logos** — 游戏叙事架构智能体；作家 / 编剧双运行模式（OM）按需切换。
- **OM** — 运行模式（Operating Mode）。顶层角色：**AM（作家）**、**SM（编剧）** 等。
- **Shell** — Agent 调度器：确定性路由、端口调用、任务边界。
- **CB（Context Builder）** — 对话历史、Prompt 模板、上下文预算；资产默认 **`resources/prompts/`**。
- **PR（Paradigm Router）** — Agent 范式路由（默认 ReAct）。

---

## 分层

- **基础设施层** — 进程内内部 API：**Retrieval**、**MS**、**`logos.tools`** 等；**非** MCP Skills。
- **能力层（Skills）** — MCP Server；注册表、渐进式披露；位于 **`skills/`**。
- **I&I** — Interface & Integration：HTTP、**SSE**、GUI、CLI、**组合根**（`harness/ii_layer`）。
- **S&G** — Security & Governance：沙箱、工具白名单、输出治理、**MCP 进程治理**（`harness/sg_layer`）。
- **Obs** — 可观测性；统一日志，默认 **`logs/`**。
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

*最后更新：2026-05-12 — 对齐 KSFS/HDL 现行模型与本会话定案。*
