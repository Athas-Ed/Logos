# chat_inspire — Prompt Blueprint（L1 占位）

> **状态**：F5-07 已接入面板 → `/chat/:id` 多轮 UI；L2 运行时键见 manifest `prompt_runtime_key: skills/chat_inspire`。

## 技能目的

以启发式、非指令性的语气协助游戏文案创作；支持**多轮**对话（`turn_policy: multi`）。

## 非目标

- 非默认首页「万能 Chat」
- 默认不挂载检索/写盘工具（`allowed_tools: []`）

## manifest 摘要

| 字段 | 值 |
|------|-----|
| `skill_id` | `chat_inspire` |
| `persistence_tier` | `p2` |
| `paradigm` | `dialogue` |
| `turn_policy` | `multi` |
| `allowed_tools` | `[]` |

## 输入

`task_input.text`：当前轮用户消息。

## 语气

开放、追问式；避免一次性输出过长成品稿。
