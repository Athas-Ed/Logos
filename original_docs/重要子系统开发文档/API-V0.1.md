# HTTP API 契约 — V0.1

> 由 **I&I（Stream 5）** 实现；变更请通知 **GUI（Stream 6）** 与架构维护者。展示与日志见 [`../SPEC-DISPLAY-AND-LOGGING-V0.1.md`](../SPEC-DISPLAY-AND-LOGGING-V0.1.md)。

---

## `GET /api/v1/health`

- **200**：`{"status": "ok"}`

---

## `GET /api/v1/bootstrap`

- **200**：`default_presentation`（`work`|`developer`）、`log_profile`（`minimal`|`standard`|`verbose`|`audit`）、`operating_mode`（字符串）。

---

## `POST /api/v1/chat`（SSE）

### 请求 Body

- `messages`、`operating_mode`（可选，默认 `author`）
- `presentation`（可选）：`work`|`developer`；省略则用配置 `ui.default_presentation`。

### SSE 事件（按 `presentation` 只发对应档位）

- 工作：`reasoning_summary`、`citations_partial`、`tool_trace_summary`
- 开发者：`reasoning_full`、`citations_full`、`tool_trace_full`
- 共用：`delta`、`done`、`error`

契约校验：`src/logos/harness/ii_layer/sse_contract.py`；单测：`tests/test_sse_chat_contract.py`。
