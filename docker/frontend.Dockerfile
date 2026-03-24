# 多阶段构建
FROM node:18-alpine AS builder

WORKDIR /app

# 复制前端代码
COPY frontend/ /app/frontend/

# 安装依赖
RUN cd /app/frontend && npm install

# 构建
RUN cd /app/frontend && npm run build

# Nginx 生产镜像
FROM nginx:alpine

# 复制构建产物
COPY --from=builder /app/frontend/dist /usr/share/nginx/html

# Nginx 配置
RUN echo 'server { \
    listen 80; \
    server_name localhost; \
    root /usr/share/nginx/html; \
    index index.html; \
    location / { \
        try_files $uri $uri/ /index.html; \
    } \
    location /api { \
        proxy_pass http://backend:8000; \
        proxy_set_header Host $host; \
    } \
    location /ws { \
        proxy_pass http://backend:8000; \
        proxy_http_version 1.1; \
        proxy_set_header Upgrade $http_upgrade; \
        proxy_set_header Connection "upgrade"; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
