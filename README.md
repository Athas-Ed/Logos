# Logos

游戏叙事向双模式 Agent（作家 / 编剧）。**V0.1 规格**见 `original_docs/SPEC-V0.1.md`；并行开发见 `original_docs/DEVPLAN-V0.1-PARALLEL.md`。

## Stream 0 本地环境

```bash
cd g:\GithubProject\Logos
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
pytest
# 跳过需本机 BGE 权重的慢测：pytest -m "not slow"
```

- Python **3.11+**
- 包根：`import logos`（源码在 `src/logos/`，说明见 `src/README.md`）

## 配置与隐私

- 默认配置：`config/defaults.yaml`；本机密钥与覆盖：`config/local.yaml`（从 `config/local.example.yaml` 复制，勿提交）。
- 个人创作目录：`workspace/`（默认已 `.gitignore`）。
- 面向本机阅读的**日志行、JSON 日志字段名、常见异常提示**等以**简体中文**为主（便于日常使用）；API 路径、配置键名、代码标识符仍保持英文以便与文档/生态对齐。

## 向量与 HTTP（开发依赖）

- **`chromadb`**：Chroma 持久化客户端（`ChromaSemanticStore`），`pip install -e ".[dev]"` 已包含。
- **`sentence-transformers` + PyTorch**：本地 `BgeSmallZhEmbedder` 加载 `models/tooling/embeddings/bge-small-zh-v1.5` 时需要（体积较大，首次会自动下载相关 wheel）。
- **`fastapi` / `uvicorn` / `httpx`**：`/api/v1` 与 SSE 测试用，同上在 `[dev]` 中。
