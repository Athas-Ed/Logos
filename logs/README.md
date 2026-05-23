# `logs/` 目录说明

根路径由配置 **`paths.logs_root`** 决定（默认即本目录 `./logs`），Obs 与 Electron 壳层审计共用此根。

## `daily/` — 日常轨

- **路径形态**：`daily/YYYY-MM/YYYY-MM-DD.log`（按 UTC 日期切分）。
- **内容**：面向「产品日常运行」的 **INFO 及以上** 记录；**不**随 `obs.log_profile` 放宽到 DEBUG（与维护轨解耦）。
- **典型用途**：排障时按日期打开，体积可控。

## `maint/` — 维护轨

- **路径形态**：按子系统分文件，例如 `api.log`、`mcp.log`、`platform.log`、`core.log` 等（路由规则见 `src/logos/platform/obs/path_handlers.py`）。
- **内容**：工程侧细节；**级别**随 **`obs.log_profile`**（及控制台）变化，可为 DEBUG / 审计向。
- **Electron**：后端崩溃与自动重启审计写在 **`electron-shell.log`**（与 Python 同根，不落系统 userData）。

## Git 与忽略

- 仓库内保留 **`README.md`** 与子目录 **`.gitkeep`** 作为占位；所有 **`*.log`** 由根目录 `.gitignore` 忽略，避免误提交运行产物。

## 旧文件名（platform 重命名后）

- 支撑层维护轨已由 **`harness.log`** 改为 **`platform.log`**。若本机 `maint/` 下仍有 `harness.log`，可手动删除或重命名；新日志写入 `platform.log`。
