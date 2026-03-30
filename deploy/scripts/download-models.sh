#!/bin/bash
# download-models.sh
# 在有网络的机器上执行，下载 YOLO/SAM/DINO 模型权重
# 用法: ./download-models.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
MODELS_DIR="$PROJECT_DIR/models"
TRAIN_MODELS_DIR="$PROJECT_DIR/data/models"

echo "=== 下载 AI 模型权重 ==="
mkdir -p "$MODELS_DIR/yolo" "$MODELS_DIR/sam" "$MODELS_DIR/grounding-dino" "$TRAIN_MODELS_DIR"

cd "$MODELS_DIR"

# ===== YOLOv8 系列 =====
echo ""
echo ">>> 下载 YOLOv8n (nano, 最快) ..."
if [ ! -f "yolo/yolov8n.pt" ]; then
    curl -L -o yolo/yolov8n.pt \
        "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt" \
        2>&1 | tail -3
else
    echo "已存在，跳过"
fi

echo ">>> 下载 YOLOv8s (small) ..."
if [ ! -f "yolo/yolov8s.pt" ]; then
    curl -L -o yolo/yolov8s.pt \
        "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8s.pt" \
        2>&1 | tail -3
else
    echo "已存在，跳过"
fi

echo ">>> 下载 YOLOv8m (medium) ..."
if [ ! -f "yolo/yolov8m.pt" ]; then
    curl -L -o yolo/yolov8m.pt \
        "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8m.pt" \
        2>&1 | tail -3
else
    echo "已存在，跳过"
fi

# ===== SAM (Segment Anything) =====
echo ""
echo ">>> 下载 SAM ViT-H 模型 ..."
SAM_DIR="sam"
if [ ! -f "$SAM_DIR/sam_vit_h_4b8939.pth" ]; then
    curl -L -o "$SAM_DIR/sam_vit_h_4b8939.pth" \
        "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth" \
        2>&1 | tail -3
else
    echo "已存在，跳过"
fi

# ===== Grounding DINO =====
echo ""
echo ">>> 下载 Grounding DINO T (transformer) ..."
DINO_DIR="grounding-dino"
if [ ! -f "$DINO_DIR/groundingdino_t" ]; then
    curl -L -o "$DINO_DIR/groundingdino_t" \
        "https://huggingface.co/ShilongLiu/GroundingDINO/resolve/main/groundingdino-tiny-config.py" \
        2>&1 | tail -3
fi

if [ ! -f "$DINO_DIR/groundingdino_t.pth" ]; then
    curl -L -o "$DINO_DIR/groundingdino_t.pth" \
        "https://huggingface.co/ShilongLiu/GroundingDINO/resolve/main/groundingdino-tiny.pth" \
        2>&1 | tail -3
fi

echo ""
echo "=== 模型下载完成 ==="
echo "YOLO: $(ls -lh yolo/ 2>/dev/null | tail -n+2 || echo '无')"
echo "SAM: $(ls -lh sam/ 2>/dev/null | tail -n+2 || echo '无')"
echo "DINO: $(ls -lh grounding-dino/ 2>/dev/null | tail -n+2 || echo '无')"
echo ""
echo "下一步：将 models/ 目录拷贝到目标服务器的 data/ 下："
echo "  cp -r models/* /opt/yolo-agent-platform/data/models/"
