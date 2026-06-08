---
name: skill-writer
description: Interactive skill authoring — multi-turn conversation to draft, iterate, and finalize a skill before writing to disk. Use when you need to discuss and refine.
---

# skill-writer — 交互式 Skill 撰写

这是一个**对话驱动**的工作流：不是一次性用 `install_skill` 写死，而是通过多轮讨论，逐步迭代，最后在双方确认后才写入文件。

## 核心原则

1. **先讨论，后落盘** — 在调用 `install_skill` 之前至少经过一轮草案→反馈的循环。
2. **渐进式细化** — 每一轮只聚焦一两个可改进的方面，不要一次性塞给用户所有细节。
3. **用户说「可以了」才写** — 在用户明确确认之前，绝不调用 `install_skill`。

## 工作流

### Phase 1 — 需求理解

先弄清楚用户想写什么样的 skill：

- **目标**：这个 skill 解决什么问题？
- **触发条件**：什么场景下应该调用它？
- **行为**：它应该做什么？有什么特殊情况？
- **与现有 skill 的关系**：是否与已有 skill 重叠？是否需要引用它们？

向用户复述你的理解，并确认是否正确。

### Phase 2 — 初稿

基于需求理解，写一份完整的 markdown 草案（**在头脑中或临时笔记中构建，不写入文件**），包含标准段落：

- 名称与描述（供 future agent 索引使用的一两句话）
- 使用时机（When to use）
- 具体行为（逐条步骤，清晰无歧义）
- 边界情况与错误处理
- 可选：示例

然后**以代码块形式展示给用户**，问：
> "这是初稿，你看看哪些地方需要调整？"

### Phase 3 — 迭代修改

根据用户的反馈，逐一调整。每一轮：

1. 指出你做了什么修改（"根据你的反馈，我调整了 X 和 Y"）
2. 展示更新后的完整版本（再次在对话中展示，不要写文件）
3. 询问是否还需要调整

可以循环多轮，直到用户说 "可以了" 或类似确认。

### Phase 4 — 定稿写入

当用户确认满意后：

1. 调用 `install_skill` 写入文件（使用 `scope: "project"`）
2. 告知用户已写入，并简要总结 skill 的位置和内容

## 注意

- **绝对不要**在 Phase 1-3 期间调用 `install_skill`。
- 如果用户对现有 skill 提出修改意见，同样遵循此流程——先讨论再修改。
- 如果草案较长（超过 2500 词），使用 chunked-import 技能分块处理。
- 写入后提醒用户：该 skill 会在下一次会话时出现在索引中。
