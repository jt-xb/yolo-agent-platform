#!/usr/bin/env python3
"""
创建演示数据集
用于 YOLO Agent 平台测试
"""
import os
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import numpy as np

# 创建目录
DEMO_DIR = Path("/tmp/yolo_demo_dataset")
TRAIN_IMG_DIR = DEMO_DIR / "images" / "train"
VAL_IMG_DIR = DEMO_DIR / "images" / "val"
TRAIN_LBL_DIR = DEMO_DIR / "labels" / "train"
VAL_LBL_DIR = DEMO_DIR / "labels" / "val"

for d in [TRAIN_IMG_DIR, VAL_IMG_DIR, TRAIN_LBL_DIR, VAL_LBL_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# COCO128 有 80 类，这里用 5 类演示
CLASS_NAMES = ['person', 'bicycle', 'car', 'motorcycle', 'airplane']
COLORS = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7']

def draw_random_objects(img_array, draw, num_objects):
    """在一张图上随机画一些物体框"""
    h, w = img_array.shape[:2]
    boxes = []
    for _ in range(num_objects):
        cls_id = random.randint(0, len(CLASS_NAMES) - 1)
        # 随机生成 bbox (YOLO format: cx, cy, w, h 归一化)
        bw = random.uniform(0.05, 0.3)
        bh = random.uniform(0.05, 0.3)
        cx = random.uniform(bw/2, 1 - bw/2)
        cy = random.uniform(bh/2, 1 - bh/2)

        # 画框
        color = COLORS[cls_id]
        x1 = int((cx - bw/2) * w)
        y1 = int((cy - bh/2) * h)
        x2 = int((cx + bw/2) * w)
        y2 = int((cy + bh/2) * h)

        # 画填充
        draw.rectangle([x1, y1, x2, y2], fill=color + '40', outline=color, width=2)

        # 写类别名
        draw.text((x1 + 4, y1 + 4), CLASS_NAMES[cls_id], fill=color)

        boxes.append((cls_id, cx, cy, bw, bh))

    return boxes

def create_demo_image(img_idx, split='train'):
    """创建一张演示图片"""
    w, h = 640, 480
    img = Image.new('RGB', (w, h), color=(240, 242, 245))
    draw = ImageDraw.Draw(img)

    # 随机添加一些背景元素
    for _ in range(random.randint(5, 15)):
        x = random.randint(0, w)
        y = random.randint(0, h)
        r = random.randint(10, 30)
        color = tuple(random.randint(200, 255) for _ in range(3))
        draw.ellipse([x-r, y-r, x+r, y+r], fill=color)

    # 添加物体
    num_objects = random.randint(1, 5)
    boxes = draw_random_objects(np.array(img), draw, num_objects)

    # 保存图片
    img_file = TRAIN_IMG_DIR if split == 'train' else VAL_IMG_DIR
    img_path = img_file / f"demo_{split}_{img_idx:03d}.jpg"
    img.save(img_path, quality=85)

    # 保存标签
    lbl_file = TRAIN_LBL_DIR if split == 'train' else VAL_LBL_DIR
    lbl_path = lbl_file / f"demo_{split}_{img_idx:03d}.txt"
    with open(lbl_path, 'w') as f:
        for cls_id, cx, cy, bw, bh in boxes:
            f.write(f"{cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")

    return len(boxes)

def main():
    print("Creating demo dataset...")

    # 创建训练集 20 张
    total_objects = 0
    for i in range(20):
        num = create_demo_image(i, 'train')
        total_objects += num
        if (i + 1) % 5 == 0:
            print(f"  Created {i + 1}/20 training images")

    # 创建验证集 5 张
    for i in range(5):
        num = create_demo_image(i, 'val')
        total_objects += num
        print(f"  Created {i + 1}/5 validation images")

    print(f"\nDemo dataset created at: {DEMO_DIR}")
    print(f"  Training images: 20")
    print(f"  Validation images: 5")
    print(f"  Total objects: {total_objects}")
    print(f"  Classes: {', '.join(CLASS_NAMES)}")

    # 创建 data.yaml
    data_yaml = DEMO_DIR / "data.yaml"
    data_yaml.write_text(f"""# YOLO Demo Dataset
path: {DEMO_DIR.resolve()}
train: images/train
val: images/val

nc: {len(CLASS_NAMES)}
names: {CLASS_NAMES}
""")
    print(f"\ndata.yaml created at: {data_yaml}")

if __name__ == "__main__":
    main()
