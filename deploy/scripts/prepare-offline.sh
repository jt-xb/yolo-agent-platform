#!/bin/bash
# prepare-offline.sh
# 在有网络的机器上执行，一键准备离线部署所需的所有资源
# 下载 pip wheel 包、npm 包、模型权重，并打包 Docker 镜像
# 用法: ./prepare-offline.sh [arch]
#   arch: aarch64 (默认, ARM Kylin) 或 x86_64 (x86 Linux)

set -e

ARCH="${1:-aarch64}"
PYTHON_VERSION="${2:-3.10}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DEPLOY_DIR="$PROJECT_DIR/deploy"

echo "============================================"
echo "  YOLO Agent Platform — 离线部署准备脚本"
echo "============================================"
echo "架构: $ARCH"
echo "Python 版本: $PYTHON_VERSION"
echo "项目目录: $PROJECT_DIR"
echo ""

cd "$PROJECT_DIR"

# ===== 1. 下载 pip wheel 包 =====
echo ""
echo ">>> [1/4] 下载 Python 依赖包..."
if [ -d "$DEPLOY_DIR/wheels" ] && [ "$(ls "$DEPLOY_DIR/wheels" 2>/dev/null | wc -l)" -gt 50 ]; then
    echo "wheels/ 已存在 ($(du -sh "$DEPLOY_DIR/wheels" | cut -f1))，跳过下载"
else
    bash "$DEPLOY_DIR/scripts/download-wheels.sh" "$PYTHON_VERSION"
fi

# ===== 2. 下载模型权重 =====
echo ""
echo ">>> [2/4] 下载 AI 模型权重..."
if [ -d "$DEPLOY_DIR/models/yolo" ] && [ "$(ls "$DEPLOY_DIR/models/yolo" 2>/dev/null | wc -l)" -gt 0 ]; then
    echo "models/ 已存在，跳过下载"
else
    bash "$DEPLOY_DIR/scripts/download-models.sh"
fi

# 复制模型到项目 data/models/
mkdir -p "$PROJECT_DIR/data/models"
cp -rn "$DEPLOY_DIR/models"/* "$PROJECT_DIR/data/models/" 2>/dev/null || true

# ===== 3. 构建前端 dist =====
echo ""
echo ">>> [3/4] 构建前端..."
if [ -d "$PROJECT_DIR/frontend/dist" ] && [ "$(ls "$PROJECT_DIR/frontend/dist" 2>/dev/null | wc -l)" -gt 5 ]; then
    echo "dist/ 已存在，跳过构建"
else
    cd "$PROJECT_DIR/frontend"
    if [ -d "$DEPLOY_DIR/node_modules" ]; then
        echo "使用离线 node_modules"
        cp -r "$DEPLOY_DIR/node_modules" "$PROJECT_DIR/frontend/"
    fi
    npm install --legacy-peer-deps 2>&1 | tail -3
    npm run build 2>&1 | tail -5
    echo "前端 dist/ 大小: $(du -sh dist/ | cut -f1)"
fi

# ===== 4. 打包 Docker 镜像 =====
echo ""
echo ">>> [4/4] 构建并打包 Docker 镜像..."
echo "注意：Docker 构建需要网络连接下载基础镜像"

# 确保 wheels 目录存在
if [ ! -d "$DEPLOY_DIR/wheels" ] || [ "$(ls "$DEPLOY_DIR/wheels" 2>/dev/null | wc -l)" -lt 10 ]; then
    echo "警告: wheels/ 目录为空或不完整，Docker 镜像构建可能失败"
    echo "（请先确保 pip wheel 下载成功）"
fi

# 保存镜像
bash "$DEPLOY_DIR/scripts/save-images.sh"

echo ""
echo "============================================"
echo "  离线部署准备完成！"
echo "============================================"
echo ""
echo "输出目录结构："
echo "  deploy/wheels/        — Python pip 包 ($(du -sh "$DEPLOY_DIR/wheels" 2>/dev/null | cut -f1 || echo '无')"
echo "  deploy/images/        — Docker 镜像 tar 包"
echo "  deploy/models/         — AI 模型权重"
echo "  frontend/dist/        — 前端静态文件"
echo ""
echo "下一步 — 拷贝到目标离线服务器："
echo "  scp -r yolo-agent-platform root@<目标服务器>:/opt/"
echo ""
echo "然后在目标服务器上执行："
echo "  cd /opt/yolo-agent-platform/deploy/scripts"
echo "  chmod +x *.sh"
echo "  ./load-images.sh"
echo "  cd /opt/yolo-agent-platform"
echo "  source venv/bin/activate"
echo "  # 或直接用 docker compose:"
echo "  cd deploy && docker compose -f docker/docker-compose.offline.yml up -d"
