## Skill：审核晋升（draft_review）

你的任务是帮用户审查 workspace 中的草稿，并在用户确认后晋升至 KSFS。

### 默认范围

- 优先审查 `pending_review/` 子目录下的草稿（用户手动放入、或从其他 Skill 汇总至此）。
- 用户也可指定其他路径（如 `writing_entry/`、`setting_entry/`）。

### 步骤

1. **列出候选**：用 `list_drafts(path="pending_review/")` 展示待审核文件（路径、大小、修改时间）。
2. **预览内容**：对用户感兴趣的草稿，用 `read_draft` 读取内容供用户审阅。
3. **用户确认**：只有用户明确说「晋升」「确认」「通过」等指令时，才调用 `promote_draft`。
4. **晋升执行**：调用 `promote_draft(items=[...])` 后向用户汇报晋升结果。

### 规则

- **不要擅自晋升**：promote_draft 是写 KSFS 的操作，必须在用户明确同意后执行。
- **展示要清晰**：列出草稿时附带路径和修改时间，方便用户判断哪些需要审查。
- **处理冲突**：如果 `promote_draft` 返回 `"ok": false`，向用户解释错误原因（如目标已存在、mtime 不一致）。
- **晋升后建议**：建议用户验证 KSFS 中的结果（用 `read_ksfs` 或直接查看文件）。
