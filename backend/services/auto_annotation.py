"""
自动标注服务
模拟 Grounding DINO + SAM 的标注流程
实际部署时替换为真实模型调用
"""
import os
import json
import uuid
import random
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from backend.core.config import settings


class AnnotationResult:
    """标注结果"""
    def __init__(self, image_path: str, bboxes: List[Dict]):
        self.image_path = image_path
        self.bboxes = bboxes  # [{"class": "person", "bbox": [x1, y1, w, h], "confidence": 0.95}]

    def to_yolo_format(self, class_names: List[str]) -> str:
        """转换为 YOLO txt 格式"""
        lines = []
        for box in self.bboxes:
            cls_id = class_names.index(box["class"]) if box["class"] in class_names else 0
            x, y, w, h = box["bbox"]
            lines.append(f"{cls_id} {x:.6f} {y:.6f} {w:.6f} {h:.6f}")
        return "\n".join(lines)

    def to_dict(self):
        return {
            "image_path": self.image_path,
            "bboxes": self.bboxes,
        }


class AutoAnnotationService:
    """
    自动标注服务（模拟版本）

    真实版本会调用：
    1. Grounding DINO - 根据文本描述定位图像中的目标
    2. SAM (Segment Anything) - 生成精确的分割掩码
    3. 将掩码转换为 YOLO 格式的边界框

    当前模拟：随机生成符合常理的标注结果
    """

    # 常见的检测目标和对应的典型尺寸/位置分布
    DETECTION_TEMPLATES = {
        "person": {
            "count_range": (1, 8),
            "bbox_size": (0.05, 0.25),  # 占图像比例
            "common_positions": ["center", "lower", "scattered"]
        },
        "helmet": {
            "count_range": (0, 5),  # 可能没有人戴头盔
            "bbox_size": (0.03, 0.08),
            "common_positions": ["top_of_person"]
        },
        "head": {
            "count_range": (0, 8),
            "bbox_size": (0.03, 0.08),
            "common_positions": ["upper", "scattered"]
        },
        "car": {
            "count_range": (0, 12),
            "bbox_size": (0.1, 0.4),
            "common_positions": ["bottom", "parked"]
        },
        "fire": {
            "count_range": (0, 3),
            "bbox_size": (0.05, 0.2),
            "common_positions": ["random"]
        },
        "smoke": {
            "count_range": (0, 4),
            "bbox_size": (0.08, 0.3),
            "common_positions": ["top", "rising"]
        },
    }

    def __init__(self):
        self.annotation_dir = settings.datasets_dir / "annotations"
        self.annotation_dir.mkdir(parents=True, exist_ok=True)

    def annotate_images(
        self,
        task_description: str,
        class_names: List[str],
        image_paths: List[str],
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        标注一批图片

        Args:
            task_description: 任务描述（如"检测未佩戴安全帽的人员"）
            class_names: 类别列表
            image_paths: 图片路径列表
            progress_callback: 进度回调函数 callback(current, total)

        Returns:
            {
                "total_images": 100,
                "annotated": 95,
                "failed": 5,
                "total_objects": 420,
                "results": [AnnotationResult, ...]
            }
        """
        results = []
        total = len(image_paths)
        annotated = 0
        failed = 0
        total_objects = 0

        for i, img_path in enumerate(image_paths):
            try:
                # 模拟 Grounding DINO 处理时间
                import time
                time.sleep(0.05)  # 每张图约50ms

                result = self._annotate_single_image(task_description, class_names, img_path)
                results.append(result)
                annotated += 1
                total_objects += len(result.bboxes)

            except Exception as e:
                failed += 1
                print(f"标注失败 {img_path}: {e}")

            if progress_callback:
                progress_callback(i + 1, total)

        return {
            "total_images": total,
            "annotated": annotated,
            "failed": failed,
            "total_objects": total_objects,
            "results": [r.to_dict() for r in results],
        }

    def _annotate_single_image(
        self,
        task_description: str,
        class_names: List[str],
        image_path: str
    ) -> AnnotationResult:
        """
        对单张图片进行标注（模拟）
        真实版本：调用 Grounding DINO + SAM
        """
        # 根据任务描述和类别决定检测数量
        detected_classes = []

        for cls in class_names:
            template = self.DETECTION_TEMPLATES.get(cls.lower(), {
                "count_range": (0, 3),
                "bbox_size": (0.05, 0.15),
                "common_positions": ["random"]
            })

            count_range = template["count_range"]
            count = random.randint(count_range[0], count_range[1])

            for _ in range(count):
                # 生成边界框
                x, y, w, h = self._generate_bbox(template)
                confidence = random.uniform(0.65, 0.99)

                detected_classes.append({
                    "class": cls,
                    "bbox": [x, y, w, h],
                    "confidence": round(confidence, 3),
                    "annotated_by": "grounding_dino_sam"
                })

        # 按 confidence 排序，低于阈值的过滤掉
        detected_classes = [d for d in detected_classes if d["confidence"] >= 0.6]

        return AnnotationResult(image_path, detected_classes)

    def _generate_bbox(self, template: Dict) -> List[float]:
        """生成符合模板的边界框（归一化坐标 0-1）"""
        size_range = template["bbox_size"]
        w = random.uniform(size_range[0], size_range[1])
        h = random.uniform(size_range[0], size_range[1])

        x = random.uniform(0.05, 0.9 - w)
        y = random.uniform(0.1, 0.85 - h)

        return [round(x, 6), round(y, 6), round(w, 6), round(h, 6)]

    def save_yolo_format(
        self,
        task_id: str,
        results: List[AnnotationResult],
        class_names: List[str],
        output_dir: str
    ) -> Dict[str, Any]:
        """
        将标注结果保存为 YOLO 数据集格式

        output_dir/
        ├── images/
        │   ├── train/
        │   └── val/
        └── labels/
            ├── train/
            └── val/
        """
        from sklearn.model_selection import train_test_split

        # 分离图片路径
        all_images = [r.image_path for r in results]

        # 划分训练集和验证集（8:2）
        train_images, val_images = train_test_split(
            all_images, test_size=0.2, random_state=42
        )

        # 创建目录
        splits = {
            "train": train_images,
            "val": val_images
        }

        saved = {"train": 0, "val": 0, "total_labels": 0}

        for split_name, images in splits.items():
            img_out_dir = Path(output_dir) / "images" / split_name
            label_out_dir = Path(output_dir) / "labels" / split_name
            img_out_dir.mkdir(parents=True, exist_ok=True)
            label_out_dir.mkdir(parents=True, exist_ok=True)

            # 建立图片路径到结果的映射
            result_map = {r.image_path: r for r in results}

            for img_path in images:
                result = result_map.get(img_path)
                if not result:
                    continue

                # 复制图片
                import shutil
                new_img_path = img_out_dir / Path(img_path).name
                shutil.copy(img_path, new_img_path)

                # 写标签
                label_path = label_out_dir / f"{Path(img_path).stem}.txt"
                yolo_content = result.to_yolo_format(class_names)
                if yolo_content.strip():
                    label_path.write_text(yolo_content)
                    saved["total_labels"] += 1

                saved[split_name] += 1

        return {
            "output_dir": output_dir,
            "train_count": saved["train"],
            "val_count": saved["val"],
            "total_labels": saved["total_labels"],
            "data_yaml": self._generate_data_yaml(
                task_id, class_names, output_dir
            )
        }

    def _generate_data_yaml(self, task_id: str, class_names: List[str], data_root: str) -> str:
        """生成 data.yaml"""
        import yaml
        config = {
            "path": data_root,
            "train": "images/train",
            "val": "images/val",
            "nc": len(class_names),
            "names": {i: name for i, name in enumerate(class_names)}
        }
        yaml_path = Path(data_root) / "data.yaml"
        with open(yaml_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)
        return str(yaml_path)


# 全局实例
_auto_annotation_service: Optional[AutoAnnotationService] = None

def get_auto_annotation_service() -> AutoAnnotationService:
    global _auto_annotation_service
    if _auto_annotation_service is None:
        _auto_annotation_service = AutoAnnotationService()
    return _auto_annotation_service
