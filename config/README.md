# 配置说明

- **`defaults.yaml`**：**可提交 Git** 的默认值，**不含**真实密钥。
- **`local.yaml`**：本机私有覆盖（含 API Key 等）。**不要提交**；从 **`local.example.yaml`** 复制一份后改名/填写。

加载顺序建议：`defaults.yaml` → `local.yaml`（后者覆盖前者）；若实现支持，可再允许**进程环境变量**覆盖个别键（便于容器部署），**不**使用仓库根目录的 `.env` 文件。

## 日志目录（`logs/`）

- **配置位置**：`defaults.yaml` → `paths.logs_root`（默认 `./logs`）；可用 `local.yaml` 覆盖，或用环境变量 `LOGOS_PATHS__LOGS_ROOT`。
- **生效方式**：在进程启动时调用 `logos.harness.obs.configure_logging`（会读取合并后的配置）；内部会**自动创建**该目录（含父路径）。
- **测试**：`pytest` 会在临时目录下创建 `…/logs/_pytest/` 子目录写入测试日志，避免污染你本机 `./logs`。
