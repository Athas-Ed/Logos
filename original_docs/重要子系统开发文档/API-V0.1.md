# HTTP API 契约 — V0.1

> 由 **I&I（Stream 5）** 实现；变更请通知 **GUI（Stream 6）** 与 `SPEC-V0.1.md`。

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

| `event` 名 | `data` JSON 字段 | 说明 |
|------------|-------------------|------|
| `delta` | `{"text": "..."}` | 助手正文增量片段；可多次发送。 |
| `citations` | `{"items": [{"path":"…","snippet":"…","score":0.0}]}` | 可选；检索引用批次（可在首包或末包前发送）。 |
| `done` | `{}` 或 `{"usage": {...}}` | 流结束；可携带粗粒度 usage（Token 等），字段可选。 |
| `error` | `{"code":"…","message":"…"}` | 不可恢复或需中断时发送，随后应结束流。 |

**说明**：上表字段名为 V0.1 **锁定**约定；前端与后端共用同一套字符串，避免再搞一套别名（即此前文档中所谓「响应字段微调」所指：已无必要再模糊待定）。

### 非流式

V0.1 **不提供**同路径 JSON 非流式降级；若调试需要，可另增 `POST /api/v1/chat/debug`（可选，SPEC 未强制）。
