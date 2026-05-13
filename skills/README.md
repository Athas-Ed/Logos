# `skills/` — 能力层（MCP Skill 包）

与 **`src/logos/`** 并列：此处放 **可插拔、可单独版本化** 的 **MCP Server**（及元数据），经 **`harness/sg_layer`** 治理后把 **工具（tools）** 暴露给 Agent。

> **现阶段（2026-05-12）**：**不要求**在本目录新增「设定导入」MCP 包；该方向封存见 **`original_docs/重要子系统开发文档/设定导入Skill开发.md`**。仍可用 **`example-stdio-mcp/`** 验证 MCP 与 S&G 接线。

## 与「设定导入」的关系（已定方向，实现延后）

- **用户触发路径**：`DECISIONS.md` §12.1 导入流水线以 **「触发 Skill」** 为起点；**物理上**宜在 `skills/` 下新增独立目录（例如 `settings-import-mcp/`，名称实现期再定），内含 MCP 入口脚本、工具 schema、对 `entity_template` 的引用说明等。
- **不在 Skill 里独占的部分**：**JSON Schema 校验、按 `render_spec` 写 `workspace/setting_entry/`、晋升与 HSI** 属于 **HDL / `logos.persistence`（及 `logos.tools`）**；Skill 负责 **编排**（收粘贴、调 LLM、调本机校验/写盘 API 或受控工具），避免在 Skill 仓库复制第二套与 **`resources/entity_template/`** 脱节的契约。

## 仓库内示例

- **`example-stdio-mcp/`**：真实 MCP（FastMCP + stdio），工具 **`echo`**；另含 **`echo_worker.py`** 供非 MCP 子进程生命周期测试。
- **`amap-weather-mcp/`**：完整 MCP（FastMCP + stdio），工具 **`query_weather`**；在 `config/local.yaml` 的 **`skills.mcp_servers`** 中启用并配置 `env.AMAP_WEB_KEY`（详见该目录 `README.md`）。

权威分层：`original_docs/ARCHITECTURE.md` §2.4–2.5；KSFS 与导入细则：`original_docs/重要子系统开发文档/KSFS开发.md` §7.3。
