"""
独立训练服务（FastAPI on port 8001）
专门处理 YOLO 模型训练，支持 GPU 独占

前端通过 http://train:8001 调用
"""
import os
import sys
import json
import threading
import queue as sync_queue
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional

import torch
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# 确保 backend 模块在路径中
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.config import settings
from backend.services.real_yolo_training import (
    RealYOLOTrainer,
    start_real_training,
    stop_training,
    get_training_progress,
)

# ============================================
# FastAPI 应用
# ============================================

app = FastAPI(
    title="YOLO Training Service",
    version="0.1.0",
    description="独立训练服务 - 处理 YOLO 模型训练",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# 请求模型
# ============================================

class TrainStartRequest(BaseModel):
    task_id: str
    data_yaml: Optional[str] = None
    model_name: str = "yolov8n"
    epochs: int = 50
    batch_size: int = 16
    image_size: int = 640
    device: str = "cpu"


class TrainStopRequest(BaseModel):
    task_id: str


# ============================================
# 训练状态管理（内存）
# ============================================

_training_jobs: Dict[str, Dict[str, Any]] = {}
_job_queues: Dict[str, sync_queue.Queue] = {}
_job_events: Dict[str, threading.Event] = {}


def _emit_event(task_id: str, event_type: str, data: Any):
    """向 SSE 队列推送事件"""
    q = _job_queues.get(task_id)
    if q:
        try:
            q.put_nowait((event_type, json.dumps(data, ensure_ascii=False)))
        except sync_queue.Full:
            pass


def _run_training_in_thread(task_id: str, config: Dict[str, Any]):
    """后台线程执行训练"""
    from backend.services.real_yolo_training import RealYOLOTrainer

    trainer = RealYOLOTrainer(
        task_id=task_id,
        data_yaml=config.get("data_yaml", ""),
        model_name=config.get("model_name", "yolov8n"),
        epochs=config.get("epochs", 50),
        batch_size=config.get("batch_size", 16),
        image_size=config.get("image_size", 640),
        device=config.get("device", "cpu"),
    )

    _training_jobs[task_id] = {
        "task_id": task_id,
        "trainer": trainer,
        "status": "training",
        "current_epoch": 0,
        "best_map50": 0.0,
        "results": [],
    }

    _emit_event(task_id, "status", {"status": "training", "message": "训练已启动"})

    try:
        result = trainer.train()

        job = _training_jobs.get(task_id, {})
        job["status"] = "completed" if result.get("success") else "failed"
        job["result"] = result

        if result.get("success"):
            _emit_event(task_id, "status", {
                "status": "completed",
                "metrics": result.get("metrics", {}),
                "model_path": result.get("model_path"),
            })
        else:
            _emit_event(task_id, "status", {
                "status": "failed",
                "error": result.get("error", "未知错误"),
            })

    except Exception as e:
        job = _training_jobs.get(task_id, {})
        job["status"] = "failed"
        job["error"] = str(e)
        _emit_event(task_id, "status", {"status": "failed", "error": str(e)})

    # 通知结束
    _emit_end(task_id)


def _emit_end(task_id: str):
    """通知 SSE 连接结束"""
    q = _job_queues.get(task_id)
    ev = _job_events.get(task_id)
    if q and ev:
        try:
            q.put_nowait(("__END__", ""))
            ev.set()
        except sync_queue.Full:
            pass


# ============================================
# API 端点
# ============================================

@app.post("/api/train/start")
def start_training(req: TrainStartRequest):
    """启动训练任务"""
    task_id = req.task_id

    if task_id in _training_jobs and _training_jobs[task_id].get("status") == "training":
        raise HTTPException(status_code=400, detail="训练任务正在进行中")

    # 创建 SSE 队列
    q = sync_queue.Queue(maxsize=100)
    ev = threading.Event()
    _job_queues[task_id] = q
    _job_events[task_id] = ev

    config = {
        "data_yaml": req.data_yaml or "",
        "model_name": req.model_name,
        "epochs": req.epochs,
        "batch_size": req.batch_size,
        "image_size": req.image_size,
        "device": req.device,
    }

    # 启动后台线程
    thread = threading.Thread(target=_run_training_in_thread, args=(task_id, config))
    thread.daemon = True
    thread.start()

    return {
        "success": True,
        "task_id": task_id,
        "message": f"训练已启动（设备={req.device}，epochs={req.epochs}）",
    }


@app.post("/api/train/stop")
def stop_training_endpoint(req: TrainStopRequest):
    """停止训练任务"""
    task_id = req.task_id

    if task_id not in _training_jobs:
        raise HTTPException(status_code=404, detail="训练任务不存在")

    trainer = _training_jobs[task_id].get("trainer")
    if trainer:
        trainer.stop()
        _training_jobs[task_id]["status"] = "stopped"
        _emit_event(task_id, "status", {"status": "stopped", "message": "训练已停止"})
        _emit_end(task_id)

    return {"success": True, "task_id": task_id, "message": "训练已停止"}


@app.get("/api/train/status/{task_id}")
def get_status(task_id: str):
    """获取训练状态"""
    if task_id not in _training_jobs:
        raise HTTPException(status_code=404, detail="训练任务不存在")

    job = _training_jobs[task_id]
    trainer = job.get("trainer")

    return {
        "task_id": task_id,
        "status": job.get("status", "unknown"),
        "current_epoch": trainer.current_epoch if trainer else 0,
        "best_map50": trainer.best_map50 if trainer else 0.0,
        "result": job.get("result"),
    }


@app.get("/api/train/stream/{task_id}")
def stream_training(task_id: str):
    """SSE 实时流"""
    from starlette.responses import StreamingResponse

    q = sync_queue.Queue(maxsize=200)
    ev = threading.Event()
    _job_queues[task_id] = q
    _job_events[task_id] = ev

    async def event_generator():
        yield "event: connected\ndata: \n\n"
        try:
            while True:
                try:
                    item = q.get(timeout=60)
                except sync_queue.Empty:
                    yield "event: heartbeat\ndata: \n\n"
                    continue

                if item == "__END__" or (isinstance(item, tuple) and item[0] == "__END__"):
                    yield "event: end\ndata: \n\n"
                    break

                etype, edata = item
                yield f"event: {etype}\ndata: {edata}\n\n"
        finally:
            _job_queues.pop(task_id, None)
            _job_events.pop(task_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/health")
def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "train-service",
        "gpu_available": torch.cuda.is_available(),
        "gpu_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
    }


@app.get("/")
def root():
    """根路径"""
    return {
        "service": "YOLO Training Service",
        "version": "0.1.0",
        "gpu_available": torch.cuda.is_available(),
    }


# ============================================
# 主入口
# ============================================

if __name__ == "__main__":
    port = int(os.getenv("TRAIN_PORT", 8001))
    uvicorn.run(
        "backend.train_service:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
