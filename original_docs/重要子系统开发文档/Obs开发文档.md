# Logos — Obs（可观测性 / 日志子系统）开发指导

> **地位**：**日志落盘粒度、维护轨与日常轨分工、与配置 `obs.log_profile` 的关系** 以 **`SPEC-DISPLAY-AND-LOGGING-V0.1.md`**、**`API-V0.2.md`**（`bootstrap` 中的 `log_profile`）、**`logs/README.md`**、**`ARCHITECTURE.md`**（Obs 目录约定）为权威组合。本文在第四阶段承担 **「排期、分步、验收与实现要点」** 的补充：把 **Agent / 工具 / MCP 调用链** 与 **GUI 排障消费** 串成可执行里程碑，并与 **`MCP开发.md`** §3「Obs 联动」对齐。  
> **边界重申**（与 SPEC 一致）：**用户屏幕上展示什么** 由 I&I + GUI（展示档位）负责；Obs 负责 **记**——不在本文重新定义 WM / 开发者展示语义。

---

## 1. 预期效果（第四阶段结束时「好」的样子）

| 维度 | 预期 |
|------|------|
| **落盘** | 在约定 `log_profile` 下，单次对话或多轮 ReAct 可在 **`logs/maint/`** 相应文件中检索到 **结构化** 的步序号、工具名、耗时、结果/错误摘要（参数级内容遵守脱敏与截断策略）。 |
| **与 MCP 一致** | MCP stdio 子进程生命周期事件与工具调用结果，与内置工具路径使用 **同一套字段约定**（或明确映射表），避免 GUI 解析分叉。 |
| **与 Electron 长会话** | 后端崩溃/重启、壳层状态可与 **`electron-shell.log`**、Python 维护轨 **交叉时间戳** 对照（不要求合并单文件）。 |
| **GUI（可选增量）** | 至少一种 **开发者向** 消费方式：例如「复制最近一轮工具摘要」、或极简「调用链时间线」只读视图——**不**强制第四阶段完成复杂可视化；以日志可检索为硬验收。 |
| **回归** | 新增字段或事件名有 **单测或契约测**（grep 日志样例 / JSON 行）防漂移；与 **`test_stream5_api`** 精神兼容处不弱化 HTTP/SSE 契约纪律。 |

---

## 2. 分步开发与每步验收

### O1 — 现状审计与字段表（只读 + 文档）

| 产出 | 验收 |
|------|------|
| 梳理 `path_handlers` 路由、`obs.log_profile` 各档位实际写入路径；列出 Agent/ReAct/MCP 已有日志点（文件 + 级别）。 | 审计笔记写入 **`DEVLOG.md`** 或本文 **§5 修订记录**；团队成员能据表找到「一次对话对应哪些文件」。 |

### O2 — 调用链最小字段冻结

| 产出 | 验收 |
|------|------|
| 在实现中固化 **JSON 行或等价结构** 的键名：`step_index`、`tool_name`、`elapsed_ms`、`status`、`param_digest`（或占位）、`error_class` 等（允许与 **`MCP开发.md`** P3 表格对齐后微调一次）。 | **代码注释或短 spec 段**（可放在本文 §5）写明冻结字段；**单测**：模拟一轮带工具调用的对话，断言日志中出现上述键（或对 `maint/` 样例行快照测）。 |

### O3 — MCP / 内置工具路径对齐

| 产出 | 验收 |
|------|------|
| MCP `call_tool` 与内置工具在写入前走统一 **摘要/脱敏** 辅助函数；重复对话不产生未关闭句柄（与 **P1-MCP-2** 协同）。 | **`tests/test_mcp_stdio_process_leak.py`** 仍绿；新增或扩展测试：**带 MCP 的对话**后日志行数与进程数在阈值内；非法配置 **fail fast** 与 **P1-MCP-3** 对齐。 |

### O4 — GUI 薄消费（可选）

| 产出 | 验收 |
|------|------|
| 开发者菜单或设置页：**展示「日志根路径」**、**一键打开 `maint/`**（Electron `shell` 在 Main 中做 allowlist）、或「复制最近工具摘要」从内存态拼接（**不**要求 GUI 解析完整历史 log 文件）。**是否向 GUI 暴露「解析后的日志根绝对路径」**由配置 **`obs.show_log_root_in_gui`** 控制（默认 **false**）；为 true 时 **`GET /api/v1/bootstrap`** 返回 **`obs_logs_root`**，GUI 据此展示；与 **`GUI开发文档.md`** §6.2 一致。 | 与 **`GUI开发文档.md`** §3 IPC 边界一致；无 renderer 直接 `fs`。 |

### O5 — 与 `verbose` / `audit` 档位回归

| 产出 | 验收 |
|------|------|
| 文档化各 `log_profile` 下 **哪些字段保证出现**；与 **`SPEC-DISPLAY-AND-LOGGING-V0.1.md`** §5.2 无矛盾。 | 单测或脚本：切换 profile（或环境覆盖）后抽样日志符合表格。 |

**建议合并顺序**：**O1 → O2 → O3** 尽量串行（.touch 同一批 harness 文件）；**O4** 可与 O3 尾段并行（不同目录）；**O5** 收尾文档与断言。

---

## 3. 开发要点与建议

1. **脱敏默认偏保守**：工具参数、检索片段可能含用户正文；`param_digest` 优先摘要化；全量仅出现在 `audit` 且文档提示风险。  
2. **不要通过加日志「修复」展示 bug**：展示错误应改 I&I/SSE；Obs 只增加**可观测性**。  
3. **性能（Obs 写盘侧）**：高频 DEBUG 在长会话下可能放大 IO；必要时 **异步写** 或 **采样**（若引入须在 SPEC 或 `defaults.yaml` 注释中说明）。**注意**：此处**不**指「模型写得好不好」；后者见 **`Harness Engineering文档.md`**；阶段计划中「性能」**默认**指软件整体性能（**`../已完成/第四阶段开发计划.md`** §8 **A**）。  
4. **与第四阶段主线顺序**：Obs 与 **A7**、**MCP** 并行时，优先合入 **不改变 HTTP 契约** 的 Obs 改动；若必须暴露新 `bootstrap` 字段，走 **`API-V0.2.md`** 与 githooks 同步流程。  
5. **Electron**：壳层审计 **`electron-shell.log`** 继续由 Main 写入；Obs Python 侧不强制解析该文件，仅文档互链。

---

## 4. 与其它文档的索引

| 文档 | 用途 |
|------|------|
| **`SPEC-DISPLAY-AND-LOGGING-V0.1.md`** | `log_profile`、展示与日志正交 |
| **`MCP开发.md`** §3 | 渐进式披露与 Obs P3 理想字段 |
| **`logs/README.md`** | `daily/` vs `maint/`、Electron 共根 |
| **`../已完成/第四阶段开发计划.md`** | 本 Obs 路线在阶段内的优先级（§2） |

---

## 5. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-05-14 | §3：区分 Obs 写盘「性能」与 **`../已完成/第四阶段开发计划.md`** §8 默认语义；互链 **`Harness Engineering文档.md`**。 |
| 2026-05-14 | **§6**：第四阶段 **S7～S10** 落地（O1 路由审计、O2 冻结字段、O3 ReAct 单点写链、O5 `log_profile` 表）；实现 **`src/logos/harness/obs/tool_chain.py`**；测 **`tests/test_obs_tool_chain.py`**。 |
| 2026-05-14 | **O4 / 配置**：新增 **`obs.show_log_root_in_gui`**（默认 false）与 **`bootstrap.obs_logs_root`**；GUI 仅在该开关为 true 时展示日志根；详 **`GUI开发文档.md`** §6.2。 |

---

## 6. 第四阶段交付：工具调用链与 `log_profile`（S7～S10）

### 6.1 O1 — 落点与路由审计（摘要）

| 类别 | 路径 / 行为 |
|------|-------------|
| **日常轨** | ``<logs_root>/daily/YYYY-MM/YYYY-MM-DD.log``；**固定** ``>= INFO``；与 ``obs.log_profile`` **解耦**（``logging_setup.configure_logging``）。 |
| **维护轨** | ``<logs_root>/maint/<子系统>.log``；路由见 ``path_handlers.MaintSubsystemFileHandler.ROUTES``（``logos.harness.mcp``→``mcp.log``；``logos.agent``→``agent.log``；``logos.api``→``api.log`` 等）。 |
| **工具调用链** | 记录器 ``logos.agent.tool_chain`` → **``maint/agent.log``**（与 ``logos.agent.react`` 同文件聚合）。 |
| **HTTP 对话** | ``POST /api/v1/chat`` 在流入口 ``prime_obs_log_profile_for_chat`` / ``reset_react_tool_steps``；``finally`` 中 ``clear_obs_log_profile_tls``（``api_v1.py``）。使用 **线程局部** 以兼容 Starlette 线程池迭代同步生成器。 |

### 6.2 O2 — 冻结字段（``logos_tool_chain_v1``）

实现：**``src/logos/harness/obs/tool_chain.py``**。``emit_tool_chain_v1`` 写入 JSON（作为 LogRecord ``消息`` 正文）须含：

| 键 | 说明 |
|----|------|
| ``event`` | 固定 ``logos_tool_chain_v1`` |
| ``step_index`` | 会话内自 1 递增 |
| ``tool_name`` | 工具名 |
| ``elapsed_ms`` | 毫秒 |
| ``status`` | ``ok`` \| ``error`` \| ``denied`` |
| ``param_digest`` | 脱敏 + 截断摘要 |
| ``error_class`` | 失败时类名或约定字面；成功 ``null`` |

### 6.3 O3 — 内置与 MCP 对齐

**单点**：``logos.agent.react`` 在 ``registry.execute`` 前后计时并 ``emit_tool_chain_v1``；MCP 与内置工具共用同一路径。``param_digest_for_log`` 对 ``api_key`` 等后缀键名脱敏。

### 6.4 O5 — 各 ``log_profile`` 与 ``tool_chain`` 可见性

| ``obs.log_profile`` | maint handler 阈值 | ``tool_chain`` 级别 | 保证（解析 JSON ``消息`` 内对象） |
|---------------------|-------------------|---------------------|-------------------------------------|
| ``minimal`` | WARNING | **WARNING** | 冻结键全集；**maint** 可见 |
| ``standard`` | INFO | INFO | 同上 |
| ``verbose`` | DEBUG | INFO | 同上 |
| ``audit`` | DEBUG | INFO | 同上；``param_digest`` 更长（见实现） |

**日常轨**：``minimal`` 下 ``tool_chain`` 为 WARNING 时 **``daily/…``** 仍收录，便于检索。

**单测**：**``tests/test_obs_tool_chain.py``**。
