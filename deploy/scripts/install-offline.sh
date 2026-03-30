#!/bin/bash
# install-offline.sh
# 在目标离线 ARM 服务器上执行，安装所有依赖
# 用法: ./install-offline.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DEPLOY_DIR="$PROJECT_DIR"

echo "=== 离线安装 YOLO Agent Platform ==="
echo "项目目录: $PROJECT_DIR"

# ===== 1. 创建目录结构 =====
echo ""
echo ">>> [1/5] 创建目录结构"
mkdir -p "$PROJECT_DIR/data"/{datasets,models,logs}
mkdir -p "$PROJECT_DIR/venv"

# ===== 2. 安装 Python 虚拟环境 =====
echo ""
echo ">>> [2/5] 创建 Python 虚拟环境"
if [ -d "$PROJECT_DIR/venv/bin/python" ]; then
    echo "虚拟环境已存在，跳过"
else
    python3 -m venv "$PROJECT_DIR/venv"
fi
source "$PROJECT_DIR/venv/bin/activate"

echo "Python: $(python --version)"
echo "pip: $(pip --version)"

# ===== 3. 安装 pip wheel 包 =====
echo ""
echo ">>> [3/5] 安装 Python 依赖（离线模式）"
if [ -d "$DEPLOY_DIR/wheels" ] && [ "$(ls "$DEPLOY_DIR/wheels" | wc -l)" -gt 0 ]; then
    pip install --no-index --find-links="$DEPLOY_DIR/wheels" -r "$PROJECT_DIR/backend/requirements.txt" \
        2>&1 | tail -20
else
    echo "警告: wheels 目录为空或不存在，尝试直接从 requirements.txt 安装"
    echo "（需要目标服务器能访问 PyPI，或已预装相同版本的包）"
    pip install -r "$PROJECT_DIR/backend/requirements.txt" \
        2>&1 | tail -20
fi

# ===== 4. 复制模型权重（如果有）=====
echo ""
echo ">>> [4/5] 复制模型权重"
if [ -d "$DEPLOY_DIR/models" ]; then
    cp -rn "$DEPLOY_DIR/models"/* "$PROJECT_DIR/data/models/" 2>/dev/null || true
    echo "模型已复制到 data/models/"
else
    echo "未找到 models/ 目录，跳过（YOLO 会自动下载基础权重）"
fi

# ===== 5. 构建前端（如果需要）=====
echo ""
echo ">>> [5/5] 前端构建"
if [ -d "$PROJECT_DIR/frontend/dist" ] && [ "$(ls "$PROJECT_DIR/frontend/dist" | wc -l)" -gt 0 ]; then
    echo "dist/ 已存在，跳过前端构建"
else
    echo "检测到前端需要构建..."
    # 检查是否有 npm
    if command -v npm >/dev/null 2>&1; then
        cd "$PROJECT_DIR/frontend"
        if [ -d "$DEPLOY_DIR/node_modules" ]; then
            echo "使用离线 node_modules"
            cp -r "$DEPLOY_DIR/node_modules" "$PROJECT_DIR/frontend/"
        fi
        npm install --legacy-peer-deps --offline 2>&1 | tail -5 || \
        npm install --legacy-peer-deps 2>&1 | tail -5
        npm run build 2>&1 | tail -10
    else
        echo "警告: 未找到 npm，请先安装 Node.js 或确保 dist/ 目录已存在"
    fi
fi

# ===== 6. 创建 .env =====
echo ""
echo ">>> 创建配置文件"
if [ ! -f "$PROJECT_DIR/backend/.env" ]; then
    cp "$DEPLOY_DIR/config/.env.offline" "$PROJECT_DIR/backend/.env"
    echo "已从模板创建 .env，请编辑 $PROJECT_DIR/backend/.env 确认配置"
else
    echo ".env 已存在，跳过"
fi

echo ""
echo "=== 安装完成 ==="
echo ""
echo "下一步 - 启动服务："
echo ""
echo "  # 激活虚拟环境"
echo "  cd $PROJECT_DIR"
echo "  source venv/bin/activate"
echo ""
echo "  # 启动后端（8000端口）"
echo "  PYTHONPATH=. nohup python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 \\"
echo "    > data/logs/backend.log 2>&1 &"
echo ""
echo "  # 启动前端（5173端口，开发模式）或用 nginx 托管 dist/"
echo "  cd frontend && npm run dev -- --host 0.0.0.0 --port 5173 \\"
echo "    > ../data/logs/frontend.log 2>&1 &"
echo ""
echo "建议：使用 nginx 托管 dist/ 静态文件，性能更好"
