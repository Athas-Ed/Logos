#!/usr/bin/env bash
# =============================================================================
# Logos 一键启动脚本（Docker 方式）
# 用法:
#   ./start.sh              # 构建 + 启动 + 打开浏览器
#   ./start.sh --no-browser # 构建 + 启动，不打开浏览器
#   ./start.sh --rebuild    # 强制重建镜像
#   ./start.sh --down       # 停止所有容器
#   ./start.sh --logs       # 跟踪日志
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# ─── 停止 ───────────────────────────────────────────────────────────
if [ "${1:-}" = "--down" ]; then
    echo "⏹️  停止 Logos 容器..."
    docker compose down
    echo "✅ 已停止"
    exit 0
fi

# ─── 确保 Docker 运行 ───────────────────────────────────────────────
if ! docker info &>/dev/null; then
    echo "❌ Docker Desktop 未运行，请先启动 Docker Desktop。"
    exit 1
fi

# ─── 自动生成默认配置 ─────────────────────────────────────────────
if [ ! -f config/local.yaml ]; then
    echo "📝 生成默认配置 config/local.yaml（无 API Key = 桩后端模式）..."
    cat > config/local.yaml << 'CONFIG'
# 自动生成 — 无 API Key，使用桩后端 LLM
# 如需调用真实模型，取消注释并填入：
# llm:
#   api_key: "sk-..."
#   base_url: "https://api.deepseek.com/v1"
#   model: "deepseek-chat"
CONFIG
fi

# ─── 构建镜像 ──────────────────────────────────────────────────────
if [ "${1:-}" = "--rebuild" ]; then
    echo "🏗️  强制重建 Docker 镜像..."
    docker compose build --no-cache
else
    echo "🏗️  构建 Docker 镜像（如有变更）..."
    docker compose build
fi

# ─── 启动容器 ──────────────────────────────────────────────────────
echo "🚀 启动 Logos（后端 :8000 + 前端 :3000）..."
docker compose up -d

# ─── 等待就绪 ──────────────────────────────────────────────────────
echo "⏳ 等待后端就绪..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/api/v1/health > /dev/null 2>&1; then
        echo "✅ 后端就绪"
        break
    fi
    echo "."
    sleep 2
done

# ─── 打开浏览器 ────────────────────────────────────────────────────
if [ "${1:-}" != "--no-browser" ]; then
    echo "🌐 打开 http://localhost:3000 ..."
    if command -v xdg-open &>/dev/null; then
        xdg-open http://localhost:3000
    elif command -v open &>/dev/null; then
        open http://localhost:3000
    else
        echo "  请手动打开 http://localhost:3000"
    fi
fi

# ─── 提示 ──────────────────────────────────────────────────────────
echo ""
echo "╔════════════════════════════════════════╗"
echo "║  Logos 已启动                          ║"
echo "║  前端: http://localhost:3000           ║"
echo "║  后端: http://localhost:8000           ║"
echo "║  停止: ./start.sh --down               ║"
echo "║  日志: ./start.sh --logs               ║"
echo "╚════════════════════════════════════════╝"

if [ "${1:-}" = "--logs" ]; then
    echo "📋 跟踪日志（Ctrl+C 停止，容器继续运行）..."
    docker compose logs -f
fi
