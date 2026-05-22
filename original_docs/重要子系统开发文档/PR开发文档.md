# Logos — PR（范式路由）开发文档（权威）

> **地位**：**`src/logos/agent/pr.py`** 及 **Shell / CB / 执行器** 分范式落地的**唯一实施与验收**依据。  
> **定案（语义）**：**`范式路由与PR定案.md`**（范式含义、与 ReAct 分工、Prompt 矩阵）。  
> **阶段排期**：第五阶段 **F5-03**（PR-1～PR-6 已结案，见 **`../已完成/第五阶段开发计划.md`**）；**`pipeline` 可执行** → **第六阶段 F6-02～F6-03**（**`../第六阶段开发计划.md`**）。  
> **不替代**：**`API-V0.2.md`**（HTTP 字段）、**`Skill形态与Prompt工程.md`**（manifest 全表）。  
> **冷启动**：做 PR 轨时 **@ 本文件 + `../第五阶段开发计划.md` §0**；阶段总排期以 F5-03 为准。

---

## 0. 新对话起手（仅 PR 轨）

1. **先决**：F5-01 manifest 可读；F5-02 `skill_id` + scoped registry（可与 PR-1 交错，**PR-3 前**须有 `lint_zh` 样例）。  
2. **阅读**：本文 §3 对应 **PR-x** 一步 + §4 最终验收；语义疑问再读 **`范式路由与PR定案.md`**。  
3. **现状**：`src/logos/agent/pr.py` 四范式类型已有，**运行时仍 `return "react"`** — PR-1 起改。  
4. **复制起手**：

```text
【Logos · PR 步 PR-x】
权威：重要子系统开发文档/PR开发文档.md §PR-x；第五阶段开发计划.md F5-03。
范围：src/logos/agent/、resources/prompts/paradigms/、api_v1.py（若接线）。
禁止：技能面板 UI、G5 /cache、设定导入 pipeline 全链。
验收：勾选 PR 文档 §3 本步 + pytest；契约行见第五阶段计划 §0.8。
```

| PR 步 | 依赖 | 做完可勾选 F5 |
|-------|------|----------------|
| PR-1 | F5-01 | F5-03 部分 |
| PR-2 | PR-1 | F5-03 部分 |
| PR-3 | PR-2 + F5-02 | **lint_zh 后端可跑** |
| PR-4 | F5-02 | scoped react |
| PR-5～6 | 可选 | F5-09 |

**F5-03 验收** = 本文 **§4** 第 1～3 条全部满足。

---

## 1. 范围与最终效果

### 1.1 本文件负责

| 模块 | 路径（预期） |
|------|----------------|
| PR | `src/logos/agent/pr.py` |
| 范式调度 | `src/logos/agent/shell.py`（或 `paradigm_runners.py`） |
| CB 分范式 | `src/logos/agent/cb.py` + `resources/prompts/paradigms/` |
| I&I 接线 | `src/logos/harness/ii_layer/api_v1.py`（读 manifest → 选执行器） |
| 注册表 | `src/logos/harness/sg_layer/`（按 Skill 裁 `allowed_tools`） |

### 1.2 第五阶段结束时的最终效果（PR 轨）

用户从 GUI 选定带 manifest 的 Skill 后：

1. **`select_paradigm(skill_id)`** 返回 manifest 中的 **`dialogue` / `react` / `plan` / `pipeline`**（默认**非**硬编码 `react`）。  
2. **`dialogue`**：`json_mode=false`，CB **不**注入 ReAct JSON-only system，SSE 输出自然语言。  
3. **`react`**：保持现行 ReAct + `parse_react_json`，但工具目录为 **Skill 白名单** 裁剪结果。  
4. **`plan`**：至少完成 **Phase A**（一次 LLM 产出计划对象/文本，展示给用户；**可不**自动执行 B）。  
5. **`pipeline`**：Shell **识别**并返回明确错误或未实现桩（**不**误走 ReAct）；完整流水线属**下阶段**（设定导入）。

### 1.3 非本文件范围

- 技能面板、Task 向导 UI（见 GUI 定案 + 第五阶段 F5-G 步）。  
- manifest 文件格式最终落盘路径（可与 F5-01 同步，但 UI 不管）。  
- PR **`paradigm_auto` 智能推断**（远期）。  
- Plan **Phase B** 全量执行器（第五阶段可选 PR-5，不阻塞阶段结案）。

---

## 2. 范式与执行器映射（实现对照表）

| `paradigm` | 执行器入口 | `json_mode` | CB 入口 |
|------------|------------|-------------|---------|
| `dialogue` | `run_dialogue_task(...)` | `false` | `build_dialogue_system_message` |
| `react` | `iter_run_task` / `run_react_loop` | `true` | `build_react_system_message` |
| `plan` | `run_plan_phase_a(...)` | 计划步可 `true` | `build_plan_system_message` |
| `pipeline` | `run_pipeline(skill_id, ...)` | 分步 | 各阶段片段，非 ReAct 外壳 |

---

## 3. 分步推进与验收

> **依赖**：**F5-01**（manifest 可读）、**F5-02**（`skill_id` + scoped registry）可与 PR-1 交错，但 **PR-3 前** 须有 manifest 与 `lint_zh` 样例。

### PR-0 — 定案入仓（文档）

| 项 | 内容 |
|----|------|
| **交付** | `范式路由与PR定案.md`、`Skill形态与Prompt工程.md` §4、`pr.py` 四范式类型注释 |
| **验收** | [ ] `DECISIONS.md` §14 互链；[ ] `pytest` 全绿（无行为变更） |

---

### PR-1 — manifest 接入 `select_paradigm`

| 项 | 内容 |
|----|------|
| **目标** | PR 从 **Skill 注册表** 读取 `paradigm`，不再写死 `react` |
| **交付** | `load_skill_manifest(skill_id)`（或等价）；`select_paradigm(skill_id, *, user_text=None) -> Paradigm`；未知 `skill_id` → 明确异常或 HTTP 400 |
| **禁止** | 在此步改 CB 文案或 SSE 形状 |
| **验收（自动）** | [x] `tests/test_pr_manifest.py`（新建）：已知 manifest 返回 `dialogue` / `react` |
| **验收（手动）** | [x] 单元调用对 `lint_zh` 返回 `dialogue` |

---

### PR-2 — CB：`dialogue` + Prompt 目录骨架

| 项 | 内容 |
|----|------|
| **目标** | L2 模板可按范式拼装；`dialogue` **无** ReAct JSON 条令 |
| **交付** | `resources/prompts/paradigms/dialogue/`、`persistence/p2/` 占位片段；`build_dialogue_system_message(skill_id, registry?, extra_system?)`；`compose_prompt(paradigm, persistence_tier, skill_id, ...)`（名称可调整） |
| **验收（自动）** | [x] 纯函数测：拼装结果**不包含**「每一轮必须只回复**一个** JSON」 |
| **验收（自动）** | [x] `lint_zh` 片段可被 compose 加载 |
| **验收（手动）** | [x] 打印 L3 preview：结构为 system + user，符合 Blueprint |

---

### PR-3 — Shell：`dialogue` 执行器 + `api_v1` 接线

| 项 | 内容 |
|----|------|
| **目标** | `skill_id` + `dialogue` 时走对话执行器并 SSE 流式正文 |
| **交付** | `run_dialogue_task`（流式 yield 与 `ReActStreamDone` 或统一 SSE 适配层）；`api_v1` 在 `chat` 中：`resolve_skill` → `select_paradigm` → 分支；**prompt_echo** 在 `dialogue` 下仍可用 |
| **交付** | `dialogue` **不**在回复前同步 `retrieval.query` 阻塞（与 prompt_echo 定案一致） |
| **验收（自动）** | [x] `tests/test_stream5_api.py`：`skill_id=lint_zh`（dialogue）返回自然语言且无 ReAct JSON 头；[x] **不**调用 exploding LLM（可选沿用 prompt_echo 测） |
| **验收（自动）** | [x] `tests/test_dialogue_paradigm.py`：流结束快于全库 retrieval（无检索阻塞） |
| **验收（手动）** | [ ] Electron：选 lint → 输入短句 → 收到**一份**无重复正文 → `streaming` 及时结束 |

---

### PR-4 — `react` 路径收口（scoped tools）

| 项 | 内容 |
|----|------|
| **目标** | `react` 仅见 manifest.`allowed_tools`；默认无 `skill_id` 时行为定案 |
| **交付** | `build_v01_guarded_tool_registry(..., allowed_tools=frozenset(...))`；无 `skill_id`：开发环境可保留全工具 + Obs 警告，**或** 400（须在 `API-V0.2` 写清） |
| **验收（自动）** | [x] 测：白名单 Skill 的 registry 名称集 = manifest 集 |
| **验收（自动）** | [x] 现有 `test_stream5_api` / MCP 测仍绿 |
| **验收（手动）** | [x] `react` Skill 对话中 LLM 仅能见声明工具（`retrieve_qa` 样例） |

---

### PR-5 — `plan` Phase A 雏形（可选，第五阶段末）

| 项 | 内容 |
|----|------|
| **目标** | 验证 Plan 范式接线，**不**要求执行 B |
| **交付** | `build_plan_system_message`；`run_plan_phase_a` 返回 plan 文本/JSON；GUI 或 API 将 plan 作为 assistant 一条展示 |
| **验收（自动）** | [x] 单测：demo skill `outline_plan` 返回含步骤列表的 JSON 或 Markdown |
| **验收（手动）** | [x] 用户可复制计划文本（Task 向导 SSE `delta` 展示） |

---

### PR-6 — `pipeline` 转发桩（第五阶段可仅文档）

| 项 | 内容 |
|----|------|
| **目标** | 避免 `pipeline` 误进 ReAct |
| **交付** | `select_paradigm` 返回 `pipeline` 时 Shell 调 `run_pipeline`；未实现则 SSE `error` code=`not_implemented` |
| **验收** | [x] 单测：`paradigm=pipeline` 不调用 `iter_run_task`（`test_dialogue_paradigm.py`） |

---

## 4. PR 轨最终验收（第五阶段结案门槛）

以下条件 **全部** 满足时，PR 轨视为第五阶段结案：

| # | 条件 | 状态 |
|---|------|------|
| 1 | `select_paradigm` **仅** 以 manifest 为准（除显式 developer 覆盖外无硬编码 `react`） | [x] `test_pr_manifest.py` |
| 2 | 至少 **一个** `dialogue` Skill（`lint_zh`）端到端：API + GUI，自然语言输出，无 ReAct JSON 强塞 | [x] API + e2e 竖切片 |
| 3 | 至少 **一个** `react` Skill 在 **scoped tools** 下端到端 | [x] `retrieve_qa` |
| 4 | `plan`：PR-5 完成 **或** 明确推迟并在 `第五阶段开发计划.md` 标注顺延 | [x] F5-09 `outline_plan` |
| 5 | `pipeline`：PR-6 不误路由；设定导入不在本阶段冒充完成 | [x] `test_pipeline_paradigm_not_implemented` |
| 6 | `pytest` 全绿；契约 PR 含 `契约：` 行 | [x] F5-10：146 passed；改契约须 `契约：` 提交行（见 API 纪律） |
| 7 | Prompt 目录存在 `paradigms/dialogue`、`paradigms/react`、`persistence/p0|p1|p2` 骨架 | [x] `resources/prompts/` |

---

## 5. 测试与契约纪律

- 改 `api_v1.py` 行为 → 同步 **`API-V0.2.md`** + `tests/test_stream5_api.py` + 前端类型（若涉及 `skill_id`）。  
- 仅改 `pr.py` / `cb.py` / 新执行器 → 新增 `tests/test_pr_*.py` / `tests/test_dialogue_*.py`。  
- **禁止** 在无 `skill_id` 时默认 `dialogue` 冒充产品路径（开发默认须显式 Skill）。

---

## 6. Cursor 起手模板

```text
【Logos · PR 步 PR-x】
权威：重要子系统开发文档/PR开发文档.md §x、范式路由与PR定案.md。
范围：src/logos/agent/、resources/prompts/paradigms/、api_v1.py（若接线）。
禁止：技能面板 CSS、G5 缓存页、设定导入 pipeline 全链。
验收：列出 PR开发文档.md 对应勾选；pytest；契约：…。
```

---

## 7. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-05-16 | 初版：PR-0～PR-6、最终效果与最终验收、与第五阶段 F5-03 对齐。 |
| 2026-05-20 | §0 新对话起手表、与 F5-01/02 依赖说明。 |
| 2026-05-21 | §4 PR 轨最终验收全表勾选（F5-10 结案）；PR-5 `outline_plan` 已交付。 |
