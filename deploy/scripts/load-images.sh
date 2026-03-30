#!/bin/bash
# load-images.sh
# 在目标离线服务器上加载 Docker 镜像
# 用法: ./load-images.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
IMAGES_DIR="$PROJECT_DIR/deploy/images"

echo "=== 加载 Docker 镜像 ==="

if [ ! -d "$IMAGES_DIR" ]; then
    echo "错误: 找不到镜像目录 $IMAGES_DIR"
    exit 1
fi

for tar in "$IMAGES_DIR"/*.tar; do
    if [ -f "$tar" ]; then
        name=$(basename "$tar" .tar)
        echo "加载: $name ..."
        docker load -i "$tar" 2>&1 | grep -v "Loading layer" | grep -E "(Loaded image|Loaded:)" || true
    fi
done

echo ""
echo "=== 加载完成，当前镜像列表 ==="
docker images | grep -E "yolo-agent|label-studio" || echo "（请手动确认镜像已加载）"
