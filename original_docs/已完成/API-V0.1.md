# HTTP API 契约 — V0.1（归档）

> **状态**：**归档**，仅供与旧提交、`已完成文档/SPEC-V0.1.md` 对照。  
> **现行权威**：**[`API-V0.2.md`](API-V0.2.md)**（路径仍为 `/api/v1/*`，含 SSE 增量与开发者端点）。

---

## 与 V0.2 的差异摘要

| 项目 | V0.1（本文档成稿时） | V0.2（现行） |
|------|----------------------|--------------|
| SSE 事件 | `delta` / `citations` / `done` / `error` | 增加 **`reasoning_delta`**；事件顺序见 V0.2 文档第 3.5 节 |
| 开发者 HTTP | 未描述 | **`GET/PUT /api/v1/developer/*`** 见 V0.2 文档第 4 节 |
| `messages` 拆分 | 未写清 | **system 补充 + 历史 + 末条用户** 见 V0.2 文档第 3.2 节 |
| `operating_mode` | 仅示例 | **`author` / `screenwriter`** 语义见 V0.2 文档第 3.1 节 |

---

## 附录：V0.1 当时锁定的 SSE 子集（原文）

以下表格为 **V0.1 文档历史版本** 中对 `POST /api/v1/chat` 的约定；**不含** `reasoning_delta`，**不等价**于当前后端行为。

### `GET /api/v1/health`

- **200**：`{"status": "ok"}`

### `POST /api/v1/chat`（SSE）

- **Header**：`Accept: text/event-stream`（推荐）；`Content-Type: application/json`
- **Body（JSON）** 示例：

```json
{
  "messages": [{"role": "user", "content": "……"}],
  "operating_mode": "author"
}
```

### 事件约定（历史）

| `event` 名 | `data` JSON 字段 | 说明 |
|------------|-------------------|------|
| `delta` | `{"text": "..."}` | 助手正文增量片段；可多次发送。 |
| `citations` | `{"items": [{"path":"…","snippet":"…","score":0.0}]}` | 可选；检索引用批次。 |
| `done` | `{}` 或 `{"usage": {...}}` | 流结束；usage 可选。 |
| `error` | `{"code":"…","message":"…"}` | 错误并结束流。 |

V0.1 **不提供**同路径 JSON 非流式降级。
