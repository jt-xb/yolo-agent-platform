#!/bin/bash
# save-images.sh
# 在有网络的机器上构建并保存 Docker 镜像为 tar 包
# 目标架构: ARM aarch64 (麒麟服务器)
# 用法: ./save-images.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
IMAGES_DIR="$PROJECT_DIR/deploy/images"
DEPLOY_DOCKER_DIR="$PROJECT_DIR/deploy/docker"

echo "=== 构建并保存 Docker 镜像 (ARM aarch64) ==="
mkdir -p "$IMAGES_DIR"

cd "$PROJECT_DIR"

# ===== 构建后端镜像 (ARM) =====
echo ""
echo ">>> [1/3] 构建后端镜像 (arm64) ..."

# 检查是否已构建过
BACKEND_IMAGE="yolo-agent-backend:offline"
docker build \
    -f "$DEPLOY_DOCKER_DIR/Dockerfile.offline.backend" \
    --platform linux/arm64 \
    -t "$BACKEND_IMAGE" \
    . 2>&1 | tail -5

docker save "$BACKEND_IMAGE" -o "$IMAGES_DIR/yolo-agent-backend.tar"
echo "后端镜像已保存: yolo-agent-backend.tar ($(du -sh "$IMAGES_DIR/yolo-agent-backend.tar" | cut -f1))"

# ===== 构建前端镜像 (ARM) =====
echo ""
echo ">>> [2/3] 构建前端镜像 (arm64) ..."
FRONTEND_IMAGE="yolo-agent-frontend:offline"
docker build \
    -f "$DEPLOY_DOCKER_DIR/Dockerfile.offline.frontend" \
    --platform linux/arm64 \
    -t "$FRONTEND_IMAGE" \
    . 2>&1 | tail -5

docker save "$FRONTEND_IMAGE" -o "$IMAGES_DIR/yolo-agent-frontend.tar"
echo "前端镜像已保存: yolo-agent-frontend.tar ($(du -sh "$IMAGES_DIR/yolo-agent-frontend.tar" | cut -f1))"

# ===== Label Studio =====
echo ""
echo ">>> [3/3] 拉取 Label Studio 镜像 (arm64/v7) ..."
LS_IMAGE="heartexg/label-studio:1.7.2"
docker pull --platform linux/arm64 "$LS_IMAGE" 2>&1 | tail -3
docker save "$LS_IMAGE" -o "$IMAGES_DIR/label-studio.tar"
echo "Label Studio 镜像已保存: label-studio.tar ($(du -sh "$IMAGES_DIR/label-studio.tar" | cut -f1))"

echo ""
echo "=== 打包完成 ==="
ls -lh "$IMAGES_DIR"
echo ""
echo "下一步：拷贝 deploy/images/ 到目标服务器，执行 load-images.sh"
