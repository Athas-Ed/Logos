#!/usr/bin/env bash
# Logos 快速启动 Electron：按需拉起后端/Vite，轮询就绪后 electron:dev:fast（跳过多余 tsc）。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY="${ROOT}/.venv/bin/python"
GUI_DIR="${ROOT}/src/gui"
ELECTRON_DIR="${ROOT}/src/electron"
BACKEND_SCRIPT="${ROOT}/scripts/run_dev_backend.py"

if [[ ! -x "$PY" ]]; then
  echo "未找到 ${PY}，请先：python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'" >&2
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "未找到 npm，请先安装 Node.js。" >&2
  exit 1
fi
for d in "$GUI_DIR" "$ELECTRON_DIR"; do
  if [[ ! -d "$d" ]]; then
    echo "未找到目录：${d}" >&2
    exit 1
  fi
done
if [[ ! -f "$BACKEND_SCRIPT" ]]; then
  echo "未找到后端脚本：${BACKEND_SCRIPT}" >&2
  exit 1
fi

tcp_open() {
  local port=$1
  if command -v nc >/dev/null 2>&1; then
    nc -z 127.0.0.1 "$port" >/dev/null 2>&1
    return $?
  fi
  (echo >/dev/tcp/127.0.0.1/"$port") >/dev/null 2>&1
}

backend_ok() {
  curl -sf --max-time 2 "http://127.0.0.1:8000/api/v1/health" >/dev/null 2>&1
}

wait_dev_ready() {
  local timeout_sec=${1:-120}
  local start_ts
  start_ts=$(date +%s)
  while true; do
    if backend_ok && tcp_open 5173; then
      return 0
    fi
    if (( $(date +%s) - start_ts >= timeout_sec )); then
      return 1
    fi
    sleep 0.3
  done
}

BACK_PID=""
VITE_PID=""

cleanup_children() {
  [[ -n "${VITE_PID}" ]] && kill "${VITE_PID}" 2>/dev/null || true
  [[ -n "${BACK_PID}" ]] && kill "${BACK_PID}" 2>/dev/null || true
}

if ! backend_ok; then
  echo "启动后端 http://127.0.0.1:8000 …"
  "${PY}" "${BACKEND_SCRIPT}" &
  BACK_PID=$!
fi

if ! tcp_open 5173; then
  echo "启动 Vite http://127.0.0.1:5173 …"
  (
    cd "${GUI_DIR}"
    [[ -d node_modules ]] || npm install
    exec npm run dev
  ) &
  VITE_PID=$!
fi

if ! backend_ok || ! tcp_open 5173; then
  echo "轮询等待后端 health 与 Vite :5173（最多约 120 秒）…"
  if ! wait_dev_ready 120; then
    cleanup_children
    echo "超时：请确认 Backend / Vite 无报错后重试。" >&2
    exit 1
  fi
  echo "开发服务已就绪。"
fi

echo "启动 Electron（electron:dev:fast）…"
(
  cd "${ELECTRON_DIR}"
  export LOGOS_ELECTRON_SKIP_BACKEND=1
  if [[ ! -d node_modules ]]; then
    npm run install:with-mirror || npm install
  fi
  exec npm run electron:dev:fast
) &
ELECTRON_PID=$!

trap 'kill "${ELECTRON_PID}" 2>/dev/null || true; cleanup_children' EXIT INT TERM

echo "Electron PID ${ELECTRON_PID}（LOGOS_ELECTRON_SKIP_BACKEND=1）。"
echo "若白屏，待 Vite 编译完成后在 Electron 内刷新。"
echo "按 Ctrl+C 将尝试结束本脚本拉起的子进程。"

wait "${ELECTRON_PID}"
