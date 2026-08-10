# Logos — 叙事写作智能助手

> **面向游戏叙事创作者的本地智能写作 Agent** | Python + React + Electron  
> 技能驱动（Skill-driven）· 多范式 Agent · 融合检索 · Skill 治理  
> 内置《西游记》示例知识库，克隆即用

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python)](https://www.python.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-React-3178C6?logo=typescript)](https://www.typescriptlang.org/)
[![Electron](https://img.shields.io/badge/Electron-47848F?logo=electron)]()
[![MIT License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## 项目定位

Logos 是一款面向**游戏叙事创作者**（文案、叙事策划）的本地智能写作助手。

与通用 AI 聊天工具不同，Logos 的核心假设是：**作家的叙事设定知识库（KSFS）是唯一事实源**，Agent 的能力通过**技能（Skill）清单**组织——用户从面板选择一项能力，按固定向导完成任务，而非默认打开空白万能聊天框。

> 这也是一份技术求职作品，展示了**从产品架构到工程实施**的完整能力。

---

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    GUI / Electron                       │
│        技能面板 · 任务向导 · 多标签会话 · 归档缓存            │
└──────────────────────────┬──────────────────────────────┘
                           │ HTTP + SSE (Server-Sent Events)
┌──────────────────────────▼──────────────────────────────┐
│               Platform Layer (支撑层)                    │
│    API_v1 · 组合根装配 · S&G 白名单 · Obs 可观测性 · 配置    │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│                Agent Layer (决策层)                      │
│       Shell 调度器 · CB 上下文构建 · PR 范式路由            │
│      ┌──────────┐ ┌───────┐ ┌──────────────┐           │
│      │ dialogue │ │ react │ │ Plan&Execute │           │
│      └──────────┘ └───────┘ └──────────────┘           │
└──────┬─────────────────────────────────┬────────────────┘
       │                                 │
┌──────▼──────┐                  ┌───────▼─────────────────┐
│  MCP Skills │                  │  Infrastructure Layer   │
│  (可插拔)    │                  │  检索 · LLM 适配 · 向量   │
└─────────────┘                  └──────┬──────────────────┘
                                        │
                               ┌────────▼──────────────────┐
                               │  HDL: Knowledge Storage   │
                               │  KSFS · HSI · SVS · FTS5  │
                               │  (唯一事实源 + 三层索引)     │
                               └───────────────────────────┘
```

---

## 核心技术亮点

### 🧠 范式路由（Paradigm Router）

不是所有 Agent 场景都适合 ReAct。Logos 定义了 **3 种执行范式**，每个 Skill 在 manifest 中预先声明，路由层确认后调度：

| 范式 | 适用场景 | 协议 |
|------|----------|------|
| **dialogue** | 自由文本多轮（聊天启发、语病检查） | 自然语言，非 JSON |
| **react** | 工具循环（检索问答、创作启发、设定撰写） | JSON-only ReAct |
| **plan** | 先计划再执行（大纲规划） | Phase A 结构化计划 |

**设计取舍**：不搞运行时"智能猜范式"——Skill 作者在 manifest 定好边界，PR 只做路由确认。开发者可通过 `paradigm_override` 试验，但不作为默认路径。

### 🔍 三路融合检索（KSFS 为基准 + 知识图谱补充）

叙事写作检索与通用 RAG 不同——用户常搜**专有名词**（人名/地名/物品名），需要精确命中而非语义近似。Logos 以 **KSFS（Markdown 文件树）为唯一事实基准**，在其上构建三层索引：

| 路 | 技术 | 职责 |
|----|------|------|
| **HSI** | SQLite 元数据索引 | 路径/title 弱匹配 |
| **SVS** | Chroma 向量库 (bge-small-zh) | 语义近似 |
| **Sparse** | SQLite FTS5 全文索引 | 专有名词精确命中 |

三路按 path 去重取 max score 排序，Agent 通过 `retrieve` 工具拿到 `Citation[]` 后，再调 `read_ksfs` 读全文核实——**chunk snippet 是"诱饵"，真相在全文**。

此外，**知识图谱（CozoDB + Datalog）** 提供实体关系查询补充：`kg_query` 工具可检索一跳/多跳邻居（如「孙悟空 → 持有 → 如意金箍棒」）和最短路径。数据层已实现，`retrieve_qa` / `setting_write` 等 Skill 已注册该工具。

### 🛡️ Skill 治理

Logos 的 Skill 系统既有**本地进程内工具**（检索、文件读写、草稿晋升等），也有**通过 MCP 协议接入的外部工具**（高德天气等）。无论接入方式，治理策略统一：

- **工具白名单**：每 Skill 在 manifest 声明 `allowed_tools`，S&G 层构造 scoped registry，不向 LLM 暴露全目录
- **路径沙箱**：`read_ksfs` / `write_draft` 等文件工具仅允许操作 KSFS 树内或 workspace 内的相对路径，禁止绝对路径与 `..` 穿越
- **MCP 进程治理**：Discovery 缓存（同一配置下 `tools/list` 仅执行一次）；进程泄漏防护（每次调用启停一次 stdio 进程，超时 kill）
- **Fail-fast 配置校验**：`mcp_servers` 等配置项误写为非列表时抛出 `ValueError`，不静默降级

### 📋 工程纪律

| 实践 | 实现 |
|------|------|
| **API 契约同步** | `.githooks/commit-msg` + `pre-commit` 脚本——改 `api_v1.py` 须同时暂存 `API-V0.2.md` 与契约测试 |
| **分层测试** | L1 单元 → L2 集成（无 HTTP）→ L3 契约（SSE 事件名校验）→ L4 慢测（真实 embedder） |
| **检索基准** | 30-50 条中文叙事 query 的基准集，`Recall@k` / `MRR` / 组件隔离分析 |
| **可观测性** | 工具调用链 `logos_tool_chain_v1` 写入维护轨日志，4 级 `log_profile`（minimal 到 audit） |

---

## 能力速览

### ✅ 已实现

- **Skill 驱动 GUI**：技能面板 → 任务三步向导 → SSE 流式执行 → 归档（Electron + React）
- **KSFS 叙事知识库**：`.md` 文件树作为唯一事实源，含 front matter 元数据
- **示例数据**：内置《西游记》主题示例 KSFS（人物/地点/势力/概念/种族共 9 篇实体），克隆即用
- **设定导入 Pipeline**：粘贴结构文本 → LLM 渲染为草稿 → 人审晋升至 KSFS
- **三路融合检索**：HSI + SVS (Chroma) + Sparse (FTS5)，增量同步
- **知识图谱**：CozoDB Datalog 实体关系查询（`kg_query` 工具已注册）
- **对话 / ReAct / Plan 三种范式**（Plan 为 Phase A 预览）
- **Obs 可观测性**：工具调用链落盘、4 级日志 profile、GUI 可选日志根展示
- **单实例 Electron 壳**：健康门、后端托管、退出清理、Windows portable 打包

### 🧊 规划中或有限

- 知识图谱融合检索（`kg_query` 工具已注册，但尚未接入 `FusedRetrievalService` 的融合管道）
- RRF 混合排序（当前三路取 max 已够用，基准集验证后可引入）
- 大纲规划 Skill 产品定稿（Phase A 代码已就绪，但面板默认隐藏）
- Pipeline 范式（`import_setting` 内部使用，未对用户开放为独立 Skill）
- 安装包/签名/自动更新（便携版够用，暂缓）

---

## 快速启动

### 🐳 方式 A：Docker 一键体验（推荐快速试用）

> 无需安装 Python/Node.js，只需 **Docker Desktop**。适合给面试官、同事演示。

```bash
# Windows — 双击根目录的 start.cmd
start.cmd

# macOS / Linux — 终端执行：
chmod +x start.sh && ./start.sh
```

脚本自动完成：**生成默认配置 → 构建镜像 → 启动后端+前端 → 打开浏览器**。

```
前端界面 → http://localhost:3000    （Nginx + React）
后端 API → http://localhost:8000    （FastAPI，/api 自动代理）
```

停止：在 Docker Desktop 中停止容器，或终端执行 `docker compose down`。

---

### 🛠️ 方式 B：开发环境启动（适合改代码调试）

> 需要本机安装 **Python 3.11+** 和 **Node.js 18+**。支持 Vite 热重载 + Electron 壳。

**双击 `scripts\start_logos.cmd`（Windows）** 一键启动三个窗口：

| 窗口 | 端口 | 技术 |
|------|------|------|
| Logos Backend | :8000 | Python FastAPI |
| Logos Vite | :5173 | React + Vite（热重载） |
| Logos Electron | 加载 Vite | 桌面壳 |

**或手动分步启动（macOS/Linux 通用）：**

```bash
python -m venv .venv
source .venv/bin/activate                  # Windows: .\.venv\Scripts\activate
pip install -e ".[dev]"

cp config/local.example.yaml config/local.yaml

python scripts/run_dev_backend.py          # 终端1: 后端 :8000
cd src/gui && npm install && npm run dev   # 终端2: GUI :5173
```

浏览器打开 `http://localhost:5173`，或 `cd src/electron && npm run electron:dev` 启动桌面壳。

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | **Python 3.11+** · FastAPI · httpx · PyYAML · jsonschema |
| 前端 | **TypeScript** · **React** · **Vite** |
| 桌面壳 | **Electron**（contextIsolation + preload 窄 IPC）|
| 向量检索 | **Chroma** · **sentence-transformers** (bge-small-zh) |
| 关键词检索 | **SQLite FTS5** |
| 知识图谱 | **CozoDB** + Datalog（数据已完成，融合待接） |
| MCP 协议 | **mcp** 1.2+ (stdio 传输) |
| LLM 协议 | OpenAI 兼容 API（DeepSeek / OpenAI / 任何兼容服务） |
| 测试 | **pytest** · Playwright（E2E）|

---

## 仓库结构

```
Logos/
├── src/
│   ├── logos/              # Python 核心
│   │   ├── agent/          # Agent 决策层: Shell, PR, CB, 范式执行器
│   │   ├── platform/       # 支撑层: HTTP API, S&G, Obs, 配置, 组合根
│   │   ├── infrastructure/ # 基础设施: 检索, LLM 适配, 向量库
│   │   ├── persistence/    # 持久层: KSFS, HSI, SVS, Sparse, KG, 晋升
│   │   └── ports/          # 端口抽象: 检索, 元数据, 向量, 稀疏索引
│   ├── gui/                # React + Vite 前端
│   └── electron/           # Electron 桌面壳
├── skills/manifests/       # 产品 Skill YAML 声明
├── resources/prompts/      # Prompt 模板资产 (范式/技能/持久化档位)
├── resources/pipelines/    # Pipeline 阶段配置
├── resources/entity_template/ # 实体模板与渲染规格
├── config/                 # defaults.yaml + local.yaml(本机)
├── tests/                  # 分层测试套件 (含检索基准集)
├── scripts/                # 开发与运维脚本
└── docs/                   # 对外介绍文档
```

---

## 相关文档

| 如果你是… | 建议阅读 |
|-----------|----------|
| 想快速理解设计思路 | [docs/项目概述.md](docs/项目概述.md) → [docs/架构概览.md](docs/架构概览.md) |
| 想动手运行 | [docs/快速开始.md](docs/快速开始.md) |
| 想了解检索怎么做的 | [docs/子系统文档/KSFS与叙事知识库.md](docs/子系统文档/KSFS与叙事知识库.md) |
| 想了解 Agent 范式 | [docs/子系统文档/Agent与范式路由.md](docs/子系统文档/Agent与范式路由.md) |
| 想了解 Skill 系统 | [docs/子系统文档/任务与Skill界面.md](docs/子系统文档/任务与Skill界面.md) |
| 想了解 MCP 集成 | [docs/子系统文档/Skills与MCP扩展.md](docs/子系统文档/Skills与MCP扩展.md) |
| 完整文档索引 | [docs/README.md](docs/README.md) |

---

## 许可

[MIT License](LICENSE)
