#!/bin/sh
# =============================================================================
# Logos Docker 容器入口点
# 自动生成默认配置（如不存在），确保 docker compose up 零手动步骤
# =============================================================================
set -e

if [ ! -f /app/config/local.yaml ]; then
    echo "📝 生成默认配置 config/local.yaml（无 API Key = 桩后端模式）"
    cat > /app/config/local.yaml << 'CONFIG'
# 自动生成 — 无 API Key，使用桩后端 LLM
# 如需调用真实模型，取消注释并填入：
# llm:
#   api_key: "sk-..."
#   base_url: "https://api.deepseek.com/v1"
#   model: "deepseek-chat"
CONFIG
fi

exec python -m logos.platform.ii_layer.app "$@"
