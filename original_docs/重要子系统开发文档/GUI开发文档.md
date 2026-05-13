# Logos — GUI 与 Electron 壳层开发（权威指南）

> **地位**：**本仓库内一切与「Web GUI（`src/gui`）+ 未来/现行 Electron 桌面壳」相关的实现与评审**，以本文与 **`API-V0.2.md`**、**`SPEC-DISPLAY-AND-LOGGING-V0.1.md`**、**`DECISIONS.md` §10** 为权威组合：  
> - **HTTP/SSE 形状与事件名** → 以 **`API-V0.2.md`** 为准；  
> - **展示档位、日志 profile、`bootstrap` 语义** → 以 **SPEC** 与 **`API-V0.2.md`** 为准；  
> - **产品形态（侧边栏优先、Electron 壳）** → 以 **`DECISIONS.md` §10** 为准；  
> - **进程模型、安全边界、目录约定、Cursor 协作** → **以本文为准**。  
> **更新**：随 Electron 落地与 CI 策略迭代；与 **`第三阶段开发计划.md`** 范围同步。

---

## 1. 当前仓库事实（写作基线）

| 要素 | 现状 |
|------|------|
| **Web GUI** | `src/gui/`：Vite + React + TypeScript；开发服务器默认端口 **5173**。 |
| **开发态 API** | `vite.config.ts` 将 **`/api` 代理**到 `VITE_DEV_API_PROXY_TARGET`（默认 `http://127.0.0.1:8000`）。 |
| **HTTP 客户端** | `src/gui/src/api/`：`health.ts`、`bootstrap.ts`、`sseChat.ts`、`developer.ts`；类型见 `src/gui/src/types/`。 |
| **Electron** | **物理路径已定案：`src/electron/`**（Main、preload、壳层专用 `package.json` / tsconfig 等）；与 `src/gui`、`src/logos` 并列，见 §6.1。**开发态启动**：先 `cd src/gui && npm run dev`，再 `cd src/electron && npm install && npm run electron:dev`（Main 先展示内嵌加载页，再轮询 **`GET /api/v1/health`** 就绪后 `loadURL` 至默认 `http://127.0.0.1:5173/`；若 5173 未监听则 Main 内警告对话框 + stderr 提示）。**Main 默认**在仓库根 `spawn` **`scripts/run_backend_stub.py`**（`LOGOS_REPO_ROOT`、优先 `.venv` 下 Python，与 `README` 一致）；若后端已在外部启动，设 **`LOGOS_ELECTRON_SKIP_BACKEND=1`**（`scripts/start_logos.*` 已设；此时**跳过**健康门）。可选覆盖：`LOGOS_GUI_DEV_HOST`、`LOGOS_GUI_DEV_PORT`、`LOGOS_PYTHON`、`LOGOS_BACKEND_USE_UV`、`LOGOS_ELECTRON_BACKEND_STDIO`、`LOGOS_BACKEND_HEALTH_URL` 或 `LOGOS_BACKEND_API_ORIGIN`、`LOGOS_ELECTRON_BACKEND_READY_TIMEOUT_MS`（默认 120000，**0** 表示仅探测一次）、`LOGOS_ELECTRON_BACKEND_HEALTH_POLL_MS`（默认 400）。若安装 Electron 时出现 **`read ECONNRESET`**，在 `src/electron` 使用 **`npm run install:with-mirror`**（见 **`README.md`**）。**退出清理**：`before-quit` 与 `will-quit` 均会尝试终止后端；非 macOS 在 **`window-all-closed`** 于 `app.quit()` 前再终止一次；Windows 使用 **`taskkill /PID <pid> /T /F`** 结束进程树，Unix 对子进程发 **`SIGTERM`**（重复调用容错）。 |

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
- 在会话首条消息粘贴 **`第三阶段开发计划.md`** 或本文件中的对应小节，并写明：**禁止修改** `src/logos/persistence/` 等无关目录（除非任务本身需要）。

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

## 9. 测试与 CI 期望（第三阶段对齐）

| 层级 | 目标 |
|------|------|
| **单元 / 契约** | TS 侧对 `bootstrap` 解析、`sseChat` 事件归约做纯函数测（可选，按投入递增）。 |
| **E2E** | 至少一条：**应用启动 → `/api/v1/health` 或 bootstrap 成功路径**；Electron 合并后改为「起壳 → 后端就绪 → 同上」。 |
| **手动清单** | 保留一份短清单在 **`README.md`** 或本文附录：首次安装、端口占用、日志路径。 |

---

## 10. 与阶段计划的对应关系

| 第三阶段内容 | 本文锚点 |
|----------------|----------|
| P0 Electron HA | §2、§3、§4、§9 |
| P0 打包 | §2.2、§9 |
| P1 契约工程升级 | §7、**`API终极文档.md`** §4.3 |
| P1 A7 / MCP | 以后端与 CLI 为主；GUI 仅在需要暴露按钮或路径时遵循 §6 |

---

## 11. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-05-13 | 初版：与 **`第三阶段开发计划.md`**（已定案 P0+P1）对齐；Electron 定案 + Cursor 工作法 + 契约纪律。 |
| 2026-05-13 | **§6.1**：定案 Electron 物理路径为 **`src/electron/`**；§1 表与 §6 路径表同步。 |
| 2026-05-13 | §1：补充 **Electron 开发态启动命令** 与 `LOGOS_GUI_DEV_*` 环境变量，对齐 **`第三阶段开发计划.md`** M-A（步 1～2）。 |
| 2026-05-13 | §1：Electron 依赖安装改为 **`npm run install:with-mirror`**（`ELECTRON_MIRROR`），避免 npm 10+ 对项目级 `electron_mirror` 的警告；与 `README.md` 互链。 |
