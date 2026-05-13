#!/usr/bin/env bash
# Logos 一键启动：后台 Uvicorn（:8000）+ 后台 Vite（:5173）+ 后台 Electron；Ctrl+C 结束本脚本时一并清理子进程。
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

GUI_DIR="${ROOT}/src/gui"
ELECTRON_DIR="${ROOT}/src/electron"
if [[ ! -d "$GUI_DIR" ]]; then
  echo "未找到前端目录：${GUI_DIR}" >&2
  exit 1
fi
if [[ ! -d "$ELECTRON_DIR" ]]; then
  echo "未找到 Electron 目录：${ELECTRON_DIR}" >&2
  exit 1
fi

echo "仓库根: ${ROOT}"
echo "启动后端 http://127.0.0.1:8000 …"
"${PY}" "${ROOT}/scripts/run_backend_stub.py" &
BACK_PID=$!

(
  cd "${GUI_DIR}"
  [[ -d node_modules ]] || npm install
  exec npm run dev
) &
VITE_PID=$!

sleep 2

# Electron loadURL 依赖 Vite；首次编译可能较慢
sleep 5

(
  cd "${ELECTRON_DIR}"
  if [[ ! -d node_modules ]]; then
    npm run install:with-mirror || npm install
  fi
  exec npm run electron:dev
) &
ELECTRON_PID=$!

cleanup() {
  kill "${ELECTRON_PID}" 2>/dev/null || true
  kill "${VITE_PID}" 2>/dev/null || true
  kill "${BACK_PID}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "已启动：后端 PID ${BACK_PID}，Vite PID ${VITE_PID}，Electron PID ${ELECTRON_PID}。"
echo "若 Electron 白屏，待 Vite 编译完成后在 Electron 内刷新或重启 Electron。"
echo "按 Ctrl+C 将尝试结束上述进程。"

wait "${VITE_PID}"
