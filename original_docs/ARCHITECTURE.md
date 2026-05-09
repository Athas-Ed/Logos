# Logos - 架构总纲



## 1. 系统概述

**Logos**是一个面向游戏行业的双模式智能体，采用分层架构设计，支持作家与编剧双运行模式按需切换。本文档描述**全项目全流程**的系统结构、模块职责与接口约定；具体版本的裁剪范围以对应 **SPEC**（如 `SPEC-V0.1.md`）为准。



## 2. 分层架构

数据流自上而下，支撑关系横跨各层；**新增基础设施层**，与**能力层（Skills）**在职责上分离：**基础设施长期存活、服务全局；Skills 为可插拔专业能力，按需经 MCP 加载**。重要子系统细节见 **`original_docs/重要子系统开发文档/`**。

**依赖方向（DIP）**：决策层与编排逻辑依赖**端口（抽象）**，不依赖具体存储或模型 SDK；**基础设施层**实现这些端口；**I&I** 负责进程边界上的适配与**依赖装配**（见 §2.6）。



### 2.1 决策层

负责请求调度与决策路由，不直接执行具体任务。

- Shell：核心调度器，接收用户输入，协调下层模块完成请求处理；依赖 **端口** 调用检索、模型、工作区等能力，不直接 import 具体驱动。

- CB：自动选择 Prompt 模板，组装最终上下文，管理对话历史。重要子系统。

- PR：根据任务类型选择 Agent 范式（默认 ReAct，V0.1 仅开发 ReAct）。重要子系统。



### 2.2 能力层（Skills）

**设计意图**：可插拔的专业能力单元；**注册表模式**；**渐进式披露**（按需暴露工具/元数据，避免上下文膨胀）；**通过 MCP 暴露能力**，以 **本地 MCP Server** 为主，与核心进程解耦。

- 不包含 Retrieval / MS；二者归属 **§2.3 基础设施层**。

- V0.1 至少一个示例 Skill（stdio MCP），与内置工具 schema 尽量同源，避免两套真理。



### 2.3 基础设施层（Infrastructure Layer）

为全局提供 **内部 API**（进程内调用），生命周期通常与应用同级；可含**策略路由**、**适配器插件**（如不同向量后端、检索融合策略），但**不等同于 Skills**。

- **Retrieval**：检索子系统，统一查询入口，内部策略路由调度 HDL（HSI / SVS 等）。重要子系统。

- **MS**：模型服务子系统（远程兼容 API / 未来本地模型）。V0.1 以远程 API 为主。

- **系统工具集（tools）**：逻辑上归属本层；**物理代码路径**为 `src/tools/`（文件 I/O、路径规范化、与 S&G 协作的沙箱辅助等）。



### 2.4 持久层（概念：HDL）

叙事权威事实源在 **KSFS**，经 **KSS** 进入 **LKC**；**HDL（混合数据层）**由 LKC、HSI、SVS、KG 组成，是检索与一致性的数据面。

- LKC：本地知识缓存（可重建副本），是 HSI / SVS 构建的输入基准。

- HSI：SQLite 元数据索引等。重要子系统。

- SVS：语义向量库（V0.1 **ChromaDB** 持久化），与 HSI 存储分离。

- KG：预留；持久化目录独立。

**实现归属**：HDL 的**读写、索引、同步代码**属工程底座，放在 **`src/persistence/`**（与 `harness` 并列，**不**放入 `skills/`），以免与「可卸载 Skill」混淆；概念上仍称持久层/HDL。



### 2.5 支撑层

横切能力：与外界交互、安全治理、可观测性、配置、偏好等。

- **I&I**：HTTP/WebSocket、GUI 静态资源、CLI；**适配器与集成实现**（将外部协议转换为对内端口调用）；**组合根（Composition Root）**：在启动时把端口实现绑定为 Infrastructure 的具体类（或工厂）。具体约定见 §2.6。

- **S&G**：输入过滤、输出审查、工具调用沙箱、API 健康检查；**MCP 进程治理**（启动参数校验、并发/资源限额、**任务结束后的释放与回收**、与 Shell 协作的终止信号）。重要子系统。

- **Obs**：链路可视化、分级日志、Token 统计；**统一配置全应用日志**（handler、格式、级别），默认文件输出到仓库根 **`logs/`**（详见 `SPEC-V0.1.md`）。

- Config：配置加载、与环境变量合并；**人类可编辑的默认文件**建议见根目录 `config/`（见 §3）。

- PL：偏好学习（远期）；V0.1 可仅静态文件。

**生命周期分工**：**何时**启停某次 MCP 会话由 **Shell 工作流**（任务边界）驱动；**能否启、资源上限、如何杀进程、是否泄露句柄**由 **S&G** 策略与执行保障——二者协作，避免把「编排」与「治理」混为一谈。



### 2.6 I&I 与 DIP：端口、实现、装配（计划）

| 要素 | 建议位置（物理） | 说明 |
|------|------------------|------|
| **端口（Protocol / ABC）** | `src/logos/ports/`（import：`logos.ports`） | 决策层与公共库只依赖此处抽象（如 `RetrievalService`、`LLMClient`）。 |
| **基础设施实现** | `src/logos/infrastructure/` | Retrieval、MS、`tools` 的具体实现，**实现** `logos.ports` 中的契约。 |
| **HDL 实现** | `src/logos/persistence/` | KSS、HSI、SVS、KG 相关代码。 |
| **I&I 适配与装配** | `src/logos/harness/ii_layer/` | FastAPI 路由、WebSocket、静态前端托管；**应用启动**时注册实现、注入 Shell；对外部 SDK 可做**薄适配**（避免把业务逻辑堆进路由）。 |

如此满足：**依赖倒置**（向内依赖抽象）、**适配器**（Chroma/其他向量库藏在 Infrastructure 内，对 Retrieval 暴露统一端口）。



### 2.7 工厂层

用于本地部署 LLM 的离线工具链。V0.1 不实现此层任何模块。



## 3. 项目目录结构（逻辑与物理）

**原则**：`src/` 承载**随版本发布的核心程序**（决策、基础设施、持久化代码、支撑层、GUI 源码）；**不入库的个人创作与运行数据**与仓库分离；**可插拔 Skills** 与 `src` 并列；**一键启动脚本随仓库**，便于他人部署。

```text
Logos/
├── src/
│   ├── logos/                 # Python 包根（import logos；说明见 src/README.md）
│   │   ├── agent/             # 决策层（Shell、CB、PR）
│   │   ├── infrastructure/  # 基础设施层（Retrieval、MS 等）
│   │   ├── persistence/       # HDL 实现（KSS、HSI、SVS、KG）
│   │   ├── tools/             # 系统工具集
│   │   ├── harness/         # I&I、S&G、Obs、Config 加载器
│   │   │   ├── ii_layer/
│   │   │   ├── sg_layer/
│   │   │   ├── obs/
│   │   │   └── config/
│   │   └── ports/             # 端口/抽象契约（DIP）
│   └── gui/                   # Web GUI（Vite+React+TS）
├── skills/                  # 能力层：MCP Skill 包、注册元数据、渐进式披露配置
├── config/                  # 统一配置：可提交 defaults + local.example；本机私密见 local.yaml（不入库，见 config/README.md）
├── resources/               # 行业约定俗成资源：图标、空模板等（可提交 GitHub）
├── example_ksfs/            # 当前阶段示例 KSFS（可提交；KSFS 独立后可删或迁出）
├── workspace/               # 个人创作与可阅览内容（KSFS 实体根、作者直接维护的 LKC、未来 KG 产物等）— 默认不入库，见 .gitignore
├── models/                  # 说明文件可入库；tooling 权重目录见 .gitignore
├── scripts/                 # 一键启动等（.bat / .sh 等，应提交 GitHub，便于 clone 即用）
├── logs/                    # 运行时日志根目录（Obs 写入；默认不入库）
├── .index/                  # 索引类数据默认根：`.vector_index/`（SVS/Chroma）、`.high-speed_index`（HSI/SQLite）（默认不入库）
├── tests/                   # 自动化测试
├── original_docs/           # 内部开发文档（根目录；不上传 GitHub 的约定不变）
├── docs/                    # 对外文档精修版
└── README.md
```

**说明**：

- **索引类数据**：V0.1 默认仓库根 **`.index/`**；其下 **`.vector_index/`** 为 Chroma 持久化目录，**`.high-speed_index`** 为 HSI 默认 SQLite 文件；**不**与 `workspace/` 混用。均可 Config 覆盖。
- **`workspace/`**：个人小说、设定、剧本等**禁止进入公开 Git**；路径由 Config 指向此处或任意盘符。
- **`example_ksfs/`**：仅示例/跑通管线；与将来独立的 KSFS 产品边界清晰。



## 4. 一键启动与 GitHub

- **应提交仓库**：`scripts/` 下的 **`.bat` / `.sh` / PowerShell** 等启动脚本，以及 README 中的启动说明——便于他人 clone 后一键拉起前后端或 Docker。
- **可不提交或提交生成流水线**：由脚本**现场编译**的 `.exe` 若体积大、或与 CI 产物重复，可将 **构建产物**列入 `.gitignore`，但**保留**构建脚本或 `scripts/package.md` 说明来源；若 `.exe` 为小而稳定的官方启动器且团队希望「双击即用」，也可选择提交——二者取一，在 README 写清即可。

**先前易混点**：不建议忽略的是「**源码级**一键启动」；忽略的是「**无溯源的大二进制**」或本地密钥。



## 5. 其他开发要点

- GUI：**现阶段以 Web 跑通**（如 Vite + React + TS）；长期 IDE 级工作区见 `SPEC-V0.1.md`。
- ReAct 考虑 **JSON-only** 工具调用，提高成功率。
- 目录可随实现微调；**新功能默认归类**：先判断属决策 / Skills(MCP) / 基础设施 / 持久(HDL) / 支撑哪一层，再落盘路径。
- 能在确定性代码路径完成的工作，尽量不交给 LLM。



## 6. 与对外 `docs/` 的关系

内部迭代以 **`original_docs/`** 为准；对外展示可将定稿同步至 `docs/`。
