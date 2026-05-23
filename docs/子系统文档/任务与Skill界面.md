# 任务与 Skill 界面

## 产品交互模型

Logos 的 GUI 以 **任务（Task）** 为主轴，而不是默认打开空白聊天框：

```text
选择 Skill → 输入本任务内容 → 执行（SSE 流式）→ 结束 / 归档
```

- **单任务模式**（主路径）：语病检查、设定导入、检索问答等，各对应独立 Skill。
- **长对话模式**：如「聊天启发」，仍是**一个 Skill 实例 = 一个任务**，工具暴露刻意收窄，**不是**首页默认的万能 Agent。

首页为 **技能面板**（`/`），展示 `GET /api/v1/bootstrap` 返回的 `skills` 列表（名称、简述、说明正文、范式类型）。

## 路由（概要）

| 路由 | 用途 |
|------|------|
| `/` | 技能面板 |
| `/task/:id` | 单任务向导与执行 |
| `/chat/:id` | 长对话类 Skill（如 `chat_inspire`） |
| `/settings` | 设置与诊断 |
| `/cache` | 已归档任务列表 |

顶栏 **标签** 表示进行中的任务槽；切换标签即切换任务上下文。

## Skill 清单从哪来

- 后端扫描 `skills/manifests/*.yaml`，经 bootstrap 下发给 GUI。
- 每项包含 `skill_id`、`display_name`、`description`、`ui_instructions`、`paradigm`、`persistence_tier` 等。
- 前端 `src/gui/src/skills/catalog.ts` 可在 manifest 缺失时作有限回退，**不应**硬编码替代 manifest 的业务规则。

## 与 KSFS 的关系

- 任务过程状态保存在**档 B** 本地 JSON（见 [会话与任务缓存](会话与任务缓存.md)）。
- 将内容**升格为作品 / 设定**应走专用 Skill 或 **KSFS 晋升 / 导入** 路径，**不**与会话 JSON 混用语义。

## 渐进式工具披露

每个 Skill 的 manifest 声明允许的工具子集；执行时仅这些工具（含绑定的 MCP）进入模型可见列表，避免「全仓库工具一次暴露」。

## 相关文档

- [Agent 与范式路由](Agent与范式路由.md)
- [会话与任务缓存](会话与任务缓存.md)
- [GUI 与桌面壳](GUI与桌面壳.md)
