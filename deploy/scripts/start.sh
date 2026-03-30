#!/bin/bash
# start.sh
# 启动 YOLO Agent Platform 所有服务
# 用法: ./start.sh [mode]
#   mode: dev (默认) - 开发模式，前端 npm run dev
#   mode: prod      - 生产模式，nginx 托管静态文件

MODE="${1:-dev}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== 启动 YOLO Agent Platform ==="
echo "模式: $MODE"
echo "项目目录: $PROJECT_DIR"

# 激活虚拟环境
source "$PROJECT_DIR/venv/bin/activate"

# 创建日志目录
mkdir -p "$PROJECT_DIR/data/logs"

# ===== 启动后端 =====
echo ""
echo ">>> 启动后端 (8000端口)..."
cd "$PROJECT_DIR"

# 检查是否已有运行中的后端
if curl -s http://localhost:8000/docs >/dev/null 2>&1; then
    echo "后端已在运行，跳过"
else
    PYTHONPATH=. nohup python -m uvicorn backend.main:app \
        --host 0.0.0.0 --port 8000 \
        > data/logs/backend.log 2>&1 &
    echo "后端 PID: $!"
    sleep 3

    # 检查是否启动成功
    if curl -s http://localhost:8000/docs >/dev/null 2>&1; then
        echo "后端启动成功: http://localhost:8000"
    else
        echo "后端启动失败，查看日志:"
        tail -20 data/logs/backend.log
    fi
fi

# ===== 启动前端 =====
echo ""
if [ "$MODE" = "prod" ]; then
    echo ">>> [生产模式] 使用 nginx 托管前端静态文件..."
    if command -v nginx >/dev/null 2>&1; then
        cp "$SCRIPT_DIR/../config/nginx.conf" /tmp/yolo-nginx.conf
        sed -i "s|/opt/yolo-agent-platform|$PROJECT_DIR|g" /tmp/yolo-nginx.conf
        nginx -c /tmp/yolo-nginx.conf
        echo "nginx 启动完成，访问 http://localhost:3000"
    else
        echo "nginx 未安装，fallback 到 npm run preview"
        cd "$PROJECT_DIR/frontend"
        nohup npm run preview -- --port 5173 --host 0.0.0.0 \
            > ../data/logs/frontend.log 2>&1 &
        echo "前端 PID: $!，访问 http://localhost:5173"
    fi
else
    echo ">>> [开发模式] 启动前端 dev server..."
    cd "$PROJECT_DIR/frontend"
    nohup npm run dev -- --host 0.0.0.0 --port 5173 \
        > ../data/logs/frontend.log 2>&1 &
    echo "前端 PID: $!，访问 http://localhost:5173"
fi

echo ""
echo "=== 服务状态 ==="
echo "后端 API: http://localhost:8000"
echo "前端 UI:  http://localhost:5173"
echo "API 文档: http://localhost:8000/docs"
echo ""
echo "日志位置: $PROJECT_DIR/data/logs/"
echo "  后端: data/logs/backend.log"
echo "  前端: data/logs/frontend.log"
echo ""
echo "停止服务: kill \$(lsof -ti:8000,5173)"
