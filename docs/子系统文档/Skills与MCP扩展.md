# Skills 与 MCP 扩展

## Skill 是什么

**Skill** 是 Logos 中可注册的产品能力单元，由 manifest 描述：

- 展示名称、说明、UI 指引
- 允许的**进程内工具**与 **MCP 工具** 子集
- `paradigm`（对话 / ReAct / Plan / Pipeline，代码值 `pipeline`）
- 持久化档位 `persistence_tier`（p0 / p1 / p2）
- 可选 `input_schema` 约束任务输入

manifest 位于 `skills/manifests/<skill_id>.yaml`，与 `skills/<name>/` 下的设计说明、MCP 入口脚本并列。

## 内置 Skill 一览

`skills/manifests/` 下当前包含以下 10 个产品 Skill（以实际文件为准）：

| skill_id | 范式 | 用途（概要） |
|----------|------|----------------|
| `chat_inspire` | react | 长对话启发（`turn_policy: multi`） |
| `draft_review` | react | 审核晋升：列出待审草稿，预览后晋升至 KSFS（`custom_page: review`） |
| `import_setting` | pipeline | 结构化设定导入（确定性阶段表，`pipeline_profile: your_profile_v1`） |
| `lint_zh` | dialogue | 中文语病检查（纯对话，无工具） |
| `outline_plan` | react | 大纲规划：检索已有设定后生成结构化分步大纲（原 plan 范式已改 react） |
| `retrieve_qa` | react | 检索问答（三路融合检索 + read_ksfs 原文核实） |
| `RQA` | react | `retrieve_qa` 的本地实验变体（额外允许 MCP 工具 `query_weather`；无专属 prompt） |
| `setting_check` | dialogue | 设定一致性检查：检索相关 KSFS 条目并判定冲突（独立 LLM 服务，非 ReAct） |
| `setting_write` | react | 设定撰写：基于 KSFS 上下文起草新条目 |
| `weather` | react | 天气查询：调用 MCP 工具 `query_weather`（需注册 amap-weather-mcp） |

> **MCP 依赖提示**：`weather` 与 `RQA` 的 `allowed_tools` 含 MCP 工具 `query_weather`，
> 仅当 `config/local.yaml → skills.mcp_servers` 注册了 `amap-weather-mcp`（`AMAP_WEB_KEY`）时该工具才可用；
> 未注册时这两个 Skill 仍出现在技能面板，但声明的工具不可用（Agent 调用会收到 "unknown tool" 类观测）。
> `RQA` 为实验副本（`resources/prompts/skills/` 下无对应 `RQA.md`，复用通用 ReAct prompt）。

## MCP 集成

外部能力以 **本地 MCP Server（stdio）** 为主：

1. 在 `config/local.yaml` 的 `skills.mcp_servers` 注册 `id`、`entrypoint`、`env`。
2. 支撑层 **S&G** 负责进程启动、沙箱与回收。
3. 仅当某 Skill manifest **显式允许** 时，对应 MCP 工具才会进入该次任务的工具列表。

示例目录：`skills/example-stdio-mcp/`、`skills/amap-weather-mcp/`。

## 添加新 Skill（概要）

1. 编写 `skills/manifests/my_skill.yaml`。
2. 在 `resources/prompts/skills/` 增加 CB 用 Prompt（若需要）。
3. 实现 MCP 或进程内工具，并在 manifest 的 `allowed_tools` 中列出。
4. 重启后端，确认 bootstrap 的 `skills` 数组含新项。
5. 在 GUI 技能面板验证端到端流程。

## 相关文档

- [任务与 Skill 界面](任务与Skill界面.md)
- [Agent 与范式路由](Agent与范式路由.md)
- [配置说明](../配置说明.md)
