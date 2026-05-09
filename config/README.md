# 配置说明

- **`defaults.yaml`**：**可提交 Git** 的默认值，**不含**真实密钥。
- **`local.yaml`**：本机私有覆盖（含 API Key 等）。**不要提交**；从 **`local.example.yaml`** 复制一份后改名/填写。

加载顺序建议：`defaults.yaml` → `local.yaml`（后者覆盖前者）；若实现支持，可再允许**进程环境变量**覆盖个别键（便于容器部署），**不**使用仓库根目录的 `.env` 文件。
