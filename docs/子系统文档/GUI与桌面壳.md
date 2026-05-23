# GUI 与桌面壳

## 组成

| 部分 | 路径 | 技术 |
|------|------|------|
| Web GUI | `src/gui/` | React、TypeScript、Vite |
| 桌面壳 | `src/electron/` | Electron Main + Preload |

开发态：GUI 由 Vite 提供（`:5173`），`/api` 代理到后端（`:8000`）。  
打包态：静态资源随 Electron 分发，Preload 提供 API 根地址与会话 IPC。

## 主要页面

- **技能面板**、**任务页**、**长对话页**、**设置**、**缓存治理**（`/cache`）。
- 开发者选项（Prompt 回显等）受配置 `developer.show_dev_tools_ui` 控制。

## Electron 职责

- 启动或跳过内置桩后端（`LOGOS_ELECTRON_SKIP_BACKEND`）。
- 解析仓库根（`LOGOS_REPO_ROOT`、便携包向上查找等）。
- 会话 JSON 的 **IPC 读写**（`conversations/*.json`）。
- 子进程日志写入 `logs/maint/electron-shell.log` 等。

## 开发启动顺序

1. 后端 `:8000`（一键脚本或 `run_backend_stub.py`）。
2. `cd src/gui && npm run dev`。
3. `cd src/electron && npm run electron:dev`（需 Vite 已就绪）。

Windows 一键：`scripts/start_logos.cmd` / `start_logos.ps1`。

## 安装与打包提示

| 问题 | 处理 |
|------|------|
| Electron 下载失败 | `npm run install:with-mirror`（npmmirror） |
| `Electron failed to install correctly` | 删除 `node_modules/electron` 后重装 |
| 打包 Windows | 先 `src/gui` 执行 `npm run build`，再 `src/electron` 的 `npm run package:win` |
| 仅拷贝 exe 无仓库 | 设置环境变量 `LOGOS_REPO_ROOT` |

产物目录：`src/electron/release/`（便携 exe 与 `win-unpacked/`）。

## 测试

- 单元：`cd src/gui && npm test`（Vitest）
- E2E：`npm run test:e2e`（Playwright，会按需拉起后端与 Vite）

## 相关文档

- [快速开始](../快速开始.md)
- [会话与任务缓存](会话与任务缓存.md)
- [HTTP API 概览](HTTP-API概览.md)
