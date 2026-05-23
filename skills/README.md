# `skills/` — 能力层

与 **`src/logos/`** 并列。本目录含两类内容，**禁止混称**（见 **`docs/子系统文档/Skills与MCP扩展.md`**）：

| 子目录 | 类型 | 说明 |
|--------|------|------|
| **`manifests/`** | **产品 Skill** | `*.yaml` manifest；`get_skill_manifest(skill_id)`（`logos.harness.skills_registry`） |
| **`<包>/server.py`** | **工具 Skill（MCP）** | 可插拔 MCP Server，经 **`harness/sg_layer`** 暴露 **tools** |

## 产品 Skill manifest（F5-01）

- 路径：**`skills/manifests/<skill_id>.yaml`**
- 样例：`lint_zh`、`chat_inspire`；L1 占位：**`skills/<skill_id>/DESIGN.md`**
- 详见 **`manifests/README.md`**

## MCP 工具包（既有）

> **现阶段（2026-05-12）**：**不要求**在本目录新增「设定导入」MCP 包；该方向封存见 **`original_docs/重要子系统开发文档/设定导入Skill开发.md`**。仍可用 **`example-stdio-mcp/`** 验证 MCP 与 S&G 接线。

## 与「设定导入」的关系（已定方向，实现延后）

- **用户触发路径**：`DECISIONS.md` §12.1 导入流水线以 **「触发 Skill」** 为起点；**物理上**宜在 `skills/` 下新增独立目录（例如 `settings-import-mcp/`，名称实现期再定），内含 MCP 入口脚本、工具 schema、对 `entity_template` 的引用说明等。
- **不在 Skill 里独占的部分**：**JSON Schema 校验、按 `render_spec` 写 `workspace/setting_entry/`、晋升与 HSI** 属于 **HDL / `logos.persistence`（及 `logos.tools`）**；Skill 负责 **编排**（收粘贴、调 LLM、调本机校验/写盘 API 或受控工具），避免在 Skill 仓库复制第二套与 **`resources/entity_template/`** 脱节的契约。

## 仓库内示例

- **`example-stdio-mcp/`**：真实 MCP（FastMCP + stdio），工具 **`echo`**；另含 **`echo_worker.py`** 供非 MCP 子进程生命周期测试。
- **`amap-weather-mcp/`**：完整 MCP（FastMCP + stdio），工具 **`query_weather`**；在 `config/local.yaml` 的 **`skills.mcp_servers`** 中启用并配置 `env.AMAP_WEB_KEY`（详见该目录 `README.md`）。

分层见 **`docs/架构概览.md`**；KSFS 与导入见 **`docs/子系统文档/KSFS与叙事知识库.md`**。
