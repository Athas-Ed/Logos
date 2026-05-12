# 设定导入 Skill 开发（封存规格）

> **地位**：**产品/架构讨论结果的封存稿**；与 **`KSFS开发.md` §7.3**、**`DECISIONS.md` §12** 冲突时以二者为**现行权威**；本文件负责 **收束已定方向、路径与分工**，便于下阶段开箱即做。  
> **状态（2026-05-12）**：**当前开发计划内不实现**「设定导入」全链（含 MCP Skill、渲染落盘、与导入绑定的晋升自动化）；**本阶段重心为 KSFS 本体**（HSI、登记、SVS、E2E 等，见 [`../下一阶段开发计划.md`](../下一阶段开发计划.md)）。恢复开发时以本文为起点更新 `KSFS开发.md` / `DECISIONS.md` 与代码。

---

## 1. 范围与分层（已定方向）

| 层级 | 物理位置 | 职责 |
|------|-----------|------|
| **Skill（MCP）** | `skills/<包名>/`（新建，如 `settings-import-mcp/`，实现期再定） | **Agent 可见入口**：收粘贴/参数 → 调 LLM 产出 JSON → 调用下游校验/写盘（本机 API 或受控工具）；经 **`GuardedToolRegistry`** 等治理接入对话。 |
| **HDL / 底座** | `src/logos/persistence`、`src/logos/tools` 等 | **确定性**：JSON Schema 校验、按 `render_spec` 写 **`workspace/setting_entry/`**、**`DraftPromotionPort`** 晋升、`sync_ksfs_hsi` / HSI 发号回写。 |
| **契约** | **`resources/entity_template/<profile>/`**（已备 MVP：`default_import_v0`） | **单一来源**：`manifest.yaml`、`schema.json`、`render_spec.yaml`、`llm_instructions.md`、`examples/` 金样；Skill **只引用**，勿维护第二套 schema。 |

**全局流水线（产品语义，摘自 `DECISIONS.md` §12.1）**：

粘贴/触发 Skill → LLM 输出 JSON → JSON Schema 校验 → 本地按渲染规格写 `workspace/setting_entry/` 草稿 → 人审 → 晋升 `ksfs_root`；持久 `id` 仅在落户后由 HSI 分配。

**与 MCP 总能力（A2）的关系**：本仓库 **`skills/example-stdio-mcp`** 为通用 MCP 示例；**设定导入**为**独立 Skill 包**，可与 A2 并行设计，但**本阶段均不要求为交付设定导入而完成**。

---

## 2. 目录与配置（已定案）

### 2.1 `workspace/setting_entry/`（Setting Entry）

- **含义**：**待落户**设定草稿根（设定导入渲染产物默认落此，晋升前 **不** 视为 KSFS 事实源）。  
- **说明文件**：仓库根 **`workspace/setting_entry/README.md`**（`.gitignore` 对该文件例外，可提交）。  
- **配置**：`config/defaults.yaml` 中 **`paths.setting_entry_subdir`**（默认 `setting_entry`）；代码辅助 **`logos.tools.setting_entry_directory`**。

### 2.2 实体模板 MVP

- **路径**：`resources/entity_template/default_import_v0/`  
- **内容**：`manifest.yaml`、`schema.json`、`render_spec.yaml`、`llm_instructions.md`、`examples/`（含最小与含 `suggestions` 金样）。  
- **配置**：`paths.entity_template_root`、`paths.entity_template_profile`（默认 `default_import_v0`）。  
- **总说明**：`resources/entity_template/README.md`。

---

## 3. 契约要点摘要（自原「下一阶段计划 §2.6」迁入）

### 3.1 `manifest.yaml`（建议最小字段）

- `profile_id`、`version`；`schema`、`render`、`llm_instructions`（相对 profile 目录）；`drafts_subdir: setting_entry`；`notes`；`extras` 占位（KG、黑白名单路径等）。

### 3.2 `schema.json`（硬闸门）

- 顶层：`batch_id`、`source_label`（可选）、`units[]`。  
- `units[]`：`classification`（`character` | `location` | `item` | `faction` | `lore_note`）、`slug`（安全字符集）、`title`（可选）、`body_markdown`、`suggestions`（可选，`verbatim_quote` + `message`）。  
- **不含** LLM 填写的持久 **`id`**。

### 3.3 `llm_instructions.md`

- 强制仅输出 JSON、字段与枚举与 schema 同源、拆分粒度与黑名单式软约束；详见该文件正文。

### 3.4 `render_spec.yaml`

- `classification` → 相对 **`setting_entry/` 根** 的路径模板；`front_matter_keys_allowlist`；`draft_id_placeholder: 待分配`；章节顺序（front matter → 标题 → 正文 → 可选「修改建议」）。

### 3.5 草稿 `id`（已定案）

- 草稿 front matter **`id: 待分配`**；落户后由 HSI 发号回写。  
- **「修改已落户实体」** Skill：下阶段规格；**不改变**已有实体 **`id`**。与 **`KSFS开发.md` §3.4**（导入稿 `id` 与 HSI 冲突）的衔接在实现 PR 用测试钉死。

### 3.6 S&G 接入顺序（讨论结论）

- **可先**用 **窄路径白名单** 跑通校验→渲染→`setting_entry`→（可选）晋升，再与 **`GuardedToolRegistry`** 完全同源。

### 3.7 重叠检测（讨论结论）

- **推荐时机**：Schema 通过后、写 `setting_entry` 前或后、晋升前；**本地只读**扫描，**禁止** LLM 判定；输出 `warnings[]`。  
- **本链路上不做的能力**：**「KSFS 修改」**（已落户实体）另立规格与 Skill；与导入 **分流**（`DECISIONS.md` §12、`KSFS开发.md` §7.3.1）。MVP 可不做重叠检测但须在产品说明中声明。

### 3.8 HSI 表结构（方案备忘，以 A4 实现为准）

- 主表建议：`id`、`rel_path` UNIQUE、`body_sha256`、`mtime`/`mtime_ns`、`indexed_at`、`kg_json` NULL 预留。

### 3.9 SVS / 检索与导入的关系（讨论结论）

- 多批导入 **不必** 每批全量重建 SVS；**脏集合** 驱动增量。  
- **触发**：进入 Retrieval 主路径前 **短路判断** 是否需增量 SVS；**手动「检查设定库更新」** 强制置对账标志；与 **§3.2「登记至多一次」** 钩子拆分实现（详见 `KSFS开发.md` §3.2）。

### 3.10 `DraftPromotionPort`（释义）

- **窄端口**：`list_promotion_candidates`、`apply_promotion`（含 **mtime 校验**）；CLI（A7）为薄壳。晋升目标为 **`ksfs_root`**。

### 3.11 KG / 黑白名单

- **占位**：`manifest.extras` 预留键；实现可留空分支。

---

## 4. 与本阶段 KSFS 工作的边界

- **仍要做（本阶段）**：**§3.8** 所涉 HSI 发号回写、自动登记、SVS chunk、**与「导入」无关的** `DraftPromotionPort` + CLI（若产品需要：任意 `workspace` 草稿晋升至 KSFS 的通用能力，或仅文档层先定义端口）。  
- **不做（本阶段）**：MCP **设定导入** Skill 包、LLM 编排导入、按 `entity_template` **自动**写 `setting_entry`、导入管线专用重叠检测 UI。  
- **仓库内已存在、可冻结不动**：`default_import_v0` 全套文件、`AppSettings` 中与 `setting_entry` / `entity_template` 相关的键（无运行时依赖亦可保留，便于下阶段接线）。

---

## 5. 恢复开发时的建议 Checklist

1. 打开 **`KSFS开发.md` §7.3** 与 **`DECISIONS.md` §12**，对照本文若有漂移则先改权威文档再写代码。  
2. 在 `skills/` 下新建 MCP 包，工具 schema 与 **`schema.json`** 对齐或引用。  
3. 在 `logos.persistence`（或约定包）实现：校验 → 渲染 → 写 `setting_entry`；单测对齐 **`examples/*_expected.md`**。  
4. 接 **`DraftPromotionPort`** 与 HSI 登记；再接 S&G 全量规则。  
5. 更新 [`../下一阶段开发计划.md`](../下一阶段开发计划.md) 将 4.4 / A6 重新纳入排期与验收。

---

## 6. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-05-12 | 初版：封存讨论结论；声明本阶段不实现设定导入全链；迁入原下一阶段计划 §2.6 要点；指向 `default_import_v0` 与配置键。 |
