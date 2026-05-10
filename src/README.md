# `src/` 说明

- 可导入的 Python 包根为 **`logos`**（`import logos`、`from logos.ports import TextEmbedder`）。
- `ARCHITECTURE.md` 中的 `src/ports/`、`src/agent/` 等，在仓库里对应为 **`src/logos/ports/`**、`**src/logos/agent/**`（同一逻辑路径，符合 setuptools 单包惯例）。
- **`src/gui/`**：V0.1 前端（Vite + React + TS，Stream 6）：`npm run dev` 通过 Vite 代理调用 `/api/v1/*`。
