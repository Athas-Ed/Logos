# HTTP API 概览

Logos 对外以 **`/api/v1`** 为前缀（实现于 `src/logos/platform/ii_layer/api_v1.py`）。本地由**开发用组合根后端**（`scripts/run_dev_backend.py`）提供，默认 `http://127.0.0.1:8000`。

> 本文为**对外摘要**。字段增删以代码与 `tests/test_stream5_api.py` 为准；客户端应**忽略未知 SSE 事件名**。

## 通用约定

- JSON 请求/响应为 UTF-8。
- 主聊天路径使用 **Server-Sent Events**（`Accept: text/event-stream`），`data:` 为单行 JSON。
- 展示档位（work / developer）影响 reasoning、citations、tool_trace 等事件是否下发。

## 主要端点

### `GET /api/v1/health`

返回 `{"status": "ok"}`，用于存活探测。

### `GET /api/v1/bootstrap`

GUI 首屏数据，字段包括（节选）：

| 字段 | 说明 |
|------|------|
| `default_presentation` | **Pd** 展示档位：`work` \| `developer`（`work` ≈ WM） |
| `log_profile` | 日志详细度 |
| `llm_mode` | `stub` \| `remote` |
| `skills` | Skill 列表（面板与会话页元数据；含 `paradigm`） |
| `conversations_cache_root` | 档 B JSON 目录绝对路径 |
| `ui` | 含 `SSE_maxNum`、`cache_warn_bytes`、`max_history_full_text`、`react_max_steps`、`react_max_qa_steps` 等 |

### `POST /api/v1/chat`（SSE）

主执行路径。请求体要点：

| 字段 | 说明 |
|------|------|
| `skill_id` | 产品 Skill 标识（推荐必填） |
| `task_input` | 任务向导输入（对象，依 Skill 而定） |
| `messages` | 多轮消息数组；连续问答 Skill 可含历史 user/assistant |
| `operating_mode` | 如 `author` / `director` |

响应为 SSE 流，常见事件包括（名称随展示档位变化）：

- 助手正文增量（`delta`）
- `reasoning_summary` / `reasoning_full`（开发者档）
- `tool_trace_*`、`citations_*`
- Pipeline 步骤：`pipeline_step` 等
- 结束：`done`（见下）

**`done` 载荷（ReAct 节选）**

| 字段 | 说明 |
|------|------|
| `react_hit_step_limit` | 可选；为 `true` 表示本轮 ReAct 因步数触顶收束（正文由 synthesis，触顶说明由 GUI 展示） |

已移除：`react_can_continue`、`react_resume_messages`、`react_step_wave` 及请求体中的续跑字段。

**步数配置**：`retrieve_qa` 使用 `agent.react.max_QA_steps`（按**当前 user 消息**计数）；其余 `react` Skill 使用 `agent.react.max_steps`。详见 [配置说明](../配置说明.md)。

未知 `skill_id` 返回 **400** JSON（不开启 SSE）。

### `POST /api/v1/setting-entry/promote`

将 `workspace/pending_review/setting_entry/` 下草稿晋升至 KSFS。

- Body：`draft_relpaths`（可选，相对 `setting_entry` 根的路径列表）
- Response：`ok`、`applied`、`skipped`、`notes`

语义与 `python -m logos.tools.promote_draft --apply` 一致。

> 草稿类端点（`drafts/*`、`outlines/save`）的路径统一经沙箱校验：相对路径必须落在
> `pending_review/`（outline 为 `outlines/`）内，绝对路径与 `..` 逃逸一律拒绝。
> 拒绝形态见 `original_docs/重要子系统开发文档/API-V0.2.md` §2.3。

## 开发者端点

在 `developer.show_dev_tools_ui` 等条件满足时，可能提供 Prompt 回显、诊断类只读路由；**非**公开稳定契约，集成方请勿依赖。

## 与 GUI 的对应

| GUI 行为 | API |
|----------|-----|
| 首屏 Skill 列表 | bootstrap |
| 执行任务 | `POST /chat` SSE |
| 设定晋升 | `POST /setting-entry/promote` |
| 健康检查 | health |

## 相关文档

- [快速开始](../快速开始.md)
- [KSFS 与叙事知识库](KSFS与叙事知识库.md)
- [任务与 Skill 界面](任务与Skill界面.md)
