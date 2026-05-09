# 术语表

> 本表提供 Logos 项目中所有专有名词的快速索引。

#### **系统概念**

- **Logos** —— Logos：游戏叙事架构智能体（Logos: Oracle of Game Narrative Architecture）。游戏作家与游戏编剧双模式智能体，共同讨论、激发灵感、及时点拨、协助管理的叙事合伙人。
- **OM** —— 工作模式（Operating Mode）。最顶层的 AI 角色控制，按需切换游戏作家 / 游戏编剧。
  - **AM** —— 作家模式（Author Mode）。游戏作家模式，注重“创作”、文学性表达，产出独立的叙事作品。
  - **SM** —— 编剧模式（Screenwriter Mode）。游戏编剧模式，注重“设计”、上下游协作，产出游戏叙事资产。

#### 分层与模块

- **Shell** —— Agent 核心调度器（Agent Shell）。负责确定性决策（查询策略、范式路由、上下文组装），将 LLM 封装在可控边界之内。

- **基础设施层（Infrastructure Layer）** —— 全局底座：进程内 **内部 API**；含 **Retrieval**、**MS**、**系统工具集（tools）** 等；非 MCP Skills。

- **能力层（Skills）** —— 可插拔专业能力；**注册表**、**渐进式披露**；经 **MCP**（以本地 MCP Server 为主）与核心进程交互。

- **KSFS** —— 知识源文件系统（Knowledge Source File System）。负责存储与管理叙事资产。未来会作为独立的系统进行开发，拥有权限分级与提案审核机制。
  - **KSS**  —— 知识源服务（Knowledge Source Service）。KSFS 暴露的接口，KSFS 独立后会改为 API。

- **HDL** —— 混合数据层（Hybrid Data Layer）。
  - **LKC** —— 本地知识缓存（Local Knowledge Cache）。Logos 侧从 KSS 获取的规范化副本，是 HSI、SVS、KG 构建的输入；**叙事权威事实源在 KSFS**。
  - **HSI** —— 高速索引（High-Speed Index）。基于 SQLite 的实体元数据索引表，缓存文件路径、摘要和路径语义链。
  - **SVS** —— 语义向量库（Semantic Vector Store）。存储 Markdown 内容块的向量嵌入，负责语义相似检索（V0.1 为 ChromaDB）。
  - **KG** —— 知识图谱（Knowledge Graph）。存储从 KSFS 中提炼的实体间确定性关系，负责关系推理和叙事一致性守护。

- **Retrieval** —— 检索子系统。对外（对决策层/端口）暴露统一检索接口；内部策略路由调度 HDL；属**基础设施层**。

- **PR** —— 范式路由器（Paradigm Router）。根据任务复杂度自动选择 ReAct（默认）、Plan 等范式。
- **CB** —— 上下文构建器（Context Builder）。负责对话历史管理、Prompt 模板选择、上下文预算分配和内容格式化。
- **Obs** —— 可观测性子系统（Observability Subsystem）。提供思维链录制、分级日志和成本看板；**统一配置全应用日志**，默认文件输出到 **`logs/`**。
- **MS** —— 模型服务子系统（Model Serving Subsystem）。提供 LLM 调用封装（远程兼容 API / 未来本地模型）；属**基础设施层**。
- **PL** —— 偏好学习器（Preference Learner）。负责用户偏好治理，为 CB 提供个性化指导。

#### 通用术语

- **I&I** —— 接口与集成层（Interface & Integration Layer）。HTTP/GUI/CLI、**适配器与依赖装配**（组合根），见 `ARCHITECTURE.md` §2.6。
- **S&G** —— 安全与治理层（Security & Governance Layer）。输入输出治理、沙箱、健康检查；**含 MCP 进程治理与任务结束后的资源回收**（与 Shell 任务边界协作）。
- **Config** —— 配置与状态管理（Configuration & State Management）。根 `config/` 与加载器协同。
