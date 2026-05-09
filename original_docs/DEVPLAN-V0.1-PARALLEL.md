# Logos V0.1 — 并行开发执行计划（多 Agent / 多分支）

> 目的：把 V0.1 拆成**可并行**的工作流，减少文件冲突；供 Cursor 多 Agent 或多人分工时对齐**契约**与**目录**。总规格仍以 `SPEC-V0.1.md` 为准，冲突时以 SPEC 为准。

---

## 0. 本轮已定案的路径与约定

| 项 | 定案 |
|----|------|
| 前端 | **非 monorepo**；前端工程放在 **`src/gui/`**（如 Vite + React + TS）。 |
| 索引根 | 仓库根 **`.index/`**（默认；内建 **`.vector_index/`**=SVS/Chroma、**`.high-speed_index`**=HSI/SQLite；可由 Config 覆盖）。 |
| 日志 | 仓库根 **`logs/`**；**Obs 子系统统一配置根 logger**，各层只拿子 logger（`logging.getLogger("logos.retrieval")` 等），handler 写入 `logs/`（**滚动策略为裁量项**，见 §7）。 |
| 嵌入权重 | 已就位：`models/tooling/embeddings/bge-small-zh-v1.5/`（仍由 Config 指定，禁止写死路径字符串散落业务代码）。 |

---

## 1. 「嵌入驱动的具体抽象名」指什么

指在代码里**接口（Protocol / ABC）的模块路径与类名**，例如：

- `src/logos/ports/embedding.py` 中定义 **`TextEmbedder`**（或 `IEmbedder`）协议：方法 `embed(texts: list[str]) -> list[list[float]]` 等。
- `src/logos/infrastructure/embeddings/bge_small_zh.py`（Stream 3）中 **`BgeSmallZhEmbedder`** 实现该协议。

「抽象名」= 团队在 PR/Agent 提示词里引用的**稳定符号名**，便于替换实现时只改编译/注册表，而不改 Retrieval 主逻辑。**不是**要求你现在锁死唯一名字；V0.1 建议在 **`重要子系统开发文档/SVS-Chroma.md`** 里登记最终选用的类名与 `config/defaults.yaml` 中的键名（见 §4）。

---

## 2. 并行前的「契约文件」（建议先合并到主分支或锁定分支）

以下文件建议 **Stream 0** 一次合并，其他 Agent **只增量修改、避免大范围重命名**：

1. **`src/logos/ports/`**（import 路径 **`logos.ports`**，与 `src/README.md` 说明一致）  
   - `TextEmbedder`（嵌入）  
   - `SemanticStore`（Chroma 增删查）  
   - `MetadataIndex`（HSI 抽象）  
   - `KnowledgeSource`（KSS：枚举文档、读正文）  
   - `RetrievalService`（融合查询，`Citation` DTO）  
   - `LLMClient`（MS）  
   - `AppSettings`（只读配置快照，由 harness 构建）

2. **`config/defaults.yaml`**（**V0.1 已锁定键名**，多 Agent 以仓库内文件为准；变更走 PR 并标破坏性）：

```yaml
paths:
  workspace_root: "./workspace"
  example_ksfs_root: "./example_ksfs"
  index_root: "./.index"
  logs_root: "./logs"
  hsi_sqlite_path: "./.index/.high-speed_index"
embeddings:
  provider: "bge_small_zh"
  model_path: "models/tooling/embeddings/bge-small-zh-v1.5"
chroma:
  persist_directory: "./.index/.vector_index"
  collection: "lkc_chunks_v0"
```

3. **HTTP API 契约**（`重要子系统开发文档/API-V0.1.md`）：  
   - `POST /api/v1/chat`：**SSE**（`text/event-stream`），事件 `delta` / `citations` / `done` / `error`  
   - `GET /api/v1/health`  
   - （可选）`POST /api/v1/index/rebuild`  

4. **工具 JSON Schema**（`src/logos/agent/tools/schema/` 或单文件 `tool_schemas.json`）：`retrieve`、`read_lkc`、`write_draft` 的入参出参。

---

## 3. 工作流划分（推荐 7 路 + 依赖）

> **冲突控制**：各 Stream 默认「拥有」下表目录；跨目录修改需先 Rebase 或口头约定。`src/logos/ports/` 与 `config/defaults.yaml` 由 **Stream 0** 建骨架，其他流 **提小 PR 改契约**。

| ID | 名称 | 主要职责 | 拥有目录 / 文件 |
|----|------|----------|-----------------|
| **0** | 契约与仓库骨架 | `pyproject.toml`、包 **`logos`**（`src/logos/`，含 **`logos.ports`** 等契约）、`tests/conftest.py`、`example_ksfs/` 最小样例、`src/gui/.gitkeep` | `src/logos/`、`pyproject.toml`、`README`、`example_ksfs/` |
| **1** | Config + Obs + 日志 | YAML 合并、环境变量覆盖、`logs/` 初始化、Obs 封装、结构化日志格式 | `src/logos/harness/config/`、`src/logos/harness/obs/`、`config/*.yaml` |
| **2** | 持久层 HDL | KSS 扫描、LKC 同步、HSI SQLite schema、增量哈希、mtime | `src/logos/persistence/`（Chroma SDK 调用可放 3） |
| **3** | 基础设施：嵌入 + Chroma + Retrieval | `TextEmbedder` 实现、`SemanticStore` Chroma 适配、`RetrievalService` 调 HSI+SVS | `src/logos/infrastructure/`（`embeddings/`、`vector/`、`retrieval/`） |
| **4** | 决策层 Agent | Shell、ReAct 循环、JSON tool 解析、CB/PR 最小、工具注册 | `src/logos/agent/` |
| **5** | I&I HTTP | FastAPI（或同类）应用、CORS、挂载静态 `src/gui/dist`、依赖注入组装各端口 | `src/logos/harness/ii_layer/` |
| **6** | GUI | `src/gui/` 内 Vite 工程、对话页、模式切换、引用展示；仅调 Stream 5 的 API | `src/gui/**` |
| **7** | S&G + MCP Skill | 路径沙箱、工具白名单、输出过滤；示例 stdio MCP；与 Shell 的调用边界 | `src/logos/harness/sg_layer/`、`skills/` |

### 3.1 依赖顺序（DAG）

```
0 → 1,2,3（可 2 与 3 并行；3 的单元测试可先 mock HSI）
1 → 5,4（配置与日志就绪）
2+3 → 4（集成测试：真检索）
4+5 → 6（UI 对接真实或 mock API）
7 与 1～4 并行起步；与 4 集成时合并「工具沙箱」回调
```

### 3.2 各 Stream 交付物（Definition of Done）

- **0**：`pytest` 通过；`import logos`、`from logos.ports import TextEmbedder` 可解析；`example_ksfs/` 有最小 Markdown 样例。
- **1**：启动时创建 `logs/`；全库日志经 Obs 配置；`local.yaml` 覆盖验证用例。
- **2**：对 `example_ksfs/` 跑一次同步 → LKC；HSI 可查询路径；哈希变更检测单测。
- **3**：Chroma 数据落在 `.index/.vector_index/`；HSI 为 `.index/.high-speed_index`；嵌入用配置路径；Retrieval 返回统一列表 DTO（含 `path`、`snippet`、`score`，与 SSE `citations.items` 对齐）。
- **4**：一轮 ReAct：模型 fake 时仍可跑通工具调用链；JSON 非法时错误分支有日志。
- **5**：`curl` health；`chat` **仅 SSE**（与 `API-V0.1.md` 一致）；集成测试可用 `httpx`/`aiohttp` 读 SSE 流。
- **6**：本地 `npm run dev` 代理到后端；最小可用对话 UI；**`EventSource`/`fetch`+ReadableStream** 消费 SSE（见 `API-V0.1.md`）。
- **7**：`write_draft` 无法写出 `workspace` 外；MCP 子进程在测试里起停无僵尸（尽力）。

---

## 4. 多 Cursor Agent 实操建议

1. **先跑 Stream 0**，合并后再开并行 Agent。  
2. 每个 Agent 的提示词首行附上：「仅修改 §3 表中本人拥有目录；改契约先提 PR」。  
3. **API-V0.1.md** 与 **tool_schemas** 变更视为「破坏性」：通知所有活跃分支。  
4. 每日合并用 **rebase + 小步**；`src/gui/package-lock.json` 仅 Stream 6  touch。  
5. CI（后续加）：`ruff`/`pytest` + `npm run build`（gui）。

---

## 5. 与 SPEC §11 的对应关系

| SPEC 阶段 | 本计划 Stream |
|-----------|----------------|
| 基础骨架 | 0, 1 |
| KSFS+KSS+LKC | 2 |
| HSI+SVS+增量 | 2（HSI）+ 3（SVS+嵌入） |
| Retrieval | 3 |
| Agent 核心 | 4 |
| S&G 最小 | 7（与 4 对接） |
| Web GUI | 5 + 6 |
| MCP | 7 |
| 收尾 | 全员 |

---

## 6. 嵌入实现登记（占位，实现后填）

| 字段 | 值 |
|------|-----|
| Protocol 名 | `TextEmbedder`（建议，可改为团队偏好） |
| V0.1 实现类 | `BgeSmallZhEmbedder` |
| 配置节 | `embeddings.provider` / `embeddings.model_path` |
| 权重已就绪 | 是（`models/tooling/embeddings/bge-small-zh-v1.5/`） |

---

## 7. 开工检查表（V0.1 无阻塞待定后的执行顺序）

**状态**：技术路径已全部定案；下列顺序用于单人与多 Agent 开工对齐。

| 状态 | 步 | 动作 | 完成标准 |
|------|----|------|----------|
| ✅ | 0 | **Stream 0**：`pyproject.toml`、包 **`logos`**（`src/logos/ports/` 契约）、`tests/`、`example_ksfs/` 最小样例、`src/gui/` 占位 | `pytest` 通过；`import logos` |
| ⬜ | 1 | **Stream 1**：合并 YAML、`local.yaml` 逻辑、Obs→`logs/` | 启动即写 `logs/*.log`（或单文件） |
| ⬜ | 2 | **Stream 2**：KSS + LKC 同步 + HSI 写入 `.index/.high-speed_index` | 样例 KSFS 可索引；单测覆盖哈希 |
| ⬜ | 3 | **Stream 3**：`TextEmbedder` + Chroma→`.index/.vector_index` + Retrieval | Retrieval DTO 与 SSE `citations.items` 字段一致 |
| ⬜ | 4 | **Stream 4**：Shell + ReAct + JSON tools | fake LLM 下工具链可跑 |
| ⬜ | 5 | **Stream 5**：FastAPI + SSE `chat` + health + 静态挂载 `gui/dist` | `curl` health；SSE 符合 `API-V0.1.md` |
| ⬜ | 6 | **Stream 6**：`src/gui/` Vite 工程 + EventSource 消费 SSE | 浏览器可见流式正文与引用 |
| ⬜ | 7 | **Stream 7**：S&G 沙箱 + 示例 MCP skill | `write_draft` 越权失败；MCP 可测起停 |
| ⬜ | 8 | **收尾**：README、`docs/` 同步、`scripts/` 一键启动 | 与 SPEC 验收判据一致 |

**裁量项（不列入上表门禁）**：日志滚动；chunk 参数；`/index/rebuild`；`/chat/debug`。

---

## 8. 多 Agent 开工指引（双显示器，推荐）

**原则**：契约已冻结在 **Stream 0**；并行时**每人只改自己 Stream 的目录**，改 `logos.ports` 或 `API-V0.1.md` / `config/defaults.yaml` 须先停其它 Agent、合并后再继续。

### 8.1 屏幕分工

| 显示器 | 内容 |
|--------|------|
| **主屏** | Cursor 编辑器 + 终端（`pytest` / 合并分支）；主开发者合并 PR。 |
| **副屏** | **Agents Window**（`Ctrl+Shift+P` → `Agents Window`）开 2～3 个会话；或浏览器跑 `localhost` + 文档 `API-V0.1.md`。 |

### 8.2 当前阶段（Stream 1 可单 Agent）

Stream 1 与后续流耦合少，可**只开一个 Agent**，提示词示例：

> 实现 Logos **Stream 1**：在 `src/logos/harness/config/` 实现 `defaults.yaml` + `local.yaml` 合并与可选环境变量覆盖；在 `src/logos/harness/obs/` 统一配置 `logging`，将文件 handler 指向 `config/defaults.yaml` 的 `paths.logs_root`（默认 `./logs/`）。**不要**改 `logos.ports` 里 Protocol 的方法签名；若需改 `AppSettings` 字段，先说明破坏性。参考 `config/README.md` 与 `SPEC-V0.1.md`。

### 8.3 下一阶段并行（Stream 2 + 3）

当 Stream 1 合并后，在副屏开 **两个** Agent：

1. **Agent-A（Stream 2）**：仅 `src/logos/persistence/`；KSS、LKC 同步、HSI。  
2. **Agent-B（Stream 3）**：仅 `src/logos/infrastructure/`；`TextEmbedder`、`SemanticStore`、Retrieval。  

易冲突时：对其中一方使用 **`/worktree`**，主屏负责合并。

### 8.4 每会话开头粘贴（防越权）

```
工作区：g:\GithubProject\Logos
你只允许修改：<填 DEVPLAN §3 表中你的目录>
禁止修改：logos/ports（除非我明确说改契约）、API-V0.1.md、defaults.yaml（除非走破坏性变更流程）
合并前在仓库根运行：pytest
```

---

*文档版本：V0.1 已定案可开工；§7 步骤 0 已完成；§8 为多 Agent 指引。*
