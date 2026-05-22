# Logos — GUI 与 Electron 壳层开发（权威指南）

> **地位**：**本仓库内一切与「Web GUI（`src/gui`）+ 未来/现行 Electron 桌面壳」相关的实现与评审**，以本文与 **`API-V0.2.md`**、**`SPEC-DISPLAY-AND-LOGGING-V0.1.md`**、**`DECISIONS.md` §10、§13、§14**、**`任务与Skill驱动GUI定案.md`** 为权威组合：  
> - **HTTP/SSE 形状与事件名** → 以 **`API-V0.2.md`** 为准；  
> - **展示档位、日志 profile、`bootstrap` 语义** → 以 **SPEC** 与 **`API-V0.2.md`** 为准；  
> - **产品形态（Electron 壳、任务/Skill 驱动、标签式多任务）** → 以 **`DECISIONS.md` §10、§13、§14** 与 **`任务与Skill驱动GUI定案.md`** 为准；  
> - **第四阶段 G 轨（Router / 档 B / 多标签）** → 以 **本文 §12** 为准（G1～G4 已实施部分**保留**）；  
> - **第五阶段 T 轨（技能面板 / 单任务向导）** → 以 **本文 §11** 与 **`../第五阶段开发计划.md`** 为准；  
> - **进程模型、安全边界、目录约定、Cursor 协作** → **以本文 §2～§8** 为准。  
> **更新**：随 Electron 落地与 CI 策略迭代；**第三阶段 P0** 已结案（见 **`已完成/第三阶段开发计划.md`**）；**第四阶段**主排期已定案（见 **`../已完成/第四阶段开发计划.md`**）；Electron **安装/签名/自动更新** 路线图见 **`产品化文档.md`**。

---

## 1. 当前仓库事实（写作基线）

| 要素 | 现状 |
|------|------|
| **Web GUI** | `src/gui/`：Vite + React + TypeScript；开发服务器默认端口 **5173**。 |
| **开发态 API** | `vite.config.ts` 将 **`/api` 代理**到 `VITE_DEV_API_PROXY_TARGET`（默认 `http://127.0.0.1:8000`）。 |
| **HTTP 客户端** | `src/gui/src/api/`：`apiBase.ts`（`initApiBase` / `apiUrl`，与 Electron `getApiBase` 对齐）、`health.ts`、`bootstrap.ts`、`sseChat.ts`、`developer.ts`；类型见 `src/gui/src/types/`。 |
| **Electron** | **物理路径已定案：`src/electron/`**（Main、preload、壳层专用 `package.json` / tsconfig 等）；与 `src/gui`、`src/logos` 并列，见 §6.1。**开发态启动**：先 `cd src/gui && npm run dev`，再 `cd src/electron && npm install && npm run electron:dev`（Main 先展示内嵌加载页，再轮询 **`GET /api/v1/health`** 就绪后 `loadURL` 至默认 `http://127.0.0.1:5173/`；若 5173 未监听则 Main 内警告对话框 + stderr 提示）。**Main 默认**在仓库根 `spawn` **`scripts/run_backend_stub.py`**（`LOGOS_REPO_ROOT`、优先 `.venv` 下 Python，与 `README` 一致）；若后端已在外部启动，设 **`LOGOS_ELECTRON_SKIP_BACKEND=1`**（`scripts/start_logos.*` 已设；此时**跳过**健康门）。可选覆盖：`LOGOS_GUI_DEV_HOST`、`LOGOS_GUI_DEV_PORT`、`LOGOS_PYTHON`、`LOGOS_BACKEND_USE_UV`、`LOGOS_ELECTRON_BACKEND_STDIO`、`LOGOS_BACKEND_HEALTH_URL` 或 `LOGOS_BACKEND_API_ORIGIN`、`LOGOS_ELECTRON_BACKEND_READY_TIMEOUT_MS`（默认 120000，**0** 表示仅探测一次）、`LOGOS_ELECTRON_BACKEND_HEALTH_POLL_MS`（默认 400）。**打包态**：`npm run package:win` 产出 Windows portable，`loadFile` 加载随包 `gui`；`preload` 暴露 **`getApiBase`**（与 health 对齐的 API origin；开发态 Electron 返回空串以继续走 Vite 代理）与 **`onBackendStatus`**；生产默认门控 **DevTools**（`LOGOS_ELECTRON_ALLOW_DEVTOOLS=1` 可开）。若安装 Electron 时出现 **`read ECONNRESET`**，在 `src/electron` 使用 **`npm run install:with-mirror`**（见 **`README.md`**）。**退出清理**：`before-quit` 与 `will-quit` 均会尝试终止后端；非 macOS 在 **`window-all-closed`** 于 `app.quit()` 前再终止一次；Windows 使用 **`taskkill /PID <pid> /T /F`** 结束进程树，Unix 对子进程发 **`SIGTERM`**（重复调用容错）。 |

---

## 2. Electron 架构定案

### 2.1 三进程角色

```text
┌─────────────────────────────────────────────────────────┐
│  Electron Main（Node，高权限）                            │
│  · 创建 BrowserWindow                                    │
│  ·  spawn / 监护 Python 后端（FastAPI / run_backend_stub） │
│  ·  健康检查、重启策略、退出时 SIGTERM 子进程              │
│  ·  仅通过 preload 暴露窄 IPC（见 §3）                    │
└──────────────────────────┬──────────────────────────────┘
                           │ preload（contextBridge）
┌──────────────────────────▼──────────────────────────────┐
│  Renderer（Chromium + 与现有一致的 React 应用）           │
│  ·  仅使用 fetch/EventSource 访问同源或配置的 API_BASE     │
│  ·  禁止在 renderer 直接 require('child_process') 等     │
└─────────────────────────────────────────────────────────┘
```

### 2.2 与 Python 后端的关系

- **单一事实源**：业务 API 仍为 **FastAPI**（`logos.harness.ii_layer`）；Electron **不**在 Main 里重写 HTTP 路由。  
- **托管责任**：Main 负责子进程**工作目录**、**环境变量**（如 `LOGOS_REPO_ROOT`）、**端口**（或从配置读取），与 **`scripts/run_backend_stub.py`** 文档对齐。  
- **GUI 加载方式**：  
  - **开发**：可 `loadURL('http://127.0.0.1:5173')`，与当前 Vite 一致；后端或可由 Main 拉起，或由开发者手动起（文档须写清两种模式）。  
  - **生产**：`file://` 加载 Vite `build` 产物，或 `loadURL` 至内嵌静态服务（二选一定案后写入本文修订记录）；**同一套 React 代码**应兼容两种加载基址（见 §4）。

### 2.3 设计要点清单（实施前自检）

| 要点 | 说明 |
|------|------|
| **contextIsolation: true** | 默认开启；与 `nodeIntegration: false` 组合使用。 |
| **preload 最小面** | 只暴露白名单 API（例如 `getApiBase()`、`onBackendStatus(cb)`）；禁止通配 `ipcRenderer.invoke` 转发任意字符串命令。 |
| **禁用远程模块** | 不使用 `remote`；需能力时在 Main 实现再通过 IPC 返回结果。 |
| **CSP** | 生产包对 `script-src`、`connect-src` 收紧；`connect-src` 须包含后端 origin（若非同源则显式列出）。 |
| **单实例** | Windows 上建议 `requestSingleInstanceLock`，避免多开多套后端与端口冲突。 |
| **后端崩溃** | 有限次指数退避重启 + UI 状态机（「重连中」「已放弃」）；日志落盘或写入用户数据目录。 |
| **退出** | `before-quit` / `window-all-closed` 路径上确保 Python 子进程被 kill；避免僵尸进程。 |
| **DevTools** | 开发默认可开；生产构建通过环境变量或 `app.isPackaged` 门控。 |

---

## 3. 安全与 IPC 边界（必须遵守）

1. **不信任 Renderer 传参去拼 shell 命令**；端口、可执行文件路径由 Main 从**固定配置键 + 校验**读取。  
2. **不在 preload 中暴露**原始 `fs`、`child_process`。  
3. **敏感令牌**（若将来有）：仅存 Main 或系统密钥链，不经由 `localStorage` 明文给 Renderer。  
4. **深度链接 / 打开外部 URL**：使用 `shell.openExternal` 且在 Main 中做 allowlist（若产品需要）。

---

## 4. API 基址、代理与 `bootstrap`

| 场景 | 约定 |
|------|------|
| **纯浏览器开发** | 依赖 Vite `proxy`，前端请求 **`/api/v1/...`** 相对路径即可。 |
| **Electron + dev** | 若 Renderer 仍连 `5173`，可与现网一致用相对路径 + 代理；若 Renderer 直连后端，则须统一 **`import.meta.env.VITE_*` 或壳注入的 `window.__LOGOS_API_BASE__`**（定案后只保留一种文档化来源）。 |
| **Electron + 打包** | 必须使用**绝对 API base**（由 Main 注入或构建时写入），与 **`GET /api/v1/bootstrap`** 返回的 `ui` / `obs` 等配置一起作为首屏真相来源。 |

**原则**：禁止在业务组件里散落硬编码 `http://127.0.0.1:8000`；集中在一个 `apiClient` 或等价模块。

---

## 5. 与展示 / SSE 档位（SPEC）的衔接

- 会话请求体中的 **`presentation`**、SSE 分事件档位等，严格按 **`SPEC-DISPLAY-AND-LOGGING-V0.1.md`** 与 **`API-V0.2.md`** 实现；GUI 侧解析逻辑集中在 **`sseChat.ts`** 与类型定义，避免在多个组件复制解析状态机。  
- **`bootstrap`** 仅作配置与能力发现；缺后端时的降级 UI 可以有，但**不得**长期用「写死默认值」替代服务端契约（见 **`API终极文档.md`**）。

---

## 6. 前端代码与目录约定

| 路径 | 用途 |
|------|------|
| `src/gui/src/api/` | HTTP / SSE 封装；变更若影响契约须走 §7。 |
| `src/gui/src/types/` | 与后端 JSON 对齐的 TS 类型。 |
| `src/gui/src/components/` | 页面级与可复用 UI；避免在组件内直接改契约解析。 |
| **`src/electron/`** | **Electron 壳层唯一根目录**：Main、preload、壳层构建与启动脚本；**禁止**把 Main/preload 逻辑塞进 `src/gui/src/`（避免与 Vite 前端 bundle 混淆）。 |

### 6.1 为何采用 `src/electron/`（定案理由）

- **与现有布局一致**：`src/logos`（Python）、`src/gui`（Vite/React）已在 `src/` 下；壳层作为第三种「可发布源码」放在同级，**仓库心智单一**（打开 `src/` 即见全貌）。  
- **Cursor / CI 友好**：规则与脚本可用稳定前缀 `src/electron/**`，不必与仓库根上大量杂项抢命名。  
- **和 Python 包解耦**：`logos` 仍只从 `src/logos` 安装；Electron 是 **Node 侧应用**，独立 `package.json` 放在 `src/electron` 不会污染 Python 打包语义。

**备选（未选）**：仓库根目录 **`electron/`** 也很常见（许多上游模板默认如此），与 `pyproject.toml` 并列也清晰；若团队更习惯「根上即桌面应用」，可再讨论迁目录，但**当前定案为 `src/electron/`**，避免 PR 无约定可引用。

### 6.2 设置页、缓存页与 Obs O4

| 主题 | 约定 |
|------|------|
| **路由（已定案）** | **`/settings`** 独立设置页（自 `SettingsDrawer` 迁出）；**`/cache`** 归档缓存管理；入口与验收见 **§12**。 |
| **`/cache` 入口** | **仅** 设置页按钮 **「已归档会话」**；**不在顶栏**（`DECISIONS.md` §13.8）。 |
| **Obs O4 / 日志根** | 是否展示 **解析后的 `paths.logs_root` 绝对路径** 完全由配置 **`obs.show_log_root_in_gui`** 决定，**默认 false**；为 true 时 **`GET /api/v1/bootstrap`** 携带 **`obs_show_log_root_in_gui`** 与 **`obs_logs_root`**，在设置内展示并支持「复制日志根路径」。 |
| **与 G1 分工** | 「打开 maint 目录」「复制调试信息」等仍属壳层/通用诊断；**会话 JSON 缓存目录**默认不向用户暴露路径。 |
| **视觉定稿** | 功能步完成后，由负责人执行 **§12 步 M-UI** 手动调校（Agent 仅做占位样式）。 |

---

## 7. 契约变更纪律（与 Cursor 强相关）

凡改动 **`/api/v1`** 路由、SSE **`event:`** 名、JSON 字段或顺序：

1. 遵守 **`.cursor/rules/logos-api-contract.mdc`** 中的 glob 与同步顺序。  
2. 同一逻辑变更内更新：**`api_v1.py`**（及 **`deps.py`**）→ **`API-V0.2.md`** → **`tests/test_stream5_api.py`** → 前端 **`sseChat.ts` / `bootstrap.ts` / `developer.ts`** 与相关 **`types/`**。  
3. 提交说明中**单独一行**：`契约：无变更` 或 `契约：已更新 API-V0.2（摘要：……）`。  
4. 启用 **`git config core.hooksPath .githooks`**，以便 `commit-msg` / `pre-commit` 脚本生效（详见 **`API终极文档.md`** §4.1）。

**在 Cursor 中的实操**：打开契约相关文件时，IDE 应加载上述规则；若分多 Agent 会话，**契约改动必须单会话串行**，避免两个分支同时改 `api_v1` 与 `sseChat.ts`。

---

## 8. Cursor 设计模式与推荐工作法

以下模式用于 **提高 GUI/Electron PR 的可审查性与少返工**，不是工具强制功能。

### 8.1 单会话 = 单意图 = 单分支

- **每个 Cursor 会话**绑定：**一条 git 分支** + **一个清晰目标**（例如「仅 Electron Main 拉起后端」或「仅 SSE 断线重连 UI」）。  
- 在会话首条消息粘贴 **`../已完成/第四阶段开发计划.md`**（或 **`../已完成/第三阶段开发计划.md`** 中仅涉壳层/P0 的对照小节）或本文件中的对应小节，并写明：**禁止修改** `src/logos/persistence/` 等无关目录（除非任务本身需要）。

### 8.2 契约轨与界面轨分离

| 轨 | 典型路径 | 说明 |
|----|-----------|------|
| **契约轨** | `api_v1.py`、`API-V0.2.md`、`test_stream5_api.py`、`sseChat.ts`、`bootstrap.ts` | 一次 PR 内闭环；优先合入以降低 GUI 分叉。 |
| **界面轨** | `ChatPage.tsx`、CSS、纯展示状态 | 可与契约轨并行，但**若依赖新字段**须等契约轨合并或 rebase 后再接。 |

### 8.3 使用 Project Rules 而非口头重复

- 仓库已含 **`.cursor/rules/logos-api-contract.mdc`**；GUI 专属规则若增多（例如「Electron Main 禁止事项」），可另增 **`.cursor/rules/logos-electron-shell.mdc`** 并收窄 `globs`，避免全局噪音。  
- 撰写新规则时遵循仓库内 **`create-rule` skill**（若你本地已安装该 skill）的结构化要求。

### 8.4 Agent 提示词模板（可复制）

```text
【Logos GUI 子任务】
权威：original_docs/重要子系统开发文档/GUI开发文档.md；HTTP 形状以 API-V0.2.md 为准。
范围：仅 `src/gui/...` 或仅 `src/electron/...`（二选一在任务里写明）。
禁止：改动 api_v1.py / API-V0.2.md（除非本任务 explicitly 为契约变更）。
验收：npm run build 无错；若有契约相关文件变更则必须含 契约： 行并过 githooks。
```

### 8.5 大型 UI 重构

- 先加 ** characterization 测试**（Playwright 或组件测）再大范围搬文件；避免「纯重构」PR 与功能 PR 混在同一 diff。

---

## 9. 测试与 CI 期望（第三阶段 P0 已对齐；扩展见第四阶段）

| 层级 | 目标 |
|------|------|
| **单元 / 契约** | TS 侧对 `bootstrap` 解析、`sseChat` 事件归约做纯函数测（可选，按投入递增）。 |
| **E2E** | 至少一条：**应用启动 → `/api/v1/health` 或 bootstrap 成功路径**；Electron 合并后改为「起壳 → 后端就绪 → 同上」。 |
| **手动清单** | 保留一份短清单在 **`README.md`** 或本文附录：首次安装、端口占用、日志路径。 |

---

## 10. 与阶段计划的对应关系

| 阶段与内容 | 本文锚点 |
|----------------|----------|
| **第三阶段 P0**（已结案）Electron HA | §2、§3、§4、§9 |
| **第三阶段 P0** 打包 | §2.2、§9 |
| **第四阶段 G 轨**（Router / 档 B / 多标签 SSE） | **§12**（G1～G4 已实施；G5/M-UI/G6 **冻结顺延**，见 §11.3） |
| **第五阶段 T 轨**（任务 / Skill 驱动） | **§11**、**`任务与Skill驱动GUI定案.md`**、**`../第五阶段开发计划.md`** |
| **第四阶段** P1 契约 / A7 / MCP | 后端为主；GUI 在 T3 暴露 `bootstrap.skills` 等 |

---

## 11. 第五阶段：任务与 Skill 驱动（产品 IA，2026-05-16 定案）

> **权威全文**：**`任务与Skill驱动GUI定案.md`**（必读）。  
> **DECISIONS 摘要**：**`DECISIONS.md` §14**。  
> **本节角色**：GUI 实现者速查；**不重复**定案全文。

### 11.1 产品主轴（一句话）

**用户先选 Skill，再输入，再执行；一个任务 = 档 B 一个会话 JSON；长对话只是名为 `chat_inspire` 的 Skill。**

### 11.2 目标路由（相对现行代码）

| 路由 | 目标态 | 现行（第四阶段） |
|------|--------|------------------|
| **`/`** | **技能面板** | 重定向至 `/chat/...` → **T1 改** |
| **`/task/:id`** | 单任务向导（选步/输入步/执行步） | 无 → **T1 增** |
| **`/chat/:id`** | 仅 `chat_inspire` 或过渡兼容 | 默认工作区 → **T2 降级** |
| **`/settings`**、**`/cache`** | 不变 | 已有 |

### 11.3 第四阶段成果：保留 / 冻结 / 废弃

| 类别 | 项 |
|------|-----|
| **保留** | Electron 壳、`ConversationProvider`、标签条、档 B IPC、SSE 客户端、`/settings`、健康/bootstrap |
| **冻结**（T1 前少投入） | G5 全功能 `/cache`、M-UI 以 Chat 为中心的定稿、多标签边缘体验 |
| **废弃（产品层）** | 冷启动空白全工具 Chat；对话页堆叠「运行模式 / 展示档位」（已迁设置页） |

### 11.4 第五阶段步序（实施）

**唯一排期**：**`../第五阶段开发计划.md`（F5-00～F5-10）**；**PR 细节**：**`PR开发文档.md`**。旧 T0～T3 **废止**。

```text
F5-04  技能面板 + 路由 /
  └─► F5-05  Task 向导 + lint_zh
        └─► F5-07  chat_inspire
              └─► F5-08  bootstrap.skills + react 示例
```

| 步 | 界面轨 | 后端/PR |
|----|--------|---------|
| **F5-04～05** | `SkillPanelPage`、`TaskPage` | F5-02 契约、F5-03 PR、F5-01 manifest |
| **F5-07～08** | 多轮对话、动态面板 | `dialogue` / `react` scoped |

### 11.6 技能说明 UI（manifest 驱动，2026-05-21）

| 项 | 定案 |
|----|------|
| **组件** | `src/gui/src/components/SkillInstructions.tsx`（标题固定 **「技能说明」**，`data-testid="skill-instructions"`） |
| **数据来源** | manifest 可选字段 **`ui_instructions`** → `GET /api/v1/bootstrap` → `skills[].ui_instructions`；启动时 `hydrateSkillRegistry`（`src/gui/src/skills/registry.ts`） |
| **展示位置** | **`TaskPage`** 输入区上方；**`ChatPage`** 消息列表上方（含 `chat_inspire`） |
| **写死在 GUI 的通用文案** | 输入标签「输入」、按钮 **「发送」** / **「再来一次」**、placeholder「输入内容…」、空状态与 SSE 排队提示；**步骤条**「② 输入 · ③ 执行 · 完成」 |
| **面板卡片** | 仍用 `description`（短摘要）；与 `ui_instructions`（长说明）分工 |
| **回退** | bootstrap 不可用时 `catalog.ts` 的 `FALLBACK_PANEL_SKILLS` 须与 manifest **同步** `ui_instructions`（应急，非主路径） |
| **新增 Skill** | 只改 `skills/manifests/<id>.yaml` + `resources/prompts/skills/<id>.md`；详见 **`skills/manifests/README.md`** |

**已废弃**：按 skill 分散维护的 `taskUi.ts` 式 GUI 文案。

### 11.5 Cursor 起手模板（第五阶段）

```text
【Logos GUI · 第五阶段 Tx】
权威：任务与Skill驱动GUI定案.md §x、GUI开发文档.md §11、DECISIONS.md §14。
范围：仅 src/gui / src/electron（或契约轨另开 PR）。
禁止：默认首页 Chat、无 skill_id 全工具 Agent、扩大 G5 范围（除非任务写明）。
验收：npm run build；契约：无变更 或 已更新 API-V0.2（…）。
```

---

## 12. 第四阶段 GUI 实施计划（G 轨，分步推进与验收）

> **状态（2026-05-21）**：**G1～G4 已实施**；**G5 / M-UI** 纳入 **第六阶段**（**`../第六阶段开发计划.md`** F6-04～F6-06）；§12.7～12.8 仍为实施细则。  
> **定案来源**：**`DECISIONS.md` §13**（标签页、档 B 缓存、`/cache`、配置键等）。  
> **开工前**：`git checkout -b gui/<步编号>-<简述>`；每步 **一条 Cursor 会话 / 一个 PR**（§8.1）。  
> **轨别**：默认 **界面轨**（仅 `src/gui`、`src/electron`）；涉及 `bootstrap` 新增 `ui.*` 字段时走 **契约轨**（§7）。

### 12.0 推荐目录增量（随步创建）

```text
src/gui/src/
├── routes/              # 步 G1：路由表与布局壳
├── pages/               # ChatPage、SettingsPage、CachePage
├── conversation/        # 步 G3+：store、types、persist 适配
├── components/          # TabBar、StartupCacheBanner 等
└── api/                 # 既有；步 G2 若扩 bootstrap 类型
```

Electron（步 G3 起）：

```text
src/electron/src/
└── main.ts / preload.ts   # 窄 IPC：list/read/write/size conversations
```

### 12.1 总览与依赖

```text
G0 准备
 └─► G1 Router + 设置/缓存占位  ✅
      └─► G2 bootstrap ui 段  ✅
           └─► G3 Electron 缓存 IPC  ✅
                └─► G4 多标签 + 后台 SSE  ✅
                     └─► G5 /cache 全功能  ⏸ 冻结 → 第五阶段 T1 后
                          └─► M-UI  ⏸
                               └─► G6 E2E  ⏸ 部分已有 smoke
```

| 步 | 名称 | 轨 | 状态（2026-05-16） |
|----|------|-----|-------------------|
| **G0～G4** | 见 §12.2～12.6 正文 | 界面 / 契约 | **已实施** |
| **G5** | `/cache` 全功能 + 启动提醒 | 界面 | **第六阶段 F6-04～F6-05** |
| **M-UI** | 手动 UI 调校 | 负责人 | **第六阶段 F6-06** |
| **G6** | E2E / 打包冒烟 | CI | **部分**；T 轨后增补面板路径 |

---

### 12.2 步 G0 — 准备（约 0.5h）

**动作**

1. 阅读 **`DECISIONS.md` §13** 与本节全文。  
2. 确认本机：`cd src/gui && npm install`；`pytest` / 后端可按 `README` 起 stub。  
3. 创建分支，例如 `gui/g1-router-settings`。  
4. 启用 githooks：`git config core.hooksPath .githooks`（契约步需要）。

**验收**

- [ ] `cd src/gui && npm run build` 通过（现状基线）。  
- [ ] `npm run test:e2e`（现有 smoke）通过。  
- [ ] （可选）`cd src/electron && npm run electron:dev` 能打开当前单页 Chat。

---

### 12.3 步 G1 — Router + 设置页 + 缓存占位（首 PR）

**目标**：一次交付路由骨架；设置迁出 Drawer；**不** 要求多标签与磁盘缓存本步完成。

**范围**

- 依赖：`react-router-dom`（`HashRouter` 推荐：兼容 Electron `file://` 与 Vite `base: './'`）。  
- 路由：  
  - `/` → 重定向至 `/chat/<defaultId>` 或创建默认会话 id。  
  - `/chat/:id` — 现有 `ChatPage` 逻辑迁入（单会话即可）。  
  - `/settings` — 自 `SettingsDrawer.tsx` **迁出**主内容（可拆 `SettingsPage.tsx`）。  
  - `/cache` — **占位页**（标题 + 返回设置 +「功能开发中」或只读说明）。  
- 设置页：**按钮「已归档会话」** → `navigate('/cache')`；**顶栏无** `/cache` 入口。  
- 对话页：保留进入设置的入口（齿轮/按钮 → `/settings`）；**移除** 全屏 Drawer 作为主路径。  
- 布局壳：`AppShell`（顶栏区预留标签位，G1 可只放单标签占位）。

**禁止**

- 不改 `api_v1.py`（除非同步做 G2）。  
- 不实现多路 SSE、不写 `userData` JSON（留给 G3）。

**验收（自动化）**

- [ ] `npm run build` 无 TypeScript 错误。  
- [ ] Playwright：访问 `/` 仍能看到 health 成功（更新 smoke 路径若需）。  
- [ ] Playwright：能从对话页进入 `/settings`，点击「已归档会话」进入 `/cache`，**返回** `/settings`。

**验收（手动）**

- [ ] Vite `npm run dev`：上述路由跳转正常。  
- [ ] Electron dev：同上；`getApiBase` 与 health 仍正常。  
- [ ] 提交说明含：`契约：无变更`（若确实无契约改动）。

**Cursor 提示词片段**

```text
【Logos GUI · 步 G1】
权威：GUI开发文档.md §12.3；DECISIONS.md §13.1。
范围：仅 src/gui（react-router-dom、pages、routes）。
交付：/chat/:id、/settings（自 SettingsDrawer 迁出）、/cache 占位、「已归档会话」仅 settings 入口。
禁止：api_v1、bootstrap 字段、Electron IPC、多标签、磁盘缓存。
验收：npm run build；npm run test:e2e；契约：无变更。
```

---

### 12.4 步 G2 — 配置项与 bootstrap（契约轨，可与 G1 合并）

**目标**：服务端（或本地配置）提供 GUI 所需 **`ui.SSE_maxNum`**、**`ui.cache_warn_bytes`**。

**范围**

- `config/defaults.yaml`：  
  - `ui.SSE_maxNum: 3`  
  - `ui.cache_warn_bytes: 524288000`  
- 若 GUI 首屏从 bootstrap 读取：`GET /api/v1/bootstrap` 的 `ui` 段增字段 → **契约轨全套**（`api_v1.py`、`API-V0.2.md`、`test_stream5_api.py`、`bootstrap.ts`、`types`）。  
- 若 G1 阶段设置页阈值 **仅本地 state + 默认值**：可推迟 bootstrap 字段至本步。

**验收**

- [ ] `pytest tests/test_stream5_api.py`（及既有 bootstrap 测）通过。  
- [ ] GUI `fetchBootstrap` 能读到两字段（或文档注明暂用默认常量）。  
- [ ] 提交说明：`契约：已更新 API-V0.2（摘要：ui.SSE_maxNum、ui.cache_warn_bytes）` 或 `契约：无变更`。

---

### 12.5 步 G3 — Electron 缓存 IPC + 档 B JSON（单会话 → 索引）

**目标**：跨重启保留；每会话一个 JSON；用户不接触路径。

**Electron Main / preload（窄 IPC，白名单）**

建议暴露（命名实现期可微调）：

| IPC | 作用 |
|-----|------|
| `conversations.list()` | 返回元数据列表（id、title、status、updated_at、byte_size） |
| `conversations.read(id)` | 读单文件 JSON |
| `conversations.write(id, payload)` | 原子写（tmp + rename） |
| `conversations.delete(id)` | disposed |
| `conversations.totalBytes()` | 供 `/cache` 与启动提醒 |

根目录：`app.getPath('userData')/conversations/`。

**Renderer**

- `src/gui/src/conversation/`：`ConversationRecord` 类型，`schema_version: 2`（`skill_id`、`task_phase`、`task_input`；读盘兼容 v1 → 默认 `skill_id: chat_inspire`）。  
- 启动：加载索引；默认会话 `idle`；`active` 与路由 `:id` 同步。  
- G3 可先 **仅支持 1 个活跃标签 + 写盘**；多标签列表在 G4 扩展。

**验收**

- [ ] 发若干消息后重启 Electron，消息仍在。  
- [x] JSON 含 `schema_version: 2`（写盘）；v1 读入迁移；损坏文件有降级提示（不崩溃）。  
- [ ] Renderer 无硬编码绝对路径；无 `fs` 直连。  
- [ ] `npm run build`；Electron 手动冒烟。

---

### 12.6 步 G4 — 顶栏多标签 + 后台 SSE + 排队

**目标**：浏览器式顶栏；切换标签不 abort 流；并发上限 **`SSE_maxNum`**，超额 **排队**。

**范围**

- `TabBar`：新建、`×` 关闭（关闭 → `archived` 或提示）、切换 `navigate(/chat/:id)`。  
- `conversationStore`：`Map<id, state>`；非当前标签的 SSE 仍更新 store + 磁盘 + **未读角标**。  
- 发送队列：活跃流 ≥ `SSE_maxNum` 时新请求入队，完成后出队。  
- 归档：从标签菜单「归档」→ `archived`，从顶栏移除。

**验收**

- [ ] 开 3 个标签，同时在 3 个会话各发起流式请求（或模拟），均能在后台完成。  
- [ ] 第 4 个流式请求进入排队，完成后顺序执行。  
- [ ] 切换标签时，原标签流式未中断；回到标签可见完整结果/未读清除。  
- [ ] 归档后会话从顶栏消失，磁盘 JSON 仍在。

---

### 12.7 步 G5 — `/cache` 全功能 + 设置阈值 + 启动提醒

**目标**：归档治理与磁盘占用可见。

**范围**

- `/cache`：仅列出 `archived`；摘要列；多选 **销毁** / **恢复**（恢复 → `idle` + 出现在顶栏）。  
- `/settings`：`ui.cache_warn_bytes` 可调（与 bootstrap 或本地覆盖策略一致，见 G2）。  
- 启动：若 `totalBytes >= threshold` 且未在冷却期 → 模态/横幅，引导 **设置 → 已归档会话**；**稍后提醒** / **7 天内不再提醒**（`localStorage`）。  
- `/cache`：**返回设置**导航（§13.8）。

**禁止**

- 顶栏增加 `/cache` 入口。  
- 默认「在资源管理器中打开」缓存目录。

**验收**

- [ ] 归档 2 条 → `/cache` 可见 → 恢复 1 条 → 顶栏出现 → 销毁另 1 条 → 文件删除。  
- [ ] 占用显示与 `totalBytes` 一致（误差仅来自实现方式）。  
- [ ] 调低阈值或灌大数据 → 冷启动出现提醒；点「7 天内不再提醒」后重启不再弹。  
- [ ] 窄窗 320px 宽：`/cache` 可滚动、可返回。

---

### 12.8 步 M-UI — 手动视觉与布局调校（负责人执行）

> **定位**：功能步（G1～G5）使用 **占位样式**（可用现有 CSS 模块、最小间距）。**本步由你亲自**在浏览器与 Electron 中调校观感，避免 Agent 大范围改 CSS 与功能 PR 纠缠。

**建议流程（2～4h，可跨天）**

1. **浏览器优先**：`cd src/gui && npm run dev`，Chrome DevTools 调 `/chat`、`/settings`、`/cache`。  
2. **断点**：至少验证 **宽窗** 与 **~320×480（1/4 屏）**；顶栏标签换行/滚动策略。  
3. **Electron**：`electron:dev` 复验标题栏、拖拽区与顶栏不重叠。  
4. **记录**：在 `ChatPage.module.css`、`SettingsPage.module.css`、`CachePage.module.css`、`TabBar.module.css` 等中提交；**单 PR 或若干 commit**，message 如 `gui(ui): 步 M-UI 视觉定稿`。

**本步检查清单（你可打印勾选）**

| 区域 | 检查项 |
|------|--------|
| 顶栏标签 | 高度、选中态、未读角标、过多标签时横向滚动 |
| 对话区 | 消息气泡行距、推理/引用折叠、输入区固定底栏 |
| 设置 | 分区标题、阈值输入可读性、「已归档会话」按钮显眼 |
| `/cache` | 列表行高、批量勾选、销毁按钮危险色、总占用字号 |
| 窄窗 | 次要控件收进 `⋯`；无横向溢出 |
| 主题 | 与现有 `data-theme` / 系统主题一致 |

**Agent 在本步的边界**

- **仅**在你指定文件上改 CSS/间距/文案；**不**改 store、路由、IPC、契约。  
- 若发现 **功能缺陷**，另开 Gx 修复会话，不在 M-UI 混入逻辑。

**验收（负责人签字即完成）**

- [ ] 本人在 Electron 打包或 dev 下完成一轮完整对话 + 归档 + 清理。  
- [ ] 窄窗截图/备注存入团队习惯处（可选）。  
- [ ] `npm run build` 仍通过。

---

### 12.9 步 G6 — 回归、E2E 与文档

**范围**

- Playwright：窄 viewport smoke；设置 → `/cache` → 返回。  
- （可选）Electron 打包后手动清单：health、bootstrap、单会话发送。  
- 更新根 **`README.md`** 或本文 §1：正式产品仅 Electron；开发可用 Vite 调样式。  
- **会话保存 Skill**：仍不实现；见 **`会话保存Skill文档.md`**。

**验收**

- [ ] `npm run test:e2e` CI 绿。  
- [ ] `pytest` 无回归（若动过契约）。  
- [ ] §6.2 与 **`DECISIONS.md` §13** 无矛盾描述。

---

### 12.10 开工顺序速查

| 你若只想… | 从哪步开始 |
|-----------|------------|
| 尽快看到路由 + 设置页 | **G1**（复制 §12.3 Cursor 片段） |
| 同时让设置里阈值从服务端来 | G1 后立刻 **G2** |
| 先能重启不丢对话 | G1 → **G3**（G2 可并行） |
| 先不调 CSS，功能完再好看 | G1→G5，最后 **M-UI** |
| 个人调 UI 一周 | 功能 PR 合并后单独 **M-UI** 分支 |

**持久化轨（非本计划范围）**：KSFS 会话保存 → **`会话保存Skill文档.md`**；需时再开 Skill / 契约会话。

---

## 11. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-05-13 | 初版：与 **`第三阶段开发计划.md`**（已定案 P0+P1；后 P1 迁至第四阶段）对齐；Electron 定案 + Cursor 工作法 + 契约纪律。 |
| 2026-05-13 | **§6.1**：定案 Electron 物理路径为 **`src/electron/`**；§1 表与 §6 路径表同步。 |
| 2026-05-13 | §1：补充 **Electron 开发态启动命令** 与 `LOGOS_GUI_DEV_*` 环境变量，对齐 **`已完成/第三阶段开发计划.md`** M-A（步 1～2）。 |
| 2026-05-13 | §1：Electron 依赖安装改为 **`npm run install:with-mirror`**（`ELECTRON_MIRROR`），避免 npm 10+ 对项目级 `electron_mirror` 的警告；与 `README.md` 互链。 |
| 2026-05-14 | §1：补充 **`apiBase` / `apiUrl`**、打包 **`loadFile` + `getApiBase`**、DevTools 门控与 **`package:win`**；与第三阶段步 8～11 对齐。 |
| 2026-05-14 | 阶段索引：第四阶段主排期**已定案**（A7→MCP→Obs）；契约/产品化大块顺延；互链 **`产品化文档.md`**。 |
| 2026-05-14 | **§6.2**：设置页与 **Obs O4**（`obs.show_log_root_in_gui` / `bootstrap` 字段）占位说明，供后续按体验微调 UI。 |
| 2026-05-16 | **§12**：GUI 下一阶段分步计划（G0～G6、M-UI 手动调校）；§6.2 与 **`DECISIONS.md` §13** 对齐；§10 增加 §12 索引。 |
| 2026-05-16 | **§11**：第五阶段任务/Skill 驱动 IA；G1～G4 标已实施；G5/M-UI 冻结；互链 **`任务与Skill驱动GUI定案.md`**、**`第五阶段开发计划.md`**。 |
