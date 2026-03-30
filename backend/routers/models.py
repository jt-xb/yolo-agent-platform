"""
模型管理 API
"""
import os
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.core.database import get_db, GeneratedModel, Task
from backend.core.config import settings
from backend.services.inference import get_inference_service

router = APIRouter(prefix="/api/models", tags=["模型管理"])


@router.get("/")
def list_models(db: Session = Depends(get_db)):
    """列出所有生成的模型"""
    models = db.query(GeneratedModel).all()
    return {"models": [m.to_dict() for m in models]}


@router.get("/{task_id}")
def get_model(task_id: str, db: Session = Depends(get_db)):
    """获取指定任务的模型信息"""
    model = db.query(GeneratedModel).filter(GeneratedModel.task_id == task_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    return model.to_dict()


@router.post("/{task_id}/deploy")
def deploy_model(task_id: str, db: Session = Depends(get_db)):
    """
    部署模型到推理服务
    """
    model = db.query(GeneratedModel).filter(GeneratedModel.task_id == task_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")

    inference = get_inference_service()
    result = inference.deploy_model(task_id, model.model_path)

    if result["success"] and not result.get("already_deployed"):
        model.is_deployed = True
        model.deployed_at = __import__("datetime").datetime.utcnow()
        db.commit()

    return result


@router.post("/{task_id}/undeploy")
def undeploy_model(task_id: str, db: Session = Depends(get_db)):
    """卸载模型"""
    model = db.query(GeneratedModel).filter(GeneratedModel.task_id == task_id).first()
    if model:
        model.is_deployed = False
        db.commit()

    inference = get_inference_service()
    return inference.undeploy_model(task_id)


@router.get("/{task_id}/status")
def get_model_status(task_id: str, db: Session = Depends(get_db)):
    """获取模型部署状态"""
    model = db.query(GeneratedModel).filter(GeneratedModel.task_id == task_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")

    inference = get_inference_service()
    deployment = inference.get_deployment_status(task_id)

    return {
        "task_id": task_id,
        "model_name": model.name,
        "is_deployed": model.is_deployed,
        "deployment": deployment,
    }


@router.post("/{task_id}/infer")
def infer_model(
    task_id: str,
    image_urls: list[str],
    db: Session = Depends(get_db),
):
    """
    对指定图片执行推理
    """
    inference = get_inference_service()
    result = inference.predict(task_id, image_urls)
    return result


@router.post("/{task_id}/infer-image")
async def infer_model_image(
    task_id: str,
    file: UploadFile,
    db: Session = Depends(get_db),
):
    """
    上传图片执行推理，返回带检测框的标注图片

    POST /api/models/{task_id}/infer-image
    FormData: file (图片文件)
    """
    import tempfile

    model = db.query(GeneratedModel).filter(GeneratedModel.task_id == task_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")

    model_path = settings.models_dir / task_id / "weights" / "best.pt"
    if not model_path.exists():
        model_path = settings.models_dir / task_id / "weights" / "last.pt"
    if not model_path.exists():
        return {"success": False, "message": "模型文件不存在"}

    # 保存上传的图片到临时文件
    suffix = Path(file.filename).suffix.lower() if file.filename else ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        from ultralytics import YOLO
        import cv2
        import numpy as np

        yolo = YOLO(str(model_path))
        results = yolo.predict(
            source=tmp_path,
            conf=0.25,
            verbose=False,
            device='cpu',
        )

        if not results or len(results) == 0:
            return {"success": False, "message": "推理失败，无结果"}

        r = results[0]
        img = cv2.imread(tmp_path)
        if img is None:
            return {"success": False, "message": "图片读取失败"}

        h, w = img.shape[:2]
        detections = []

        if r.boxes is not None:
            for box in r.boxes:
                cls_id = int(box.cls.item())
                conf = float(box.conf.item())
                xyxy = box.xyxy[0].cpu().numpy()
                x1, y1, x2, y2 = [int(v) for v in xyxy]
                label = yolo.names.get(cls_id, f"class_{cls_id}")
                # 画框
                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                text = f"{label} {conf:.2f}"
                (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(img, (x1, y1 - th - 4), (x1 + tw, y1), (0, 255, 0), -1)
                cv2.putText(img, text, (x1, y1 - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
                # YOLO format
                cx, cy = (x1 + x2) / 2 / w, (y1 + y2) / 2 / h
                bw, bh = (x2 - x1) / w, (y2 - y1) / h
                detections.append({
                    "class": label,
                    "confidence": round(conf, 3),
                    "bbox": [round(cx, 6), round(cy, 6), round(bw, 6), round(bh, 6)],
                    "bbox_pixel": [x1, y1, x2, y2],
                })

        # 保存带标注的图片
        annotated_path = tempfile.mktemp(suffix=".jpg")
        cv2.imwrite(annotated_path, img)

        return FileResponse(
            annotated_path,
            media_type="image/jpeg",
            filename=f"annotated_{Path(file.filename or 'image').stem}.jpg",
        )

    except Exception as e:
        return {"success": False, "message": f"推理失败: {str(e)}"}
    finally:
        os.unlink(tmp_path)


@router.post("/{task_id}/batch-infer")
def batch_infer_model(
    task_id: str,
    dataset_path: Optional[str] = None,
    max_images: int = 20,
):
    """
    批量推理测试
    """
    inference = get_inference_service()
    if dataset_path:
        result = inference.batch_predict(task_id, dataset_path, max_images)
    else:
        result = {
            "success": False,
            "message": "需要提供 dataset_path 参数"
        }
    return result


@router.get("/{task_id}/download")
def download_model(task_id: str, db: Session = Depends(get_db)):
    """下载模型文件"""
    model = db.query(GeneratedModel).filter(GeneratedModel.task_id == task_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")

    # 使用数据库中存储的实际模型路径
    model_path = Path(model.model_path) if model.model_path else None

    # 如果数据库路径不存在，尝试构造路径
    if not model_path or not model_path.exists():
        model_path = settings.models_dir / task_id / "weights" / "best.pt"
        if not model_path.exists():
            model_path = settings.models_dir / task_id / "weights" / "last.pt"

    if not model_path or not model_path.exists():
        raise HTTPException(status_code=404, detail="模型文件不存在，请先完成训练")

    # 提取文件名用于下载
    filename = model_path.name or f"{task_id}.pt"

    return FileResponse(
        str(model_path),
        media_type="application/octet-stream",
        filename=filename
    )


@router.delete("/{task_id}")
def delete_model(task_id: str, db: Session = Depends(get_db)):
    """删除模型"""
    model = db.query(GeneratedModel).filter(GeneratedModel.task_id == task_id).first()
    if model:
        db.delete(model)
        db.commit()

    # 卸载推理服务
    inference = get_inference_service()
    inference.undeploy_model(task_id)

    return {"success": True, "message": f"模型 {task_id} 已删除"}


@router.get("/{task_id}/export")
def export_model(task_id: str, format: str = "onnx", db: Session = Depends(get_db)):
    """
    导出模型为指定格式（支持 onnx, torchscript, tflite 等）

    GET /api/models/{task_id}/export?format=onnx
    """
    model = db.query(GeneratedModel).filter(GeneratedModel.task_id == task_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")

    model_path = settings.models_dir / task_id / "weights" / "best.pt"
    if not model_path.exists():
        # 尝试 last.pt
        model_path = settings.models_dir / task_id / "weights" / "last.pt"

    if not model_path.exists():
        return {"success": False, "message": "模型文件不存在，请先完成训练"}

    try:
        from ultralytics import YOLO

        yolo_model = YOLO(str(model_path))
        export_path = yolo_model.export(format=format)

        # 导出后的文件路径
        exported_file = Path(export_path) if isinstance(export_path, str) else export_path

        if not exported_file.exists():
            return {"success": False, "message": f"导出失败，文件未生成"}

        file_size = exported_file.stat().st_size
        size_str = f"{file_size / (1024*1024):.1f} MB"

        return {
            "success": True,
            "task_id": task_id,
            "format": format,
            "exported_path": str(exported_file),
            "file_size": size_str,
            "download_url": f"/api/models/{task_id}/export-file?format={format}",
        }
    except Exception as e:
        return {"success": False, "message": f"导出失败: {str(e)}"}


@router.get("/{task_id}/export-file")
def download_exported_model(task_id: str, format: str = "onnx"):
    """下载导出的模型文件"""
    from pathlib import Path

    model_dir = settings.models_dir / task_id / "weights"
    # 查找导出的文件
    candidates = list(model_dir.glob(f"*.{format}"))
    if not candidates:
        raise HTTPException(status_code=404, detail=f"找不到 {format} 格式的导出文件")

    exported_file = candidates[-1]  # 最新导出的
    return FileResponse(
        str(exported_file),
        media_type="application/octet-stream",
        filename=f"{task_id}_best.{format}"
    )
