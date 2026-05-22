# 大纲规划 Skill（`outline_plan`）— 设计封存 · 开发暂停

> **状态（2026-05-22）**：**开发暂停**；manifest 与 Plan Phase A 接线（F5-09）**保留在仓**，供试验台与回归，**不作为**第六阶段产品竖切片推进项。  
> **恢复开发前**：请先在本文件与产品讨论定稿，再改 `skills/manifests/outline_plan.yaml` 与 `resources/prompts/`。  
> **关联**：**`范式路由与PR定案.md`**（`plan` 范式）、**`Skill形态与Prompt工程.md`**、**`PR开发文档.md`** PR-5 / Plan Phase A。

---

## 1. 当前实现快照（勿当作产品定稿）

| 项 | 现状 |
|----|------|
| **skill_id** | `outline_plan` |
| **范式** | `plan` — Phase A：单次 LLM，`json_mode=true`，SSE `delta` + `done` |
| **持久化档** | `p1`（规划稿，非 P0 设定导入） |
| **工具** | `allowed_tools: []` |
| **交付阶段** | F5-09 演示接线；**未**纳入 F6 主轴 |

**代码路径**：`src/logos/agent/plan.py`、`resources/prompts/paradigms/plan/base.md`、`resources/prompts/skills/outline_plan.md`。

**面板**：技能面板默认**隐藏**本 Skill（`SkillPanelPage` 过滤）；开发者仍可通过 **范式试验台** 选用。

---

## 2. 产品意图（待你定稿）

### 2.1 作家要解决什么问题

- 在**动笔写正文之前**，把「要写什么、分几步、每步产出什么」整理成**可审阅、可修改**的大纲。  
- **不是**执行大纲（不调工具改 KSFS、不自动开写章节）。  
- **不是**万能聊天（与 `chat_inspire` 分流）。

### 2.2 与相邻 Skill 的边界

| Skill | 关系 |
|-------|------|
| **`chat_inspire`** | 多轮启发；大纲规划应是 **单任务、结构化输出** |
| **`import_setting`** | P0 pipeline，落 `setting_entry`；大纲规划 **不写 KSFS**，除非未来显式「规划结果升格」Skill |
| **`lint_zh`** | 改稿；大纲在 **结构层**，语病在 **句子层** |

### 2.3 待定产品问题（讨论清单）

1. **输出形态**：仅 JSON（`title` + `steps[]`）？仅 Markdown 有序列表？二者并存时 GUI 如何预览/编辑？  
2. **输入**：仅「主题一句」？是否要附「已有设定摘要」「篇幅/体裁约束」多字段（`input_schema` 扩展）？  
3. **Phase B**：是否在 Logos 内 **执行** 某一步（调 `retrieve` / `read_ksfs`）？若否，是否导出到外部工具即可？  
4. **持久化**：规划结果存 **档 B 会话** 即可，还是 **另存 workspace 文件** / 晋升 KSFS？  
5. **与 `operating_mode`**：作者 vs 编剧是否影响大纲条令（当前产品倾向 **仅 author**，编剧模式暂缓）。  
6. **M-UI**：Task 页是「步骤卡片」还是「纯文本计划」？窄窗下如何折叠长计划？

---

## 3. 技术方向备忘（定案后再动代码）

### 3.1 范式与 PR

- 维持 **`paradigm: plan`**；Phase A 已满足「只生成计划」。  
- 若 Phase B 需要工具，再评估 `plan` + 受限 ReAct 或新子阶段类型（属 **平台版本**，非改 yaml 即可）。

### 3.2 Prompt / 资源

| 资源 | 用途 |
|------|------|
| `resources/prompts/paradigms/plan/base.md` | 范式头（JSON/Markdown 二选一或优先级） |
| `resources/prompts/skills/outline_plan.md` | 产品 Skill 片段（体裁、步骤粒度、禁止事项） |
| 可选 `skills/outline_plan/examples/` | 金样计划 JSON/Markdown，供单测与 stub |

### 3.3 GUI（恢复开发时）

- 路由：单任务 **`/task/:id`**（与 **`任务与Skill驱动GUI定案.md`** 一致）。  
- SSE：沿用 **`delta` + `done`**；**不**复用 `pipeline_step`（除非未来改为 pipeline 式多阶段计划生成）。  
- **`ui_instructions`** 仅来自 manifest / bootstrap，禁止 `TaskPage` 硬编码。

### 3.4 验收草案（恢复开发时填入计划）

- [ ] 面板可见（或刻意隐藏的策略写清）  
- [ ] Task：输入主题 → 收到可复制的步骤列表  
- [ ] pytest / Playwright 与 `API-V0.2` 契约一致  
- [ ] 与 `outline_plan` 相关的 e2e 不依赖「桩后端」假 JSON（若输出改为严格 JSON）

---

## 4. 恢复开发 Checklist

1. 产品在本文件 §2.3 逐项结论，更新 **「定案」** 小节（可另开日期标题）。  
2. 同步 **`skills/outline_plan/DESIGN.md`**、manifest、`outline_plan.md` Prompt。  
3. 从 **`第六阶段开发计划.md`** 或后续阶段计划中单列验收步（**不要**与 `import_setting` / G5 混 PR）。  
4. 取消 `SkillPanelPage` 对 `outline_plan` 的隐藏（若产品要上面板）。  
5. 跑通 `pytest` + `npm run test:e2e`。

---

## 5. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-05-22 | 初版：宣告开发暂停；整理待定问题与恢复清单；F5 接线状态快照。 |
