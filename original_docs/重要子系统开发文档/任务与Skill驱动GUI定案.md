# Logos — 任务与 Skill 驱动 GUI 定案（第五阶段产品主轴）

> **地位**：**作家模式 GUI 的产品与信息架构权威**（2026-05-16 定案）。  
> **取代范围**：不推翻 **`DECISIONS.md` §13** 的 Electron、档 B 缓存、标签切换、窄窗等**工程定案**；**取代**「默认入口为万能 Agent 聊天页」的**隐含产品假设**。  
> **关联**：分层见 **`../ARCHITECTURE.md`**；HTTP/SSE 字段表见 **`API-V0.2.md`**；**第五阶段排期**见 **`../第五阶段开发计划.md`（F5-00～F5-10，取代旧 T0～T3）**；PR 实施见 **`PR开发文档.md`**；**`GUI开发文档.md` §11**。

---

## 1. 产品终极形态（摘要）

| 维度 | 定案 |
|------|------|
| **物理形态** | 占据**很小屏幕**的**独立写作助手**（Electron；窄窗约 1/4 屏为日常目标，见 `DECISIONS.md` §13）。 |
| **交互主轴** | **任务（Task）驱动**，而非用户自由对话驱动。 |
| **能力单元** | **Skill**：基于底层工具与 CB/机制封装而成的**高级、可独立**功能；Skill 之间可按 manifest **显式**互相调用，**禁止**默认向 LLM 暴露全工具目录。 |
| **两种使用模式** | **单任务模式**（默认、优先）与 **长对话模式**（特殊 Skill，非默认首页）。 |

---

## 2. 两种模式

### 2.1 单任务模式（主路径）

**定义**：用户从**技能面板**显式选择一个 Skill，按**固定向导**完成一次 bounded 工作；任务结束则会话进入档 B 生命周期（`idle` → 用户 **归档** → `archived` / **`/cache`** 治理）。

**标准三步（定案）**：

```text
① 选择 Skill   →  ② 输入本任务要处理的文本/参数  →  ③ 组装 Context 并执行（SSE/短流）
```

| 步 | 用户可见 | 系统职责 |
|----|----------|----------|
| **① 选 Skill** | 技能面板（网格/列表）；每项有名称、简述、图标占位 | 加载 Skill **manifest**（允许的工具、CB profile、是否流式、是否 ReAct） |
| **② 输入** | 单任务输入区（粘贴正文、路径参数等由 manifest 声明） | **不**启动 LLM；校验输入；可选预览将送入 CB 的字段 |
| **③ 执行** | 进度/流式结果；**完成**后提供「结束任务 / 归档」 | 按 Skill 注册 **scoped tool registry**；组装 `messages[]` 或 Skill 专用请求体；调用 `POST /api/v1/chat`（或未来 `POST /api/v1/tasks/run`） |

**与通用 Agent 的差异**：

- **渐进式披露**：仅 manifest 列出的 **进程内工具 + MCP 工具** 进入 LLM 工具列表；其他 Skill、其他 MCP **不暴露**。
- **无「先聊再选能力」**：禁止首屏即空白多轮聊天 + 全工具 ReAct 作为默认。
- **任务边界清晰**：完成即进入「可归档」状态；持久化进 KSFS 走**专用 Skill / 持久化轨**，**不**与会话 JSON 混语义（见 `DECISIONS.md` §13.5 档 C）。

### 2.2 长对话模式（特殊 Skill）

**定义**：面板上的独立入口（如 **「聊天启发」**），在任务模型上仍是 **一个 Skill 实例 = 一个会话（任务）**。

| 项 | 定案 |
|----|------|
| **产品职责** | **启发**作者：询问、建议、推敲语气；**不**承担「落实某具体功能」（语病检查、导入设定等由单任务 Skill 负责）。 |
| **工具暴露** | **刻意极少**（manifest 写死；实现期可仅 `retrieve` 或零工具 + 纯对话，由 Skill 作者定义）。 |
| **范式** | 允许多轮 `messages[]`，但 **UI 仍属任务向导的「执行步」变体**，而非无限 Agent 工作台。 |
| **与现行 `/chat/:id` 关系** | 实现可**复用**现有 `ChatPage` + SSE 管线，但路由/元数据须带 **`skill_id: chat_inspire`**（标识符实现期可调）；**禁止**作为应用默认首页。 |

---

## 3. 核心概念对照

| 概念 | 含义 | 档 B / GUI |
|------|------|------------|
| **Skill** | 可注册能力包；manifest 规定工具子集、CB、输入 schema、是否多轮 | 面板展示；不单独占 JSON 文件 |
| **任务（Task）** | 用户一次「选 Skill → 输入 → 执行」的**完整工作单元** | **等价于** §13 的「会话」；`conversation` JSON 增加任务字段（§6） |
| **会话 / 标签** | 进行中的任务槽位；**同时仅一个占满工作区** | 顶栏标签 = **任务切换**；非「又一个万能聊天」 |
| **任务完成** | 用户确认结束或 Skill 返回终态 | `status` → 可归档；引导 **`/cache`** 或顶栏归档 |
| **档 B 缓存** | 任务本地 JSON；跨重启恢复 | **保留**现行 Electron IPC + `ConversationProvider` 方向 |
| **档 C（KSFS）** | 落户、作品级保存 | **仅** 用户显式触发专用 Skill（见 `会话保存Skill文档.md`） |

---

## 4. 信息架构（路由与首页）

### 4.1 路由定案（目标态）

| 路由 | 用途 | 备注 |
|------|------|------|
| **`/`** | **技能面板（首页）** | 默认 `loadURL` / Router 重定向目标 |
| **`/task/:id`** | 单任务向导 + 执行 UI | 推荐新路径；实现期可与 `/chat/:id` 并存过渡 |
| **`/chat/:id`** | **过渡**：长对话 Skill 或旧链兼容 | F5-07 后降为别名或仅 `chat_inspire` |
| **`/settings`** | 全局设置、诊断 | **保留** |
| **`/cache`** | 已归档任务列表 | **保留** §13.8 |

### 4.2 首页禁止事项

- **禁止** 冷启动直达空白 `ChatPage` + 全工具 Agent。  
- **禁止** 在顶栏增加与技能无关的「新对话」作为**唯一**主 CTA（可保留为 **「聊天启发」Skill** 的快捷入口）。

### 4.3 窄窗布局优先级

1. 技能面板（可滚动网格）  
2. 单任务当前步（全宽）  
3. 顶栏：标签（进行中任务）+ 设置；**无** 常显会话侧栏（与 §13.3 一致）

---

## 5. Skill manifest（逻辑模型，实现期落盘）

> **形态与 Prompt 分层**（产品 Skill vs 工具 Skill、P0/P1/P2、Blueprint）：**`Skill形态与Prompt工程.md`**。  
> 物理位置建议：`skills/<skill_id>/` 与 MCP 元数据并列；**本文只定任务侧语义**，不绑定单文件格式。

| 字段 | 说明 |
|------|------|
| **`skill_id`** | 稳定标识，如 `lint_zh`、`import_setting`、`chat_inspire` |
| **`persistence_tier`** | `p0` \| `p1` \| `p2`（持久化依赖档位，见 Skill 形态文档 §4） |
| **`prompt_runtime_key`** | CB 运行时模板组键（L2） |
| **`display_name` / `description`** | 技能面板卡片标题与**一句话**摘要 |
| **`ui_instructions`** | 任务页、对话页 **「技能说明」** 区块正文（多行 YAML）；经 **`bootstrap.skills[]`** 注入 GUI，**禁止**在 `TaskPage` / `ChatPage` 按 skill 硬编码 |
| **`input_schema`** | 第二步表单：纯文本 / 文件路径 / 多字段 |
| **`allowed_tools`** | 进程内工具名 + MCP 工具名白名单 |
| **`allowed_skill_calls`** | 可选；允许调用的其他 `skill_id` 列表 |
| **`cb_profile` / `extra_system`** | CB 模板键或追加 system |
| **`paradigm`** | `single_shot` \| `react_bounded` \| `multi_turn` |
| **`presentation_default`** | 继承 `bootstrap` 或覆盖 |
| **`stream`** | 是否 SSE |
| **`on_complete`** | `archivable` \| `needs_review` 等 UI 提示 |

**S&G**：组合根在收到 `skill_id` 后构造 **仅含 `allowed_tools`** 的 registry（与 `build_v01_guarded_tool_registry` 对齐，见 `Harness Engineering文档.md`）。

---

## 6. 档 B 会话 JSON（`schema_version` 升级方向）

现行 **`schema_version: 2`**（F5-06）以 `messages[]` + Skill 元数据为中心；读盘仍兼容 **v1**（迁移策略见下）：

| 字段 | 类型 | 说明 |
|------|------|------|
| **`skill_id`** | string | 本任务绑定的 Skill |
| **`task_phase`** | enum | `select` \| `input` \| `running` \| `done` \| `failed` |
| **`task_input`** | object | 第二步用户输入（结构依 Skill） |
| **`title`** | string | 默认 `display_name` + 输入摘要 |
| **`messages`** | array | 第三步及以后才有；单任务单次 shot 可为空或仅 assistant |
| **（保留）** | | `operating_mode`、`presentation`、`citations`、`tool_trace_log`、`status` |

**命名**：对外仍称「会话缓存」；文档与 UI 对用户优先称 **「任务」**。

---

## 7. HTTP / 契约演进（定案方向，未实现）

现行 **`POST /api/v1/chat`** 保持；第五阶段 **推荐** 在请求体增加（契约轨单 PR）：

```json
{
  "skill_id": "lint_zh",
  "task_input": { "text": "……" },
  "messages": [],
  "operating_mode": "author",
  "presentation": "work"
}
```

| 规则 | 说明 |
|------|------|
| **`skill_id` 必填**（目标态） | 缺省则 **400** 或仅开发环境回退 `chat_inspire`（实现期二选一，写入 API-V0.2） |
| **无 skill 的全工具路径** | **废弃为默认**；可保留 `developer` 开关用于调试 |
| **Prompt 回显** | 仍属开发者能力；归属 **设置页**；与 Skill 正交 |
| **bootstrap 扩展** | `skills[]` 含 `display_name`、`description`、`ui_instructions` 等（契约轨，见 **API-V0.2** §2.1） |

---

## 8. 与第四阶段 GUI 成果的关系

| 已实现（G1～G4 等） | 第五阶段态度 |
|---------------------|--------------|
| Electron 壳、健康门、preload | **保留** |
| `ConversationProvider`、多标签、后台 SSE 队列 | **保留**；语义改为**多任务槽** |
| `/settings`、`/cache` 占位 | **保留**；G5 缓存页仍可做 |
| **`ChatPage` 为默认首页** | **废弃**（产品层） |
| 对话页内运行模式/展示档位 | **已迁设置页**；任务级覆盖由 manifest 决定 |
| 无 `skill_id` 的 ReAct + 全工具 | **冻结**；仅 `chat_inspire` 或开发者模式可用 |

---

## 9. 实施阶段

**唯一排期**：**`../第五阶段开发计划.md`（F5-00～F5-10）**；旧 T0～T3 表**废止**。PR 细节见 **`PR开发文档.md`**。

| 阶段步 | 要点 |
|--------|------|
| **F5-04～F5-05** | 技能面板 + Task 向导 + `lint_zh` 竖切片 |
| **F5-07** | `chat_inspire`（长对话 Skill） |
| **F5-03、F5-08** | PR 轨 + `react` scoped + `bootstrap.skills` |

**冻结至 F5-05 完成**：G5 全功能 `/cache`、M-UI 大改、多标签边缘体验细化。

---

## 10. 首发 Skill 清单（草案，可增删）

| `skill_id` | 模式 | 说明 | 工具倾向（草案） |
|------------|------|------|------------------|
| **`import_setting`** | 单任务 | 导入设定（粘贴 → 结构化 → `workspace/setting_entry/`） | 专用流水线 + 最少只读 KSFS |
| **`lint_zh`** | 单任务 | 检查一段中文语病 | 无工具或单次 LLM |
| **`chat_inspire`** | 长对话 | 聊天启发 | `retrieve` 可选；**无** MCP 天气等 |
| （远期）**`ksfs_edit`** | 单任务 | KSFS 修改提案 | `retrieve`、`read_ksfs`、受控写 |

---

## 11. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-05-16 | 初版：任务/Skill 主轴、单任务三步、长对话为特殊 Skill、路由与 JSON。 |
| 2026-05-16 | §9 对齐 F5-00～F5-10；排期见第五阶段开发计划。 |
