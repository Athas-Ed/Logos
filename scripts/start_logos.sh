#!/usr/bin/env bash
# Logos 一键启动：后台 Uvicorn（:8000）+ 前台 Vite（:5173）；退出时结束后台进程。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY="${ROOT}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "未找到 ${PY}，请先：python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'" >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "未找到 npm，请先安装 Node.js。" >&2
  exit 1
fi

echo "仓库根: ${ROOT}"
echo "启动后端 http://127.0.0.1:8000 …"
"${PY}" "${ROOT}/scripts/run_backend_stub.py" &
BACK_PID=$!
trap 'kill "${BACK_PID}" 2>/dev/null || true' EXIT

sleep 2

echo "启动前端 Vite http://localhost:5173 …"
cd "${ROOT}/src/gui"
if [[ ! -d node_modules ]]; then
  npm install
fi
npm run dev
