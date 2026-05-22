## Skill：大纲规划（outline_plan）

根据用户给出的主题或写作目标，产出 **Phase A 计划**（仅规划，不执行后续步骤）。

**输出格式（二选一，优先 JSON）**：

```json
{
  "title": "计划标题",
  "steps": ["步骤一", "步骤二", "步骤三"]
}
```

或使用 Markdown 有序列表，每步一行，至少 3 步。

要求：步骤具体、可执行、顺序合理；不要调用工具；不要输出 ReAct 的 `thought` / `action` 字段。

用户输入在 `task_input.text` 或当前用户消息中。
