# Logos — 范式路由（PR）与 Agent 范式定案

> **地位**：**Agent 决策层**中 **PR（Paradigm Router）** 与 **Shell** 如何分工的权威说明；与 **`Skill形态与Prompt工程.md`**（产品 Skill manifest）、**`ARCHITECTURE.md`** §2.1、**`Harness Engineering文档.md`** 配套。  
> **代码锚点**：`src/logos/agent/pr.py`（当前仅 `react`）、`shell.py`、`cb.py`、`react.py`。  
> **实施步骤**：**`PR开发文档.md`**（PR-0～PR-6、最终验收）。  
> **定案日期**：2026-05-16

---

## 1. PR 在栈中的位置

```text
用户选产品 Skill（skill_id）
        │
        ▼
  manifest.paradigm  ──►  PR（确认或将来推断）  ──►  Shell 调度具体执行器
        │                        │
        │                        ├─ dialogue  → 对话执行器（自由文本 LLM）
        │                        ├─ react     → ReAct 循环（JSON-only 协议）
        │                        ├─ plan      → Plan 雏形（先计划、再分步，见 §4）
        │                        └─ pipeline  → 非 LLM 范式路由（确定性流水线，见 §5）
        ▼
  CB：按「范式 × 持久化档位」选 Prompt 模板族（L2）
        ▼
  S&G：按 Skill 裁 scoped tool registry
```

**定案**：

| 层级 | 谁决定 | 说明 |
|------|--------|------|
| **产品 Skill 开发时** | 作者在 manifest **预先指定 `paradigm`** | 第五阶段默认路径；用户从面板选 Skill 即选定范式 |
| **PR（现行）** | 读取 manifest，**透传**指定范式 | `pr.py` 扩展为 `select_paradigm(skill_id, …) → manifest.paradigm` |
| **PR（远期）** | 在 manifest 为 `auto` 时，根据任务输入 **推断** 范式 | 不与「Skill 预绑定」冲突；推断仅作覆盖或建议 |

**不采用**：所有任务运行时都由 PR「智能自选」范式而 Skill manifest 不写范式 —— 与「任务驱动、能力边界清晰」冲突。智能路由是 **增强**，不是替代 Skill 预绑定。

---

## 2. 范式一览（与 ReAct 分工）

| 范式 ID | 中文名 | LLM 协议 | 典型工具 | 与 ReAct 关系 |
|---------|--------|----------|----------|----------------|
| **`dialogue`** | **对话范式**（自由文本） | **非** ReAct JSON；`json_mode=false`；自然语言 / Markdown 输出 | 通常无；或宿主预检索后写入 context | **并列**，非 ReAct 子集 |
| **`react`** | **ReAct 范式** | 每轮单一 JSON：`thought` / `final_answer` / `action`；`json_mode=true` | 白名单内工具，每轮至多一次 `action` | **现行默认实现** |
| **`plan`** | **Plan 范式**（雏形） | 计划阶段：结构化 **计划对象**（JSON 或编号列表）；执行阶段：见 §4 | 计划步映射到 tool 或子调用 | 先 Plan 再 **分步** ReAct/dialogue，非替代 ReAct |
| **`pipeline`** | **流水线范式** | 按阶段选用 L2 片段；某步可 `json_mode=true`（对齐 **entity schema**），**无** ReAct 外壳 | 进程内工具为主 | **不走** PR 的 ReAct 循环；Shell 调专用 runner |

**「自由范式」= `dialogue`**：不在 CB 注入「每轮必须 JSON」的 ReAct system；Prompt 模板可含语气、章节、示例、输出格式说明。

---

## 3. 对话范式（`dialogue`）

### 3.1 适用 Skill

- 语病检查、逻辑漏洞、聊天启发（`chat_inspire`）、纯分析/建议类。  
- **P2** 为主；**P1** 若仅写短草稿且不需 ReAct 亦可。

### 3.2 执行语义

| 项 | 定案 |
|----|------|
| **CB** | `build_dialogue_system_message(skill_id, registry?)`：通用头 + Skill 要求 +（可选）压缩工具说明；**无** JSON-only 条令 |
| **LLM** | `json_mode=false`；`stream_completion` 直出正文 |
| **多轮** | manifest `turn_policy: multi` 时保留 `messages[]` 历史；仍 bounded 在任务内 |
| **工具** | 默认 **不** 暴露 ReAct 工具目录；若需 `retrieve`，优先 **宿主先执行** 再将结果注入 user/context（减少模型乱调工具） |

### 3.3 开发简化

对话类 Skill 的 **Blueprint** 只写：角色、输入输出、示例、禁止项；**不写** `action`/`final_answer` JSON 示例。

---

## 4. Plan 范式（`plan`）— 雏形定案

> **目标**：支撑「先拆步骤、再执行」的 Skill（复杂大纲、多文件写作准备）；**第五阶段不强制实现完整 Plan 引擎**，先定接口与 Prompt 族，实现可分步。

### 4.1 两阶段（逻辑）

```text
Phase A — 规划（Plan）
  输入：task_input + Skill 要求 +（可选）retrieve 摘要
  输出：计划对象 plan（JSON 或 Markdown 编号列表，manifest 定一种）
  LLM：json_mode 由 manifest.plan_output_schema 决定（建议 true 仅用于 Plan 步）

Phase B — 执行（Execute）
  对 plan.steps[] 逐步：
    - 若步类型 = tool  → 确定性调 registry（不经 ReAct JSON）
    - 若步类型 = llm    → 单步 dialogue 或单步 react（manifest 可指定 execute_sub_paradigm）
  汇总为任务结果
```

### 4.2 第五阶段最小实现（建议）

| 级别 | 交付 | 验收 |
|------|------|------|
| **P0 文档** | manifest 字段 `plan_*`、Blueprint 章节、示例 JSON schema | 本文 + Skill 形态文档 |
| **P1 代码** | `plan` 仅 **A 阶段**：一次 LLM 输出计划文本/JSON，**不**自动执行 B；结果展示给用户 | 单测 + 一个 demo Skill |
| **P2 代码** | B 阶段执行 1～2 种步类型（如 `retrieve` + `dialogue` 小结） | 集成测 |

**与 ReAct 分工**：Plan **不**取代 ReAct；复杂工具循环仍用 `react`；Plan 适合 **步骤可读、可人审** 的任务前置。

### 4.3 manifest 扩展（plan 专用，可选）

| 字段 | 说明 |
|------|------|
| `plan_output_format` | `json_steps` \| `markdown_list` |
| `plan_max_steps` | 计划最多步数 |
| `execute_sub_paradigm` | 执行步默认 `dialogue` \| `react` |

---

## 5. 流水线范式（`pipeline`）

**不经过 PR 的「每轮 LLM 范式选择」**；manifest `paradigm: pipeline` 时 Shell 调 **`run_pipeline(skill_id, task_input)`**（实现期模块名可调整）。

- **设定导入**、晋升、schema 校验、本地渲染等 = **确定性代码 + 局部 LLM**。  
- Prompt：**按阶段**挂载 L2 片段；某步要求 **entity JSON** 时对该步单独 `json_mode=true`，**不是** ReAct 的 `thought/action` 格式。

PR 对 pipeline 的职责仅为：识别并 **转发到 pipeline runner**，不与 dialogue/react 并列循环。

---

## 6. Prompt 模板族：范式 × 持久化档位

产品 Skill 开发时，除 manifest 外，在 **`resources/prompts/`** 按矩阵组织 **L2 Runtime Template**（CB 片段键）：

```text
resources/prompts/
├── _shared/                    # 全局头、OM 后缀、返回规则片段
├── paradigms/
│   ├── dialogue/
│   ├── react/
│   └── plan/                   # 含 plan_phase_a、plan_phase_b 子键
├── persistence/                # 按 P0/P1/P2 的附加约束片段
│   ├── p0_workspace_ksfs.md
│   ├── p1_workspace_only.md
│   └── p2_messages_only.md
└── skills/<skill_id>/          # 本 Skill 专有片段（覆盖或追加）
```

**拼装顺序（定案）**：

```text
_shared.* 
+ paradigms.<paradigm>.* 
+ persistence.<persistence_tier>.* 
+ skills.<skill_id>.*
+ task_input（用户输入）
+ history（若 multi）
```

**L1 Blueprint** 须注明：本 Skill 的 `paradigm` + `persistence_tier`，并指向上述目录中作者应维护的片段清单。

| 矩阵示例 | dialogue + P2 | react + P2 | plan + P1 | pipeline + P0 |
|----------|---------------|------------|-----------|---------------|
| 持久化片段 | 无写盘要求 | 无写盘要求 | workspace 可选 | 晋升/人审闸门 |
| 范式片段 | 自由语气、Markdown | JSON-only + 工具目录 | 计划 JSON + 执行说明 | 分阶段说明、schema 引用 |
| 典型 Skill | lint、chat_inspire | 检索后多步推理 | 大纲规划（雏形） | 设定导入 |

---

## 7. manifest 字段（与 Skill 形态文档合并口径）

**`paradigm`** 取代原「编排档案」口语，**统一由 PR 消费**：

| 字段 | 必填 | 值 |
|------|------|-----|
| `paradigm` | 是 | `dialogue` \| `react` \| `plan` \| `pipeline` |
| `persistence_tier` | 是 | `p0` \| `p1` \| `p2` |
| `turn_policy` | dialogue/plan 常用 | `single` \| `multi` |
| `prompt_runtime_key` | 是 | 指向 `skills/<skill_id>/` 或拼装键 |
| `allowed_tools` | react/plan/pipeline 按需 | 工具名列表 |
| `paradigm_auto` | 否 | 默认 **false**；为 true 时允许 PR 推断（远期） |

**废弃口语**：`orchestration_profile` 与 `paradigm` 重复时，**只保留 `paradigm`**。

---

## 8. 实现路线图（与第五阶段对齐）

**分步实施与 PR 轨验收**以 **`PR开发文档.md`（PR-0～PR-6）** 为准；阶段总排期以 **`../第五阶段开发计划.md`（F5-00～F5-10）** 为准。

| 阶段步 | 内容 |
|--------|------|
| **F5-03** | PR 轨：PR-1～PR-4（必选），PR-5/6（可选） |
| **F5-05～F5-07** | GUI + `lint_zh` / `chat_inspire`（dialogue） |
| **F5-08** | `react` scoped + `bootstrap.skills` |
| **远期** | Plan B 执行、PR `paradigm_auto` 推断、`pipeline` 设定导入全链 |

---

## 9. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-05-16 | 初版：dialogue/react/plan/pipeline；Skill 预绑定范式；范式×持久化 Prompt 矩阵；Plan 雏形。 |
