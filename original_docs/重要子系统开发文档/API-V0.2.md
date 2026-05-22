# HTTP API 契约 — V0.2

> **地位**：**现行权威**（2026-05-13 收口）。由 **I&I（Stream 5）** 在 `src/logos/harness/ii_layer/api_v1.py` 实现；变更请同步 **GUI（Stream 6）**、`tests/test_stream5_api.py` 与 `SPEC-DISPLAY-AND-LOGGING-V0.1.md` / 展示规格中涉及 HTTP 的段落。  
> **版本说明**：URL 仍为 **`/api/v1/*`**（未改为 `/api/v2`）；**文档版本 V0.2** 表示相对 **`API-V0.1.md`（归档）** 的契约增量。  
> **沿革**：V0.1 仅含 health + chat 的四种 SSE；V0.2 增补 **按展示档位分事件**（`reasoning_summary` / `reasoning_full`、`citations_*`、`tool_trace_*`）、**`GET /api/v1/bootstrap`**、**开发者只读/调试端点**，并固化 **请求体消息拆分** 与 **`operating_mode`** / **`presentation`** 语义。

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
  - `llm_mode`：`"stub"` \| `"remote"`；无 `llm.api_key` 或环境 `LOGOS_FORCE_STUB_LLM=1` 时为 **`stub`**（桩回复带「桩后端」前缀），否则 **`remote`**
  - `obs_show_log_root_in_gui`：布尔（来自 `obs.show_log_root_in_gui`，默认 **false**；Obs O4 与 **`GUI开发文档.md`** §6.2 对齐）
  - `obs_logs_root`：字符串或 **`null`**；仅当 `obs_show_log_root_in_gui === true` 时为 **已解析的绝对路径**（`paths.logs_root` 展开），否则为 **`null`**（不向 GUI 暴露日志根）
  - `ui`：对象（来自配置 `ui.*`，供 GUI 首屏；见 **`DECISIONS.md` §13.6**、**`GUI开发文档.md`** §12.4），字段：
    - `SSE_maxNum`：正整数（来自 `ui.SSE_maxNum`，默认 **3**）；后台 SSE 并发上限，超额 **排队**
    - `cache_warn_bytes`：非负整数（来自 `ui.cache_warn_bytes`，默认 **524288000**，即 500×1024×1024 字节）；会话缓存占用告警阈值
  - `skills`：数组（**F5-08**），供 GUI **技能面板**与任务/对话页元数据；每项字段：
    - `skill_id`：字符串，稳定标识（对应 `skills/manifests/<skill_id>.yaml`）
    - `display_name`：字符串
    - `description`：字符串（技能面板卡片**一句话**摘要）
    - `ui_instructions`：字符串（任务页 `/task`、对话页 `/chat` **「技能说明」**区块正文；YAML 多行经 manifest `ui_instructions: |` 写入；**勿**在 GUI 按 `skill_id` 硬编码）
    - `persistence_tier`：`"p0"` \| `"p1"` \| `"p2"`
    - `paradigm`：`"dialogue"` \| `"react"` \| `"plan"` \| `"pipeline"`
  - 来源：宿主扫描 `skills/manifests/*.yaml`（与 `get_skill_manifest` 一致）；**不含** `turn_policy` / `allowed_tools`（路由与执行见 manifest 或前端 `catalog.ts` 回退）
  - `conversations_cache_root`：字符串；档 B 会话 JSON 目录的**绝对路径**（来自 `paths.CONVERSATIONS_CACHE`，相对仓库根解析）
- 与 `SPEC-DISPLAY-AND-LOGGING-V0.1.md` 正交：会话内切换展示档位 **不** 通过本接口写回配置。

---

## 3. `POST /api/v1/chat`（**SSE**，主路径）

V0.2 **强制**采用 **Server-Sent Events** 流式返回；**不提供**同路径 JSON 非流式降级（调试可加独立路由，非本契约范围）。

### 3.1 请求

- **Header**：`Accept: text/event-stream`（推荐）；`Content-Type: application/json`
- **Body（JSON）**：

```json
{
  "skill_id": "lint_zh",
  "task_input": { "text": "待检查段落……" },
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
| `skill_id` | 字符串 | **推荐必填**。产品 Skill 标识（manifest 见 `skills/manifests/<skill_id>.yaml`）。**省略**时服务端回退 **`chat_inspire`** 并写 WARNING 日志（过渡行为；目标态为 **400**）。**未知** id → HTTP **400** JSON（不开启 SSE），`detail` 为人类可读说明。 |
| `task_input` | 对象 | 可选。任务向导第二步输入；结构依该 Skill 的 `input_schema`（F5-03 起参与 CB 拼装；F5-02 仅透传接收）。 |
| `paradigm_override` | 字符串 | 可选。开发者试验：`dialogue` \| `react` \| `plan` \| `pipeline`；**仅当** `developer.show_dev_tools_ui=true` 或进程环境 `LOGOS_FORCE_STUB_LLM=1` 时覆盖 manifest 范式；否则忽略。 |
| `messages` | 数组 | 每项 `role` ∈ `system` \| `user` \| `assistant`，`content` 为字符串。 |
| `operating_mode` | 字符串 | 可选，默认 **`author`**。服务端按小写比较；内置 **`screenwriter`**（编剧）与 **`author`**（作者）两种提示后缀，其余值按 **author** 处理。 |
| `presentation` | 字符串 | 可选。`work` \| `developer`（及别名 `dev`）；省略则使用服务端 `ui.default_presentation`。影响 chat SSE 中推理与引用等事件的**档位**（摘要 vs 全文），见 §3.5。 |

**工具注册（S&G）**：服务端按 manifest 的 `allowed_tools` 调用 `build_v01_guarded_tool_registry(..., allowed_tools=…)`，仅注册白名单内工具名（可为空列表，如 `lint_zh`）。未传 `skill_id` 时回退 Skill 的 `allowed_tools` 同样生效。

**范式路由（PR，F5-03～F6-03）**：解析 manifest 后 `select_paradigm(skill_id)` → Shell 分支：`dialogue` 为自然语言 SSE（`json_mode=false`，**无** `reasoning_*` 事件）；`react` 为现行 ReAct + `reasoning_*` / `tool_trace_*`；`plan` 为 **Phase A** 单次计划生成（`json_mode=true`，SSE 仍为 `delta` + `done`，**无** ReAct 条令，示例 Skill **`outline_plan`**）；`pipeline` 为设定导入流水线（示例 Skill **`import_setting`**），SSE 为 **`pipeline_step`** / 可选 **`pipeline_warning`** + 摘要 **`delta`** + **`done`**（**无** ReAct 条令）。`dialogue` **不**在流结束前调用 `retrieval.query` 阻塞。

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
| `pipeline_step` | `{"step_id":"…","status":"started"\|"ok"\|"error","summary":"…"}` | **`pipeline` 范式**（F6-03）：阶段进度；`status=error` 后紧跟 `error` 并结束流。 |
| `pipeline_warning` | `{"warnings":["…"]}` | **`pipeline` 范式**：只读重叠等警告（F6-08 起可非空）；可 **多次**。 |
| `done` | `{}` 或 pipeline 扩展字段 | 正常结束。`pipeline` 成功时 `done` 可含 `written_paths`、`warnings`、`unit_count`、`batch_id`。 |
| `error` | `{"code":"…","message":"…"}` | 业务或不可恢复错误；发送后流结束。见 §3.6。 |

**典型成功顺序**（非 Prompt 回显）：

- **dialogue / plan**：零段或多段 `reasoning_*`（plan 通常无）→ 可选 `citations_*`（plan 无）→ 一段或多段 `delta` → `done`。
- **react**：`reasoning_*` → 可选 `tool_trace_*` → 可选 `citations_*` → `delta` → `done`。
- **pipeline**：多段 `pipeline_step` → 可选 `pipeline_warning` → 一段 `delta`（写入摘要）→ `done`。

**Prompt 回显模式**（`developer.prompt_echo` 为真）：**不调用 LLM**；直接产生 `delta`（内容为格式化后的 messages 回显文本，含固定标题「【Prompt 回显模式】」）与 `done`。见 §4。

### 3.6 `error` 事件的 `code`（已知值）

| `code` | 含义 |
|--------|------|
| `empty_message` | 无有效用户消息（见上文第 3.2 节）。 |
| `internal` | Agent 未正常结束（未收到结束状态）。 |
| `not_implemented` | 已废弃于 `pipeline`（F6-03 已接线）；保留供历史客户端对照。 |
| `pipeline_step_failed` | `pipeline` 某阶段 `pipeline_step.status=error`。 |
| `invalid_skill` | `pipeline` Skill 缺少 `pipeline_profile`。 |
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
| `tests/test_stream5_api.py` | 契约回归：`health`、`bootstrap`、`chat`（含分档位 SSE）、`developer/*`。 |
| `tests/test_sse_chat_contract.py` | SSE 载荷与事件名结构校验。 |
| `src/gui/src/api/sseChat.ts` | 解析 `delta`、`reasoning_summary` / `reasoning_full`、`citations_partial` / `citations_full`、`tool_trace_*`、`done`、`error`；请求体可选 `presentation`。 |
| `src/gui/src/api/bootstrap.ts` | 首屏 `GET /api/v1/bootstrap`。 |
| `src/gui/src/api/developer.ts` | 开发者 UI 与 `prompt-echo`。 |

---

## 6. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-05-13 | 对齐 A3：沿革与 GUI 表改为分档位 SSE 事件名；补充 `bootstrap.ts` / `test_sse_chat_contract` 引用。 |
| 2026-05-14 | **§2.1 `bootstrap`**：增补 **`obs_show_log_root_in_gui`**、**`obs_logs_root`**（Obs O4，默认不向 GUI 暴露日志根）。 |
| 2026-05-16 | **§2.1 `bootstrap`**：增补 **`ui`** 段（**`SSE_maxNum`**、**`cache_warn_bytes`**）；对齐 GUI 步 G2 / **`DECISIONS.md` §13.6**。 |
| 2026-05-21 | **§2.1 `bootstrap`**：增补 **`skills[]`**（F5-08）；技能面板从 manifest 摘要动态渲染。 |
| 2026-05-21 | **§2.1 `bootstrap`**：增补 **`skills[].ui_instructions`**、**`conversations_cache_root`**；GUI「技能说明」与 manifest 绑定（见 **`GUI开发文档.md`** §11.6）。 |
| 2026-05-21 | **§3.1 范式路由**：`plan` Phase A（`outline_plan`）改为 `delta`+`done`；`pipeline` 仍为 `not_implemented`（F5-09 / F5-10 对齐）。 |
