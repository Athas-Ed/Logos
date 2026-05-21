# lint_zh — Prompt Blueprint（L1 占位）

> **状态**：F5-01 占位；L2 运行时键见 manifest `prompt_runtime_key: skills/lint_zh`。

## 技能目的

对用户输入的中文段落做语病、搭配与表达问题提示，**不**改写全文、**不**调用工具。

## 非目标

- 不做设定导入或 KSFS 写入（非 P0）
- 不走 ReAct JSON-only 协议（`paradigm: dialogue`）

## manifest 摘要

| 字段 | 值 |
|------|-----|
| `skill_id` | `lint_zh` |
| `persistence_tier` | `p2` |
| `paradigm` | `dialogue` |
| `turn_policy` | `single` |
| `allowed_tools` | `[]` |

## 输入

`task_input.text`：待检查文本（见 `skills/manifests/lint_zh.yaml` → `input_schema`）。

## 返回格式

自然语言列表或短段说明；错误时说明无法处理的原因。
