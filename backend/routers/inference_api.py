"""
推理 API - 独立的推理接口
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.inference import get_inference_service

router = APIRouter(prefix="/api/infer", tags=["推理服务"])


class InferRequest(BaseModel):
    images: list[str]  # 图片URL或路径列表


@router.post("/{task_id}")
def infer(task_id: str, request: InferRequest):
    """
    对指定模型发起推理请求

    请求体:
    {
        "images": ["http://xxx.jpg", "/path/to/local/img.png"]
    }
    """
    inference = get_inference_service()
    result = inference.predict(task_id, request.images)
    return result


@router.get("/{task_id}/health")
def infer_health(task_id: str):
    """检查推理服务健康状态"""
    inference = get_inference_service()
    deployment = inference.get_deployment_status(task_id)

    if not deployment:
        raise HTTPException(status_code=404, detail="模型未部署")

    return {
        "task_id": task_id,
        "status": deployment["status"],
        "inference_count": deployment.get("inference_count", 0),
    }
