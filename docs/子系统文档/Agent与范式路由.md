# Agent 与范式路由

## 决策层组件

| 组件 | 缩写 | 作用 |
|------|------|------|
| **Shell** | — | 任务调度入口；通过端口调用检索、模型、工作区，不直接绑定具体驱动 |
| **Context Builder** | CB | 按范式与持久化档位选择 Prompt 模板，拼装消息与上下文预算 |
| **Paradigm Router** | PR | 根据 Skill manifest 的 `paradigm` 选择执行器 |

模板资产默认位于 `resources/prompts/`（含 `paradigms/`、`skills/` 等子目录）。

## 四种范式

每个产品 Skill 在 `skills/manifests/<skill_id>.yaml` 中**预先声明** `paradigm`：

| 范式 | 说明 | 典型场景 |
|------|------|----------|
| `dialogue` | 自由文本多轮，非 ReAct JSON 协议 | 聊天启发 |
| `react` | 每轮结构化 JSON（thought / action / final_answer） | 需工具调用的检查、检索 |
| `plan` | 先产出计划再分步执行（演进中） | 大纲类任务 |
| `pipeline` | 确定性流水线，由 `PipelineRunner` 驱动 | 设定导入等无 ReAct 环 |

PR **不**默认在运行时「智能猜范式」；Skill 作者在 manifest 中定好边界，与任务驱动产品一致。开发者可在开启调试工具时用 `paradigm_override` 试验（见 API 文档）。

## 一次执行的链路

```text
skill_id → 读取 manifest → PR 选定范式 → Shell 调用对执行器
         → CB 组装 messages → S&G 裁剪工具白名单 → LLM / 工具循环 / Pipeline 步骤
```

`pipeline` 范式会发出步骤级 SSE 事件（如 `pipeline_step`），GUI 可展示任务轨迹。

## 与基础设施的边界

- **检索（Retrieval）**、**模型（MS）** 属于基础设施层，**不是** Skill。
- Skill 通过 manifest 声明是否、以及如何调用检索等能力。

## 相关文档

- [任务与 Skill 界面](任务与Skill界面.md)
- [Skills 与 MCP 扩展](Skills与MCP扩展.md)
- [HTTP API 概览](HTTP-API概览.md)
