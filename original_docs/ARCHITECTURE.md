# Logos — 架构总纲

## 1. 系统概述

**Logos** 是面向游戏叙事的双模式智能体（作家 / 编剧），采用分层架构：**决策层**编排任务，**基础设施层**提供检索与模型等全局能力，**能力层（Skills）**经 MCP 可插拔扩展，**持久层（HDL）**以 **KSFS** 为叙事知识**唯一事实源**。本文描述全流程结构、模块职责与接口约定；**KSFS / HDL 细节**以 **`重要子系统开发文档/KSFS开发.md`** 为准；**已定决策**见 **`DECISIONS.md`**。

**产品形态（现行）**：**独立工作助手**（不将内置编辑器作为作品正文第一现场）；**GUI 优先侧边栏**；桌面壳 **Electron**；主传输 **HTTP + SSE**（见 **`重要子系统开发文档/API-V0.2.md`**）。

---

## 2. 分层架构

数据自上而下；**基础设施**与 **Skills** 职责分离：**基础设施长期存活、服务全局；Skills 按需经 MCP 加载**。

**依赖方向（DIP）**：决策与编排依赖 **`logos.ports`**；**基础设施 / 持久化**实现端口；**I&I（harness/ii_layer）** 负责对外协议与**组合根装配**。

### 2.1 决策层（`src/logos/agent/`）

- **Shell**：调度器；经端口调用检索、模型、工作区等；不直接 import 具体驱动。
- **CB（Context Builder）**：模板与历史、上下文预算；模板资产默认 **`resources/prompts/`**。
- **PR（Paradigm Router）**：范式路由（默认 ReAct；演进可扩展）。

### 2.2 能力层 — Skills（`skills/`）

可插拔单元；**注册表**、**渐进式披露**；以 **本地 MCP Server** 为主，与核心进程解耦。**不包含** Retrieval / MS（属基础设施）。

### 2.3 基础设施层（`src/logos/infrastructure/` 等）

进程内 **内部 API**；含 **Retrieval**、**MS**、策略路由与适配器；**不等同于 Skills**。

- **Retrieval**：统一检索入口；内部路由 **HDL（HSI / SVS；KG 预留）**；**只读 KSFS** 原语仅供索引与检索管线（见 `KSFS开发.md`）。
- **MS**：模型服务（远程 API / 未来本地）。
- **系统工具（`src/logos/tools/`）**：文件 I/O、路径规范化等**无策略原语**。

**与 S&G 分工（已定案）**：实现放在 **`logos.tools`**；**`harness/sg_layer`** 负责白名单、路径沙箱、输出过滤、MCP 治理。

### 2.4 持久层 — HDL（`src/logos/persistence/`）

**唯一事实源**：配置项 **`paths.ksfs_root`** 下的 **KSFS**（默认 **`resources/ksfs/`**）。自 KSFS **直接**构建 **HSI**、**SVS**（见 **`KSFS开发.md`**）。

- **HSI**：SQLite 元数据、实体 `id`、路径、mtime、正文 body 哈希等。
- **SVS**：向量存储（V0.1 **ChromaDB**，默认集合名等见 `config/defaults.yaml` 与 `KSFS开发.md`）。
- **KG**：预留。

### 2.5 支撑层（`src/logos/harness/`）

- **I&I（`ii_layer/`）**：HTTP、**SSE**、静态 GUI、CLI；FastAPI 路由与组合根。
- **S&G（`sg_layer/`）**：沙箱、工具注册、MCP 进程治理与回收。
- **Obs（`obs/`）**：日志与可观测性；默认根目录 **`logs/`**，下分 **`daily/`**（按 `YYYY-MM/YYYY-MM-DD.log` 的日常轨，固定 INFO+）与 **`maint/`**（按子系统的维护轨 + `electron-shell.log`，级别随 `obs.log_profile`）；详见仓库内 **`logs/README.md`**。
- **Config（`config/`）**：`defaults.yaml` + 本机 **`local.yaml`**（不入库）。

### 2.6 端口与装配

| 要素 | 物理路径 |
|------|----------|
| 端口 | `src/logos/ports/`（`import logos.ports`） |
| HDL / 同步 | `src/logos/persistence/` |
| 工具原语 | `src/logos/tools/` |
| I&I / S&G / Obs | `src/logos/harness/` |

---

## 3. 项目目录结构（逻辑与物理）

**原则**：`src/` 为随版本发布的核心程序；**不入库**数据与索引分离；**Skills** 与 `src` 并列；**`scripts/`** 应提交。

```text
Logos/
├── src/
│   ├── logos/                 # Python 包 logos（见 src/README.md）
│   │   ├── agent/
│   │   ├── infrastructure/
│   │   ├── persistence/       # HDL：KSFS 扫描、HSI、SVS、同步等
│   │   ├── tools/
│   │   ├── harness/
│   │   │   ├── ii_layer/
│   │   │   ├── sg_layer/
│   │   │   ├── obs/
│   │   │   └── config/
│   │   └── ports/
│   └── gui/                   # Web GUI（Vite + React + TS）
├── skills/                    # MCP Skills 与元数据
├── config/
├── resources/
│   ├── prompts/               # CB 用 Prompt
│   ├── entity_template/     # KSFS 实体形态契约（schema / 渲染规格）
│   └── ksfs/                  # 默认 ksfs_root；用户实体 .md 常 gitignore
├── example_ksfs/              # 示例知识树
├── workspace/                 # 工作空间（非事实源）；含 setting_entry/ 等
├── models/                    # 说明可提交；权重目录常忽略
├── scripts/
├── tests/
├── .index/                    # Chroma、HSI 等（默认不入库）
├── logs/                      # 占位与 README 可提交；*.log 见 .gitignore
│   ├── daily/                 # 日常轨：YYYY-MM/YYYY-MM-DD.log（Obs）
│   └── maint/                 # 维护轨：子系统 .log；Electron 写 electron-shell.log
├── original_docs/
├── docs/
└── README.md
```

**说明**：

- **`workspace/`**：草稿、工件、**`setting_entry/`**（待落户设定导入草稿，见 `KSFS开发.md` §2、§7）；**勿**与 **`ksfs_root`** 混用。
- **`.index/`**：**`.vector_index/`**、**`.high-speed_index`** 等；与 `workspace/`、`ksfs_root` 分离。
- **`resources/entity_template/`**：与 **`resources/prompts/`**、**`ksfs_root`** **三分离**（见 `DECISIONS.md` §9）。

---

## 4. 一键启动与 GitHub

- **应提交**：`scripts/`、README 启动说明、**`config/local.example.yaml`**。
- **可不提交**：大二进制、`config/local.yaml`、`.index/`、**`logs/**/*.log`**（运行时落盘）、默认 **`workspace/`** 用户内容（例外见 `.gitignore` 与 `workspace/README.md`）；**`logs/`** 下说明与占位目录见 **`logs/README.md`**。

---

## 5. 与对外 `docs/` 的关系

内部迭代以 **`original_docs/`** 为准；对外可将定稿同步至 **`docs/`**。

---

*最后更新：2026-05-13 — 对齐 `logs/daily` 与 `logs/maint` 落盘约定、占位目录与 .gitignore。*
