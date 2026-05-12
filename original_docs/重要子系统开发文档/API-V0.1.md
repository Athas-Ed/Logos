# HTTP API 契约 — V0.1

> 由 **I&I（Stream 5）** 实现；变更请通知 **GUI（Stream 6）** 与架构维护者。历史范围见 [`../已完成文档/SPEC-V0.1.md`](../已完成文档/SPEC-V0.1.md)（归档）。

---

## `GET /api/v1/health`

- **200**：`{"status": "ok"}`

---

## `POST /api/v1/chat`（**SSE**）

V0.1 **强制**采用 **Server-Sent Events** 流式返回，便于逐 token 渲染与后续扩展。

### 请求

- **Header**：`Accept: text/event-stream`（推荐）；`Content-Type: application/json`
- **Body（JSON）**：

```json
{
  "messages": [{"role": "user", "content": "……"}],
  "operating_mode": "author"
}
```

### 响应

- **Header**：`Content-Type: text/event-stream`；按需 `Cache-Control: no-cache`，保持连接。

### 事件约定（`event:` + `data:` 一行 JSON）

| `event` 名 | 最小 `data` JSON（字段名锁定） | 说明 |
|------------|-------------------------------|------|
| `reasoning_delta` | `{"text": "..."}` | **ReAct 流式中间态**：助手在 JSON 模式下按 token/片段输出的增量（多为未完成的 ReAct JSON）。可 **0 次或多次**；GUI 与 `src/gui/src/api/sseChat.ts` 一致解析。开启 **Prompt 回显**（`developer.prompt_echo`，见 `api_v1`）时服务端可能 **不发送** 本事件，直接输出最终正文 `delta`。 |
| `citations` | `{"items": [{"path":"…","snippet":"…","score":0.0}]}` | 可选 **0 或 1 次**；在最终 `delta` 之前发送（若有引用）。`items[]` 每项至少含 `path`、`snippet`、`score`（与 `ports.retrieval.Citation` 对齐）。 |
| `delta` | `{"text": "..."}` | **最终答复正文**增量片段（成功路径下为 `final_answer` 的分块）；可多次发送。 |
| `done` | `{}` 或 `{"usage": {...}}` | 流正常结束；`usage` 等扩展字段可选。 |
| `error` | `{"code":"…","message":"…"}` | 不可恢复或需中断时发送，随后应结束流。常见 `code`：`empty_message`（无有效用户正文）、`internal`（Agent 未正常结束）、或异常类名。 |

**典型顺序（成功路径）**：`reasoning_delta`（0..n）→ `citations`（0..1）→ `delta`（1..n）→ `done`（1）。若首包即 `error`，则不应再发 `done`。

**机器可读契约**：事件名集合与最小载荷校验见 `src/logos/harness/ii_layer/sse_contract.py`；单测 `tests/test_sse_chat_contract.py`。

**说明**：上表字段名为 V0.1 **锁定**约定；前端与后端共用同一套字符串，避免再搞一套别名（即此前文档中所谓「响应字段微调」所指：已无必要再模糊待定）。

### 非流式

V0.1 **不提供**同路径 JSON 非流式降级；若调试需要，可另增 `POST /api/v1/chat/debug`（可选，SPEC 未强制）。

---

## 演进说明（V0.1 之后）

- **主对话流**：保持 **HTTP + SSE** 为默认，便于代理兼容与单向 token 流。
- **WebSocket（或其它全双工通道）**：可与 SSE **并行**引入（例如新路径 `/ws/v1/...`），用于**取消生成、客户端信令、多类事件复用连接**等；**不**视为对 V0.1 SSE 字段的替代，新增契约须单独文档化并同步 GUI。
- **Agent 范式**（ReAct；未来 Plan、Reflection）：编排发生在服务端；传输选型主要影响**前端订阅的事件模型**，不阻塞范式扩展。详见 `ARCHITECTURE.md` §2.5、`DECISIONS.md` §8。
