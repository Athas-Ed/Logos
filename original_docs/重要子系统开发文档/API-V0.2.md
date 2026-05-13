# HTTP API 契约 — V0.2

> **地位**：**现行权威**（2026-05-13 收口）。由 **I&I（Stream 5）** 在 `src/logos/harness/ii_layer/api_v1.py` 实现；变更请同步 **GUI（Stream 6）**、`tests/test_stream5_api.py` 与 `SPEC-V0.1.md` / 展示规格中涉及 HTTP 的段落。  
> **版本说明**：URL 仍为 **`/api/v1/*`**（未改为 `/api/v2`）；**文档版本 V0.2** 表示相对 **`API-V0.1.md`（归档）** 的契约增量。  
> **沿革**：V0.1 仅含 health + chat 的四种 SSE；V0.2 增补 **`reasoning_delta`**、**开发者只读/调试端点**，并固化 **请求体消息拆分** 与 **`operating_mode`** 语义。

---

## 1. 通用约定

- **Base URL**：由部署决定（本地开发常见 `http://127.0.0.1:8000`）。
- **JSON**：请求/响应体为 UTF-8 JSON；SSE 的 `data:` 行为 **单行 JSON**（见上文第 3 节）。
- **客户端健壮性**：应 **忽略未知 `event:` 名** 的帧，以便后端在不破版本 URL 的前提下扩展 SSE。
- **`GET /api/v1/bootstrap`**：已实现（见下文 §2.1）；返回默认展示档位与日志 profile，供 GUI 首屏使用。

---

## 2. `GET /api/v1/health`

- **200**：`{"status": "ok"}`

### 2.1 `GET /api/v1/bootstrap`

- **200**：JSON 对象，字段至少包含：
  - `default_presentation`：`"work"` \| `"developer"`（来自 `ui.default_presentation`）
  - `log_profile`：`"minimal"` \| `"standard"` \| `"verbose"` \| `"audit"`（来自 `obs.log_profile`）
  - `operating_mode`：字符串（与配置 `operating_mode` 一致）
- 与 `SPEC-DISPLAY-AND-LOGGING-V0.1.md` 正交：会话内切换展示档位 **不** 通过本接口写回配置。

---

## 3. `POST /api/v1/chat`（**SSE**，主路径）

V0.2 **强制**采用 **Server-Sent Events** 流式返回；**不提供**同路径 JSON 非流式降级（调试可加独立路由，非本契约范围）。

### 3.1 请求

- **Header**：`Accept: text/event-stream`（推荐）；`Content-Type: application/json`
- **Body（JSON）**：

```json
{
  "messages": [
    {"role": "system", "content": "可选：前端补充 system"},
    {"role": "user", "content": "……"},
    {"role": "assistant", "content": "……"}
  ],
  "operating_mode": "author"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `messages` | 数组 | 每项 `role` ∈ `system` \| `user` \| `assistant`，`content` 为字符串。 |
| `operating_mode` | 字符串 | 可选，默认 **`author`**。服务端按小写比较；内置 **`screenwriter`**（编剧）与 **`author`**（作者）两种提示后缀，其余值按 **author** 处理。 |
| `presentation` | 字符串 | 可选。`work` \| `developer`（及别名 `dev`）；省略则使用服务端 `ui.default_presentation`。影响 chat SSE 中推理与引用等事件的**档位**（摘要 vs 全文），见 §3.5。 |

### 3.2 消息拆分（与实现对齐）

后端在调用 Agent 前对 `messages` 做如下处理（GUI 拼装时应预期该语义）：

1. **前端 system 补充**：所有 `role: system` 且 `content` 去空白非空的条目，按出现顺序拼接，记为 `client_extra`（多条之间用双换行连接）。
2. **对话历史**：所有 `role: user` 与 `role: assistant` 条目转为内部 `ChatMessage` 列表；**最后一条**必须为当前轮用户输入；其之前的 `user`/`assistant` 为历史。
3. **若没有任何 `user`/`assistant` 条目**，或最后一条去空白后为空：流内发送 **`error`**（`code: empty_message`）并结束；HTTP 仍为 **200** + `text/event-stream`。

服务端将 `operating_mode` 对应的模式说明拼入 system 侧上下文；若存在 `client_extra`，再附加「来自前端的 system 补充」段落。

**MCP 工具提示**：若当前进程启用了 MCP 工具（非内置白名单工具名），服务端会在 system 补充中追加已启用工具名列表，供模型按需调用（与 `skills.mcp_servers` 配置一致）。

### 3.3 响应头

- `Content-Type: text/event-stream`
- `Cache-Control: no-cache`
- `Connection: keep-alive`
- `X-Accel-Buffering: no`

### 3.4 SSE 帧格式

每个事件：

```text
event: <事件名>
data: <单行 JSON>

```

（帧以空行 `\n\n` 结束；`data` 为单行 UTF-8 JSON。）

### 3.5 事件表（`event` + `data` 最小字段）

展示档位由请求体可选字段 `presentation`（及配置 `ui.default_presentation`）决定 **`work`**（面向作者、摘要化）与 **`developer`**（更完整上下文）两类行为；下列事件中 **推理**、**引用**、**工具轨迹** 的事件名随档位变化。

| `event` 名 | `data` JSON（最小字段） | 说明 |
|------------|-------------------------|------|
| `reasoning_summary` | `{"text": "..."}` | **`work`** 档：ReAct 流式推理的**滚动摘要**（截断预览，可多次）。 |
| `reasoning_full` | `{"text": "..."}` | **`developer`** 档：推理片段**全文**流式输出（可多次）。 |
| `tool_trace_summary` | `{"tool":"…","status":"ok"\|"error","detail":"…"}` | **`work`** 档：单次工具调用的摘要状态。 |
| `tool_trace_full` | `{"tool":"…","arguments":{},"result":"…","error":…}` | **`developer`** 档：工具入参/出参/错误详情。 |
| `citations_partial` | `{"items":[{"path","snippet","score"}]}` | **`work`** 档：引用列表（条目与片段可能截断）。 |
| `citations_full` | `{"items":[…]}` | **`developer`** 档：引用全文。 |
| `delta` | `{"text": "..."}` | **最终答复**正文增量；因分块可 **多次** 发送。 |
| `done` | `{}` | 正常结束。 |
| `error` | `{"code":"…","message":"…"}` | 业务或不可恢复错误；发送后流结束。见 §3.6。 |

**典型成功顺序**（非 Prompt 回显）：零段或多段 `reasoning_*` → 可选 `citations_*` → 一段或多段 `delta` → `done`。

**Prompt 回显模式**（`developer.prompt_echo` 为真）：**不调用 LLM**；直接产生 `delta`（内容为格式化后的 messages 回显文本，含固定标题「【Prompt 回显模式】」）与 `done`。见 §4。

### 3.6 `error` 事件的 `code`（已知值）

| `code` | 含义 |
|--------|------|
| `empty_message` | 无有效用户消息（见上文第 3.2 节）。 |
| `internal` | Agent 未正常结束（未收到结束状态）。 |
| 其他 | 未捕获异常时为 **异常类型名**（如 `RuntimeError`）；`message` 为人类可读说明（`OSError` 可能含路径）。 |

### 3.7 Agent 与流式行为摘要

- ReAct **最大步数**：16（实现常量，非请求体参数）。
- **JSON 模式**：对 LLM 请求为 JSON 模式；工具与最终答复解析依 Agent 实现。

---

## 4. 开发者 API（受配置门控）

以下路由**路径**始终注册；**敏感能力**在 `developer.show_dev_tools_ui` 为 `false` 时返回 **403**。

配置键见 `config/defaults.yaml` 中 `developer` 段与 `AppSettings`（`developer_show_dev_tools_ui`、`developer_prompt_echo`）。

### 4.1 `GET /api/v1/developer/ui`

- **不受** `show_dev_tools_ui` 限制（前端需据此决定是否展示开发控件）。
- **200**：

```json
{
  "show_dev_tools_ui": false,
  "prompt_echo": false
}
```

`prompt_echo` 为**运行时**值（可被 `PUT` 修改，见上文第 4.2 节）。

### 4.2 `PUT /api/v1/developer/prompt-echo`

- **Body**：`{"enabled": true}` 或 `false`
- **403**：`show_dev_tools_ui` 为 `false`。
- **200**：`{"prompt_echo": <bool>}`（与请求体一致，且已写回运行时 toggles）。

### 4.3 `GET /api/v1/developer/agent-tools`

- **403**：`show_dev_tools_ui` 为 `false`。
- **200**：

```json
{
  "tools": ["list_ksfs", "query_weather", "..."],
  "mcp_servers": [
    {
      "id": "amap_weather",
      "enabled": true,
      "entrypoint": "skills/amap-weather-mcp/server.py",
      "entrypoint_exists": true,
      "strip_http_proxy": true
    }
  ],
  "repo_root_resolved": "G:\\\\GithubProject\\\\Logos"
}
```

| 字段 | 说明 |
|------|------|
| `tools` | 当前会注入 `AgentShell` 的工具名排序列表（含 MCP 暴露的工具）。 |
| `mcp_servers` | 与配置逐项对应；`entrypoint_exists` 为仓库根解析后的脚本是否存在。 |
| `repo_root_resolved` | 服务端解析的仓库根绝对路径（供调试）。 |

---

## 5. 与代码及 GUI 的对应关系

| 资源 | 说明 |
|------|------|
| `src/logos/harness/ii_layer/api_v1.py` | 路由与 SSE 帧实现。 |
| `tests/test_stream5_api.py` | 契约回归：`health`、`chat`（含 `reasoning_delta` / `citations`）、`developer/*`。 |
| `src/gui/src/api/sseChat.ts` | 解析 `delta`、`reasoning_delta`、`citations`、`done`、`error`。 |
| `src/gui/src/api/developer.ts` | 开发者 UI 与 `prompt-echo`。 |

---

## 6. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-05-13 | 新建 V0.2：从实现与单测收口；取代此前散失的 V0.2 草稿；`API-V0.1.md` 改为归档对照。 |
