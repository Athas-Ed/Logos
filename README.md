# Logos

游戏叙事向双模式 Agent（作家 / 编剧）。**V0.1 规格**见 `original_docs/SPEC-V0.1.md`；并行开发见 `original_docs/DEVPLAN-V0.1-PARALLEL.md`。

## Stream 0 本地环境

```bash
cd g:\GithubProject\Logos
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

- Python **3.11+**
- 包根：`import logos`（源码在 `src/logos/`，说明见 `src/README.md`）

## 配置与隐私

- 默认配置：`config/defaults.yaml`；本机密钥与覆盖：`config/local.yaml`（从 `config/local.example.yaml` 复制，勿提交）。
- 个人创作目录：`workspace/`（默认已 `.gitignore`）。
