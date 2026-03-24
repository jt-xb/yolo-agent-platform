"""
YOLO 自动标注服务
使用训练好的 YOLO 模型对图片进行自动标注
"""
import os
import random
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from backend.core.config import settings


class YOLOAutoLabeler:
    """
    YOLO 自动标注器

    使用 YOLO 模型对图片进行预测，
    将预测结果转换为 YOLO 格式标注文件
    """

    def __init__(self, model_path: str = None):
        self.model_path = model_path
        self.model = None

    def load_model(self, model_path: str = None):
        """加载 YOLO 模型"""
        if model_path and os.path.exists(model_path):
            try:
                from ultralytics import YOLO
                self.model = YOLO(model_path)
                self.model_path = model_path
                print(f"YOLO 自动标注模型加载成功: {model_path}")
                return True
            except Exception as e:
                print(f"加载 YOLO 模型失败: {e}")
                return False
        return False

    def predict(self, image_path: str, conf_threshold: float = 0.25) -> List[Dict]:
        """
        对单张图片进行预测

        Returns:
            List of {"class_id": int, "class_name": str, "bbox": [x_center, y_center, w, h], "confidence": float}
        """
        if not self.model:
            return []

        try:
            results = self.model.predict(
                source=image_path,
                conf=conf_threshold,
                verbose=False,
                device='cpu',
            )

            predictions = []
            if results and len(results) > 0:
                r = results[0]
                if r.boxes is not None:
                    for box in r.boxes:
                        cls_id = int(box.cls.item())
                        conf = float(box.conf.item())
                        # xywhn: normalized [x_center, y_center, w, h]
                        xywhn = box.xywhn[0].tolist()
                        predictions.append({
                            "class_id": cls_id,
                            "class_name": self.model.names.get(cls_id, f"class_{cls_id}"),
                            "bbox": [round(v, 6) for v in xywhn],
                            "confidence": round(conf, 3),
                        })

            return predictions

        except Exception as e:
            print(f"预测失败 {image_path}: {e}")
            return []

    def auto_label_dataset(
        self,
        image_paths: List[str],
        class_names: List[str],
        conf_threshold: float = 0.25,
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        对整个数据集进行自动标注

        Returns:
            {
                "total": int,
                "annotated": int,
                "failed": int,
                "total_objects": int,
                "results": {image_path: [Prediction, ...]}
            }
        """
        results = {}
        total = len(image_paths)
        annotated = 0
        failed = 0
        total_objects = 0

        for i, img_path in enumerate(image_paths):
            try:
                preds = self.predict(img_path, conf_threshold)
                results[img_path] = preds
                if preds:
                    annotated += 1
                    total_objects += len(preds)
            except Exception as e:
                failed += 1
                results[img_path] = []

            if progress_callback:
                progress_callback(i + 1, total)

        return {
            "total": total,
            "annotated": annotated,
            "failed": failed,
            "total_objects": total_objects,
            "results": results,
        }

    def save_labels(
        self,
        predictions: Dict[str, List[Dict]],
        output_label_dir: str,
        class_names: List[str]
    ) -> Dict[str, str]:
        """
        将预测结果保存为 YOLO 格式标签文件

        Returns:
            {image_path: label_file_path}
        """
        os.makedirs(output_label_dir, exist_ok=True)
        saved = {}

        for img_path, preds in predictions.items():
            img_name = Path(img_path).stem
            label_path = os.path.join(output_label_dir, f"{img_name}.txt")

            lines = []
            for p in preds:
                bbox = p["bbox"]
                lines.append(f"{p['class_id']} {bbox[0]:.6f} {bbox[1]:.6f} {bbox[2]:.6f} {bbox[3]:.6f}")

            with open(label_path, 'w') as f:
                f.write('\n'.join(lines))

            saved[img_path] = label_path

        return saved


# 全局实例
_auto_labeler: Optional[YOLOAutoLabeler] = None

def get_auto_labeler() -> YOLOAutoLabeler:
    global _auto_labeler
    if _auto_labeler is None:
        _auto_labeler = YOLOAutoLabeler()
    return _auto_labeler
