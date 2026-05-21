# Logos — Skill 形态与 Prompt 工程（定案）

> **地位**：**产品 Skill**（用户可选、任务驱动）的**语义与 Prompt 分层**权威；与 **`任务与Skill驱动GUI定案.md`**、**`DECISIONS.md` §14** 配套。  
> **不替代**：**`MCP开发.md`**（stdio 工具挂载）、**`KSFS开发.md`**（事实源）、**`设定导入Skill开发.md`**（P0 流水线细节）、**`API-V0.2.md`**（HTTP 字段表，待 T3 扩展 `skill_id`）。  
> **讨论定案日期**：2026-05-16

---

## 1. 在整体架构中的位置

Logos 纵向可分为两层（见 **`../ARCHITECTURE.md`**）：

| 层 | 内容 | 典型路径 / 模块 |
|----|------|-----------------|
| **下层：可实现的专业化能力** | 检索、LLM、进程内工具、MCP 工具、S&G 沙箱、CB 拼装引擎、ReAct 壳、KSFS/HDL、Obs、配置 | `src/logos/`、`skills/*/server.py`、`resources/prompts/` |
| **上层：产品化与任务化** | 技能面板、任务向导、产品 Skill manifest、持久化档位策略、档 B 任务生命周期、窄窗 GUI | `src/gui/`、`任务与Skill驱动GUI定案.md`、本文 |

**本文与第五阶段 GUI 大改**均属**上层建筑**：在**同一套**下层能力之上，规定用户如何**选能力、边界输入、 Scoped 工具、结束任务**，而不是重写 Retrieval 或 MCP 协议。

---

## 2. 两种「Skill」（禁止混称）

| 名称 | 英文标识 | 职责 | 实现形态 |
|------|----------|------|----------|
| **产品 Skill** | Product Skill | 用户/面板/任务驱动；单一职责；Prompt 策略；持久化档位；工具白名单 | 宿主 **manifest** + CB 模板键 + `POST /chat` 的 `skill_id` |
| **工具 Skill** | Tool Provider | 向注册表提供**可调用工具**（及可选 MCP 元数据） | **`skills/<包>/server.py`**（MCP）或 **`logos.tools`**（进程内） |

**定案**：

- **不是**每个产品 Skill 对应一个 MCP Server。  
- **MCP** 主承载**工具**；KSFS 与 CB 核心片段由**宿主被动读取**（**`MCP开发.md` §1**）。  
- 设定导入等 P0 能力 = **产品 Skill + 进程内工具 + 专用流水线**，而非「巨型 MCP」。

---

## 3. Prompt 三层（开发时 vs 使用时）

| 层 | 名称 | 时机 | 读者 | 典型载体 |
|----|------|------|------|----------|
| **L1** | **Prompt 设计模板（Blueprint）** | **开发**产品 Skill 时 | Skill 作者、评审者 | `skills/<skill_id>/DESIGN.md` 或 `resources/prompts/skills/<skill_id>/blueprint.md` |
| **L2** | **Prompt 运行时模板（Runtime Template）** | **执行**任务时，由 CB 拼装 | CB / Shell（非终端用户） | `resources/prompts/` 下片段键（partials + `prompt_runtime_key`） |
| **L3** | **Prompt 实例（Rendered Messages）** | 单次请求 | LLM | `messages[]`；开发者 **Prompt 回显**检视此层 |

**关系**：

```text
Blueprint  →  约束作者编写 L2 片段
L2 + task_input + history + operating_mode  →  CB.render  →  L3
```

**禁止**：把整段 L3 硬编码进 MCP；禁止用 MCP `prompts/get` 替代 KSFS 主读路径（除非对外 MCP Client 生态单独开扩展口）。

---

## 4. Agent 范式（PR）与持久化档位（二维）

> **范式权威**：**`范式路由与PR定案.md`**。产品 Skill 在 manifest **预先指定 `paradigm`**；**PR** 确认并交给 **Shell** 调度（远期可在 `paradigm_auto` 时推断）。

| 范式 `paradigm` | 说明 | JSON-only ReAct 协议 |
|-----------------|------|---------------------|
| **`dialogue`** | 对话/自由文本；`json_mode=false` | **否** |
| **`react`** | 现行 ReAct 工具循环 | **是** |
| **`plan`** | 先计划、再分步执行（雏形） | 仅计划步可选结构化 JSON |
| **`pipeline`** | 确定性流水线；不走 ReAct 循环 | 分步自定（如 entity schema） |

**Prompt 模板族** = **`paradigm` × `persistence_tier`** + `skills/<skill_id>/` 片段，见范式文档 §6。

---

## 4bis. 按「持久化依赖程度」分类（产品 Skill）

分类用于 **Blueprint 必填章节**与 **manifest 默认值**；与 **§4 范式** 正交，**不**复制多套 Shell 引擎实现。

| 档位 | 名称 | 持久化边界 | 典型 Skill | Blueprint 强调 |
|------|------|------------|------------|----------------|
| **P0** | **持久化型** | **必须**落盘：大文件、`workspace/` 草稿 → 人审 → **KSFS 晋升**（档 C）；档 B 只存任务元数据与摘要 | 设定导入、大纲助手 | 输出路径、schema、禁止静默覆盖 KSFS、人审闸门 |
| **P1** | **轻持久化型** | **可能**写 **`workspace/`**，体量有限；**不**默认晋升 KSFS；档 B 可存摘要 | 灵感记录、短草稿整理 | 是否写入、路径沙箱、可选「仅内存结果」 |
| **P2** | **纯对话型** | 在 **`messages[]`** 内完成即可；档 B 存任务与对话缓存 | 语病检查、逻辑漏洞、检索某设定、`chat_inspire` | 输入/输出格式、多轮策略、工具极少 |

**与 DECISIONS 三档存储的映射**：

| 档位 | KSFS（档 C） | workspace | 档 B 任务 JSON |
|------|--------------|-----------|----------------|
| P0 | 晋升目标 | 草稿必经 | 元数据 + 指针/摘要 |
| P1 | 一般不写 | 主要写入区 | 可存摘要 |
| P2 | 只读检索（若需） | 可选 | 完整 messages |

---

## 5. 各档 Blueprint 目录结构（开发 Skill 时）

### 5.1 通用节（所有档位）

- 技能目的与**非目标**（避免 scope creep）  
- `skill_id`、面板文案  
- `persistence_tier`、`paradigm`（见 **`范式路由与PR定案.md`**）、`allowed_tools` 草案  
- 输入 schema（向导第二步）  
- 返回格式 / 错误语义  

### 5.2 P0 追加节

- 落盘路径与命名约定  
- JSON Schema / 渲染规格引用（**`entity_template`**）  
- 人审与晋升流程（**`KSFS开发.md` §7**）  
- 与已落户实体冲突时的行为  

### 5.3 P1 追加节

- `workspace` 相对路径规则  
- 单次任务大小上限（字符/文件数）  
- 是否允许覆盖已有草稿  

### 5.4 P2 追加节

- 单轮 vs 多轮（`multi_turn` 仅在此档默认开放）  
- 是否允许 `retrieve` / `read_ksfs`  
- 启发语气 vs 严格执行（如 `chat_inspire`）  

---

## 6. 产品 Skill manifest（逻辑字段，扩展定案）

在 **`任务与Skill驱动GUI定案.md` §5** 基础上增补：

| 字段 | 必填 | 说明 |
|------|------|------|
| `skill_id` | 是 | 稳定标识 |
| `persistence_tier` | 是 | `p0` \| `p1` \| `p2` |
| `prompt_runtime_key` | 是 | CB 模板组键 |
| `allowed_tools` | 是 | 可为 `[]` |
| `paradigm` | 是 | `dialogue` \| `react` \| `plan` \| `pipeline`（PR 路由，见范式文档） |
| `turn_policy` | dialogue/plan 常用 | `single` \| `multi` |
| `input_schema` | 是 | 任务向导第二步 |
| `description` | 否 | 技能面板**一句话**摘要 |
| `ui_instructions` | 否 | GUI **「技能说明」**正文（`bootstrap.skills[]`；与 `resources/prompts/skills/*.md` 分工：后者给模型） |
| `blueprint_path` | 否 | L1 文档路径 |
| `allowed_skill_calls` | 否 | 互调须限深度，防循环 |
| `workspace_writes` | P0/P1 | 是否允许写 workspace |
| `ksfs_promotion` | P0 | 是否走人审晋升 |

**T1 竖切片**可用最小 manifest（P2 示例）：

```yaml
skill_id: lint_zh
persistence_tier: p2
paradigm: dialogue
turn_policy: single
allowed_tools: []
prompt_runtime_key: skills/lint_zh
```

---

## 7. 与 Agent / MCP 理念的对齐（摘要）

| 原则 | Logos 做法 |
|------|------------|
| 工具最小权限 | 每产品 Skill 仅 `allowed_tools` |
| 有界任务 | 用户先选 Skill，再三步向导 |
| 反对万能 Agent | 默认首页为技能面板，非全工具 Chat |
| MCP 角色 | 工具提供者；非任务与 CB 主载体 |
| Skill 互调 | 可选；须限深度（实现期护栏） |

---

## 8. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-05-16 | 初版：上下层定位、产品 Skill vs 工具 Skill、Prompt L1～L3、P0/P1/P2、Blueprint 结构、manifest 扩展。 |
| 2026-05-16 | §4：范式×持久化二维；`paradigm` 对齐 PR（dialogue/react/plan/pipeline）；互链 `范式路由与PR定案.md`。 |
| 2026-05-21 | §6：增补 `description` / `ui_instructions`；GUI 技能说明与 manifest 绑定（**GUI开发文档.md** §11.6）。 |
