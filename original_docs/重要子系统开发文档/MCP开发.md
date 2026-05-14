# MCP 子系统 — 开发路线与验收（Logos）

> **地位**：宿主侧 **stdio MCP** 挂载、声明式多技能、与 **`harness/sg_layer`**（`GuardedToolRegistry`、白名单、输出裁剪）的接线说明与迭代计划。  
> **总纲**：`../ARCHITECTURE.md`、`../DECISIONS.md` §12；阶段排期见 **`../下一阶段开发计划.md`** 之 A2。  
> **配置键**：`config` 中 **`skills.mcp_servers`**（列表）；**不**在 `defaults.yaml` 预置第三方密钥类技能（如高德），由本机 `local.yaml` 按需追加。

---

## 1. 设计前提（与 CB / KSFS 资源的关系）

### 1.1 CB 的 Prompt 模板、KSFS 与「静态资源」放在哪？

| 类别 | 原计划语义 | 建议 |
|------|------------|------|
| **CB Prompt 模板** | 叙事/编剧用的可版本化提示片段 | **仍以仓库内受控路径为主**（例如 `resources/` 或专用模板目录），由 **宿主或确定性工具** 读取、拼装进 system/user 消息；**不必**为了「专业」先全部改成 MCP **`prompts/get`**。 |
| **KSFS 本体** | 事实源 `.md` | **继续走 HDL / `read_ksfs` / `retrieve`**；这是产品语义核心，**不要**改成依赖外置 MCP resource 才能读 KSFS。 |
| **其它模板文件** | 可能被工具按需读取 | **默认仍「被动读取」**：工具（含 MCP tool）在授权路径内读文件即可。 |

### 1.2 「被动读取」vs MCP **`resources` / `prompts` 主动提供」**

- **被动读取（推荐作为默认）**  
  - **优点**：模型简单、调试直观、与现有 KSFS/HDL 一致；权限边界落在 **S&G + 路径沙箱 + 工具白名单**。  
  - **缺点**：模板更新不会自动出现在「MCP Inspector 的资源树」里；跨宿主复用主要靠仓库路径约定。

- **主动提供（MCP `resources` / `prompts`）**  
  - **优点**：对 **外部 MCP Client**（Cursor、Inspector）友好；可声明 URI、版本、订阅语义；多宿主时「发现面」统一。  
  - **缺点**：宿主需实现 **list/read/getPrompt** 等桥接；与「KSFS 仅经 HDL」容易**概念重叠**，若不做边界容易双通道读同一文件、权限漂移。

**结论（建议定案）**  
- **KSFS 与 CB 核心模板**：保持 **被动读取 + 工具/宿主拼装** 为主路径。  
- **MCP `resources` / `prompts`**：作为 **可选增强** —— 当某 Skill 需要向 **第三方 MCP 生态** 暴露「可浏览模板」或「可参数化 prompt」时再启用；**不**用它替代 KSFS 主读路径。  
这样既符合你们「运行中被工具按需读取」的原计划，又保留将来对 MCP 生态「主动发现」的扩展面，二者分层而非二选一硬切。

### 1.3 产品定案（2026-05-12）：外部 MCP 客户端与「资源型 MCP 服务」

- **大概率不需要**将 CB 模板、KSFS 等 **提供给其它 MCP 客户端**（如 Cursor、MCP Inspector）作为其可订阅资源；也 **不要求**为此 **单独打包成对外 MCP 资源 / Prompt 服务**。  
- **现阶段**：维持 **宿主内工具 + 仓库内被动读取**；下文 **§5 E3**（`resources` / `prompts` 桥）**不作为下一阶段默认交付**，仅保留为「若产品需求变化再议」的扩展口。  
- **与 §1.2 的关系**：§1.2 仍描述技术选项；**§1.3 为当前排期下的执行口径**（下一阶段开发按此收敛）。

---

## 2. 已实现（基线）

| 项 | 说明 |
|----|------|
| **通用管线** | `skills.mcp_servers` → `build_v01_guarded_tool_registry` 遍历启用项 → `discover_mcp_tools_sync` → 按 `inputSchema` 注册；与内置工具同名则忽略；跨技能重名则先到先得并打日志。 |
| **子进程命令** | `mcp_server_argv(repo, entrypoint)`：`[sys.executable, <resolved script>]`。 |
| **环境** | `strip_http_proxy: true` 时剥离常见 `HTTP(S)_PROXY`；`env` 为额外注入键值。 |
| **示例技能** | `skills/example-stdio-mcp/server.py` 工具 **`echo`**。 |
| **验证技能** | `skills/amap-weather-mcp/`（`query_weather`），**不写入** `defaults.yaml`，仅在 `local.yaml` 配置。 |

**验收**：`pytest tests/test_mcp_*.py tests/test_mcp_stdio_process_leak.py` 通过；启用 `echo` 后对话或 registry 可调用。

---

## 3. 渐进式披露 + Obs 联动（分阶段方案）

> **目标**：技能增多时，**系统提示中不要默认塞满所有工具的完整 JSON Schema**；Token 与调用链可观测由 **Obs** 统一记录。

### 阶段 P1 — 提示词瘦身（优先）

| 动作 | 内容 |
|------|------|
| 实现 | 默认 `tools_prompt_section` 只输出 **工具目录**（`name` + 极短 `one_liner`），完整 `parameters` **不**进首屏。 |
| 元工具 | 增加 **`get_tool_schema(names[])`**（或等价名），返回所选工具的完整 JSON Schema；模型在调用前按需拉取。 |
| 验收 | 单测：首屏 prompt 长度上界；调用 `get_tool_schema` 后能执行真实工具调用。 |

### 阶段 P2 — 会话缓存与预算

| 动作 | 内容 |
|------|------|
| 实现 | 会话内缓存已下发的 schema；限制单次 `names` 数量与总字符；超限分批或拒绝。 |
| 验收 | 压测脚本或单测：同一工具重复 describe 不重复膨胀 prompt。 |

### 阶段 P3 — Obs 联动

> **执行拆分与验收**：见 **`Obs开发文档.md`**（第四阶段 Obs 主线：O1～O5）。

| 动作 | 内容 |
|------|------|
| 工具调用链 | 在现有 Agent/ReAct 日志中写入 **step 序号、tool 名、参数摘要（脱敏）、耗时**；GUI「调用链可视化」消费同一结构化日志字段（字段名在 Obs 规格中冻结）。 |
| Token | 在 LLM 请求前后记录 **prompt/ completion 估算 token**（或供应商 `usage`）；与 **渐进式披露** 联动：可选日志字段 `tools_prompt_bytes` / `schema_fetch_count`。 |
| 验收 | 开启某一 `log_profile` 时，单次会话可在日志文件中检索到上述字段；与 `SPEC-DISPLAY-AND-LOGGING-V0.1.md` 无矛盾。 |

**理想状态**：模型默认只见工具目录；复杂工具先 `get_tool_schema`；Obs 能回答「本轮 Token 花在哪、工具调了几次、每次多久」。

---

## 4. 子进程与资源泄漏测试（从轻到重）

| 级别 | 做法 | 验收 |
|------|------|------|
| **L1（已有）** | 单次 `tools/list`、`tools/call` 单测；`echo` 往返。 | CI 默认跑通。 |
| **L2（已有）** | `tests/test_mcp_stdio_process_leak.py`：重复 `call_mcp_tool_sync` 后 `psutil` 观察子进程数不异常累积。 | `pip install -e ".[dev]"` 后通过。 |
| **L3（可选）** | 长跑：连续 N 分钟、混合 discover/call、并发会话（未来多 worker）；`ps` / 任务管理器人工 spot check。 | 发布前 checklist；出异常再开 issue。 |
| **L4（可选）** | Windows / Linux 双 CI job，专门跑 MCP 相关子集。 | 子进程语义 OS 差异可被发现。 |

**为何需要 L2+**：短连接模型在异常路径下仍可能出现句柄/子进程未回收；**重复压测**比「单次 happy path」更能暴露问题。实现上 **优先 psutil**（已在 `dev` 依赖中），避免解析 `ps` 文本。

---

## 5. 通用插件模型的后续增强（路线图）

| 步骤 | 内容 | 验收 |
|------|------|------|
| E1 | **`hooks` 声明式扩展**：如 `strip_http_proxy` 之外的 `env_normalize` 插件名（字符串枚举），避免为每个第三方写死 Python 分支。 | 高德仅 YAML + 枚举即可挂载。 |
| E2 | **多传输**：在保持 stdio 默认的前提下，预留 `transport: stdio \| sse`（实现可后移）。 | 文档与类型中有占位，默认行为不变。 |
| E3 | **MCP `resources` / `prompts` 桥**（**暂缓**，见 **§1.3**）：仅当未来确需对外 MCP 客户端暴露时再启用。 | 需求成立后再写集成测；默认不排入下一阶段。 |

---

## 6. 理想状态（收口画像）

1. **配置**：`skills.mcp_servers` 为唯一声明入口；无仓库内默认密钥技能。**布尔项 `enabled`**：条目已写 `id` 与 `entrypoint` 时，**省略 `enabled` 视为 `true`（默认挂载）**；需临时关闭时请显式 `enabled: false`。  
2. **治理**：所有 MCP 工具经 `GuardedToolRegistry`；命名冲突策略明确。  
3. **披露**：P1～P3 完成，Token 与工具链可观测。  
4. **测试**：L1+L2 为合并门槛；L3 为发布前自选。  
5. **文档**：**`API-V0.2.md`** 若增加与 MCP 调试相关 HTTP 字段，与 GUI 同步（见下一阶段计划第 1.1 节）。

---

## 7. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-05-12 | 初版：`mcp_servers` 通用管线、渐进式披露与 Obs、进程泄漏测试分级、resources/prompts 与被动读取的定案建议。 |
| 2026-05-12 | **§1.3**：不面向其它 MCP 客户端打包资源服务；维持现状；E3 暂缓。下一阶段按 §3～§5 主队列推进。 |
| 2026-05-13 | **§6**：`skills.mcp_servers` 条目省略 `enabled` 时默认 **挂载**（`loader._parse_mcp_servers`）；显式 `enabled: false` 关闭。宿主侧 `discover`/`call_tool` 对子进程设置 **cwd=仓库根**（与 `mcp_stdio_sync.stdio_params_for_example_skill` 一致）。 |
