# Agent 与范式路由

## Agent 决策层组件

| 组件 | 缩写 | 作用 |
|------|------|------|
| **Agent 调度器** | Shell（`shell.py`） | 任务执行入口；通过**端口**调用检索、模型、工作区，不直接绑定具体驱动 |
| **上下文构建器** | CB | 按**执行范式**与持久化档位选择 Prompt 模板，拼装消息与上下文预算 |
| **范式路由器** | PR | 根据产品 Skill manifest 的 `paradigm` 选择执行器 |

模板资产默认位于 `resources/prompts/`（含 `paradigms/`、`skills/` 等子目录）。

## 执行范式（`paradigm`）

每个产品 Skill 在 `skills/manifests/<skill_id>.yaml` 中**预先声明**执行范式：

| 执行范式 | `paradigm` 取值 | 说明 | 典型场景 |
|----------|-----------------|------|----------|
| 对话 | `dialogue` | 自由文本多轮，非 ReAct JSON | 聊天启发 |
| ReAct | `react` | 每轮结构化 JSON + 工具 | 语病检查、检索问答 |
| Plan | `plan` | 先计划再分步（演进中） | 大纲类 |
| **HITL Plan-and-Execute** | `pipeline` | 人在回路的计划—执行流水线；**非** CI Pipeline | 设定导入 |

PR **不**默认在运行时「智能猜范式」；Skill 作者在 manifest 中定好边界。开发者可在开启调试工具时用 `paradigm_override` 试验（见 API 文档）。

### ReAct 步数上限

| 配置键 | 适用 Skill | 计数范围 |
|--------|------------|----------|
| `agent.react.max_steps` | 所有 `paradigm: react`（除下表专用项外） | 单次执行内 ReAct 迭代次数 |
| `agent.react.max_QA_steps` | `retrieve_qa` | **每个 user 问题**一轮 ReAct 的迭代次数 |

触顶时循环停止，基于已有 tool observation 做收束作答；**不支持**同会话内步数续跑（无 `resume_messages` / 多 wave）。产品交互见 [任务与 Skill 界面](任务与Skill界面.md)。

## 一次执行的链路

```text
skill_id → 读取 manifest → PR 选定执行范式 → Agent 调度器调用执行器
         → CB 组装 messages → S&G 裁剪工具白名单 → LLM / 工具循环 / Pipeline 步骤
```

`pipeline`（HITL Plan-and-Execute）会发出步骤级 SSE 事件（如 `pipeline_step`），GUI 可展示轨迹。

## 与基础设施的边界

- **检索（Retrieval）**、**模型（MS）** 属于**基础设施层**，**不是**产品 Skill。
- Skill 通过 manifest 声明是否、以及如何调用检索等能力。

## 相关文档

- [术语表 · 执行范式](../术语表.md#2-agent-组件与执行范式)
- [任务与 Skill 界面](任务与Skill界面.md)
- [Skills 与 MCP 扩展](Skills与MCP扩展.md)
- [HTTP API 概览](HTTP-API概览.md)
