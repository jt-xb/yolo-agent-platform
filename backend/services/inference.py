"""
推理服务
模型部署后提供 RESTful 推理接口
"""
import os
import time
import random
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from backend.core.config import settings


class InferenceStatus(Enum):
    """推理服务状态"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"


@dataclass
class DetectionResult:
    """单图检测结果"""
    image_path: str
    detections: List[Dict[str, Any]]  # [{"class": "person", "bbox": [x1,y1,x2,y2], "confidence": 0.95}]
    inference_time_ms: float

    def to_dict(self):
        return {
            "image_path": self.image_path,
            "detections": self.detections,
            "inference_time_ms": round(self.inference_time_ms, 2),
            "detection_count": len(self.detections),
        }


class InferenceService:
    """
    推理服务（模拟版本）

    真实版本会加载 YOLO 模型并执行推理：
    ```python
    from ultralytics import YOLO
    model = YOLO('best.pt')
    results = model.predict(source='image.jpg', device='mlu')
    ```

    当前模拟：返回合理的随机检测结果
    """

    def __init__(self):
        self.deployed_models: Dict[str, Dict] = {}  # task_id -> model_info
        self.inference_count: Dict[str, int] = {}  # task_id -> count

    def deploy_model(self, task_id: str, model_path: str) -> Dict[str, Any]:
        """
        部署模型到推理服务

        Returns:
            {"success": bool, "endpoint": str, "message": str}
        """
        if task_id in self.deployed_models and self.deployed_models[task_id]["status"] == InferenceStatus.RUNNING.value:
            return {
                "success": True,
                "endpoint": f"/api/infer/{task_id}",
                "message": f"模型 {task_id} 已部署",
                "already_deployed": True
            }

        # 模拟加载模型时间
        time.sleep(0.5)

        self.deployed_models[task_id] = {
            "task_id": task_id,
            "model_path": model_path,
            "status": InferenceStatus.RUNNING.value,
            "deployed_at": datetime.now().isoformat(),
            "model_type": "yolov8",
            "inference_count": 0,
        }
        self.inference_count[task_id] = 0

        return {
            "success": True,
            "endpoint": f"/api/infer/{task_id}",
            "message": f"模型 {task_id} 部署成功"
        }

    def undeploy_model(self, task_id: str) -> Dict[str, Any]:
        """卸载模型"""
        if task_id in self.deployed_models:
            del self.deployed_models[task_id]
            if task_id in self.inference_count:
                del self.inference_count[task_id]
            return {"success": True, "message": f"模型 {task_id} 已卸载"}
        return {"success": False, "message": "模型未部署"}

    def get_deployment_status(self, task_id: str) -> Optional[Dict]:
        """获取部署状态"""
        return self.deployed_models.get(task_id)

    def predict(self, task_id: str, image_paths: List[str]) -> Dict[str, Any]:
        """
        对图片执行推理

        Returns:
            {
                "success": bool,
                "task_id": task_id,
                "results": [DetectionResult, ...],
                "total_detections": int
            }
        """
        if task_id not in self.deployed_models:
            return {
                "success": False,
                "message": f"模型 {task_id} 未部署，请先部署模型",
            }

        results = []
        total_detections = 0

        for img_path in image_paths:
            start_time = time.time()

            # 模拟 YOLO 推理（CPU/GPU 上约 20-50ms 每张图）
            time.sleep(random.uniform(0.02, 0.05))

            # 模拟随机检测结果
            num_detections = random.randint(0, 8)
            detections = []
            for _ in range(num_detections):
                # 随机生成一个检测框
                x1 = random.uniform(0.05, 0.6)
                y1 = random.uniform(0.05, 0.6)
                w = random.uniform(0.05, 0.3)
                h = random.uniform(0.05, 0.3)
                detections.append({
                    "class": random.choice(["person", "helmet", "car", "fire", "smoke"]),
                    "bbox": [round(x1, 4), round(y1, 4), round(w, 4), round(h, 4)],
                    "confidence": round(random.uniform(0.5, 0.99), 3)
                })

            inference_time = (time.time() - start_time) * 1000
            result = DetectionResult(img_path, detections, inference_time)
            results.append(result.to_dict())
            total_detections += num_detections

        # 更新计数
        self.inference_count[task_id] = self.inference_count.get(task_id, 0) + len(image_paths)
        self.deployed_models[task_id]["inference_count"] = self.inference_count[task_id]

        return {
            "success": True,
            "task_id": task_id,
            "results": results,
            "total_detections": total_detections,
            "model_status": self.deployed_models[task_id]["status"],
        }

    def batch_predict(self, task_id: str, dataset_path: str, max_images: int = 20) -> Dict[str, Any]:
        """
        批量推理测试

        从数据集目录中随机采样图片进行推理测试
        """
        # 查找图片文件
        image_extensions = {".jpg", ".jpeg", ".png", ".bmp"}
        image_files = []
        for ext in image_extensions:
            image_files.extend(Path(dataset_path).rglob(f"*{ext}"))

        # 随机采样
        import random
        sample_images = random.sample(image_files, min(max_images, len(image_files)))

        result = self.predict(task_id, [str(p) for p in sample_images])

        if result["success"]:
            result["sampled_from"] = len(image_files)
            result["sampled_count"] = len(sample_images)
            result["detection_rate"] = round(
                sum(1 for r in result["results"] if r["detection_count"] > 0) / len(result["results"]) * 100, 1
            ) if result["results"] else 0

        return result

    def list_deployed(self) -> List[Dict]:
        """列出所有已部署模型"""
        return list(self.deployed_models.values())


# 全局实例
_inference_service: Optional[InferenceService] = None

def get_inference_service() -> InferenceService:
    global _inference_service
    if _inference_service is None:
        _inference_service = InferenceService()
    return _inference_service
