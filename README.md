# Logos

面向游戏叙事的本地写作 Agent 实验仓库（作家 / 编剧双模式、KSFS 知识库、Electron 桌面 + React GUI）。

> **说明**：项目仍在积极开发，API 与目录可能变动，**暂不承诺**对外开箱即用。介绍性文档见 **[`docs/`](docs/README.md)**；作者自用草稿与排期在本机 **`original_docs/`**（不入库）。

## 仓库概览

| 路径 | 用途 |
|------|------|
| `src/logos/` | Python 核心（Agent、HDL、Harness） |
| `src/gui/`、`src/electron/` | Web GUI 与桌面壳 |
| `skills/` | MCP Skill 与 manifest |
| `config/` | `defaults.yaml` + 本机 `local.yaml`（勿提交） |
| `workspace/` | 个人创作区（默认不入库） |
| `docs/` | **对外介绍文档** |

## 文档入口

完整索引：[**docs/README.md**](docs/README.md)

| 主题 | 文档 |
|------|------|
| 项目是什么 | [docs/项目概述.md](docs/项目概述.md) |
| 架构与目录 | [docs/架构概览.md](docs/架构概览.md) |
| 安装与启动 | [docs/快速开始.md](docs/快速开始.md) |
| 配置与密钥 | [docs/配置说明.md](docs/配置说明.md) |
| KSFS 知识库 | [docs/子系统文档/KSFS与叙事知识库.md](docs/子系统文档/KSFS与叙事知识库.md) |
| 任务 / Skill 界面 | [docs/子系统文档/任务与Skill界面.md](docs/子系统文档/任务与Skill界面.md) |
| HTTP API | [docs/子系统文档/HTTP-API概览.md](docs/子系统文档/HTTP-API概览.md) |
| 更多子系统 | [docs/子系统文档/README.md](docs/子系统文档/README.md) |

## 本机运行（最短路径）

**环境**：Python 3.11+；Node.js（GUI / Electron）。在仓库根目录：

```bash
python -m venv .venv
# Windows: .\.venv\Scripts\activate
pip install -e ".[dev]"
pytest -m "not slow"
```

**日常开发（Windows）**：`scripts/start_logos.cmd` 或 `scripts/start_logos.ps1`。  
细节见 [docs/快速开始.md](docs/快速开始.md)。

## 配置与隐私

- 默认：`config/defaults.yaml`；本机：`config/local.yaml`（已 `.gitignore`）。
- 创作与索引：`workspace/`、`.index/` 默认不入库。

## 许可证

[MIT License](LICENSE)
