# =============================================================================
# Logos 后端 — 多阶段 Dockerfile
# =============================================================================
# 构建缓存策略：
# - pyproject.toml 不变 → pip 安装层永久命中（几百 MB 依赖不重下）
# - 仅改 src/ 代码    → 只重新 COPY src/ + pip install -e "."（几秒）
# =============================================================================

# ----- 阶段一：依赖安装 ------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /app

# 系统依赖（ChromaDB / sentence-transformers 可能需要的编译工具）
RUN sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || true \
    && sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list 2>/dev/null || true \
    && apt-get update -o Acquire::http::Timeout=120 \
    && apt-get install -y --no-install-recommends --option Acquire::http::Timeout=120 \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 拷贝依赖声明 + 最小占位源码（使 pip install -e 能解析包名但不拷真实代码）
COPY pyproject.toml README.md ./
RUN mkdir -p src/logos && touch src/logos/__init__.py

# 安装全部依赖（含 dev 依赖如 chromadb/fastapi/uvicorn）但不保留包本身
# 此层在 pyproject.toml 不变时永��命中缓存
RUN pip install --no-cache-dir --default-timeout=120 \
        -i https://pypi.tuna.tsinghua.edu.cn/simple \
        -e ".[dev]" \
    && pip uninstall -y logos \
    && rm -rf src

# 拷贝真实源码并安装 logos 包
COPY src/ ./src/
RUN pip install --no-cache-dir --default-timeout=120 \
        -i https://pypi.tuna.tsinghua.edu.cn/simple \
        -e "."

# ----- 阶段二：运行镜像 ------------------------------------------------
FROM python:3.11-slim AS runner

WORKDIR /app

RUN sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || true \
    && sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list 2>/dev/null || true \
    && apt-get update -o Acquire::http::Timeout=120 \
    && apt-get install -y --no-install-recommends --option Acquire::http::Timeout=120 \
    libgcc-s1 \
    && rm -rf /var/lib/apt/lists/*

# 从 builder 拷贝已安装的 site-packages + bin
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# 环境变量（容器内 Python 能找到 logos 包和配置）
ENV LOGOS_REPO_ROOT=/app
ENV LOGOS_CONFIG_DIR=/app/config
ENV PYTHONPATH=/app/src

# 拷贝只读资产
COPY pyproject.toml README.md ./
COPY resources/ ./resources/
COPY skills/manifests/ ./skills/manifests/
COPY models/ ./models/

# 拷贝入口脚本（自动生成默认配置）
COPY scripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# 最后拷贝代码（最常变）
COPY src/ ./src/

EXPOSE 8000

# 先自动生成配置（如无 local.yaml），再启动应用
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
