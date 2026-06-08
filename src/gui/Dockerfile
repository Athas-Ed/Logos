# =============================================================================
# Logos GUI — 多阶段 Dockerfile
# =============================================================================
# 构建 React 前端，以 Nginx 提供静态文件 + 反向代理 /api 到后端。
# docker-compose 中与 logos-backend 服务配合使用。
# =============================================================================

# ----- 阶段一：构建 --------------------------------------------------------
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# ----- 阶段二：运行（Nginx）-------------------------------------------------
FROM nginx:1.27-alpine

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# Nginx 配置：serve 静态文件 + /api 反向代理
COPY <<'EOF' /etc/nginx/conf.d/default.conf
server {
    listen       3000;
    server_name  localhost;

    # 前端静态文件
    location / {
        root   /usr/share/nginx/html;
        index  index.html;
        try_files $uri $uri/ /index.html;
    }

    # API 反向代理到后端
    location /api/ {
        proxy_pass http://logos-backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;

        # SSE 支持（不缓冲）
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header X-Accel-Buffering no;
    }
}
EOF

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
