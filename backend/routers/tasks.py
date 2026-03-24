"""
任务管理 API 路由
"""
import uuid
import time
import threading
from datetime import datetime
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from backend.core.database import get_db, Task, TaskLog, TaskMetric, GeneratedModel
from backend.core.config import settings
from backend.services.training_loop import (
    start_agent_training_loop,
    get_agent_training_loop,
    AgentTrainingLoop,
    IterationDecision,
)

router = APIRouter(prefix="/api/tasks", tags=["任务管理"])

# ============================================
# SSE 实时日志：threading.Queue 跨线程安全通信
# ============================================
import asyncio
import queue as sync_queue
import json
import threading
from starlette.responses import StreamingResponse

# task_id → (sync_queue.Queue, threading.Event for end signal)
_task_queues: dict[str, tuple[sync_queue.Queue, threading.Event]] = {}


@router.get("/{task_id}/stream")
async def stream_task_events(task_id: str):
    """
    SSE 实时流：推送训练日志、指标、状态更新

    前端 EventSource 接收示例：
      const es = new EventSource(`/api/tasks/${taskId}/stream`)
      es.addEventListener('log', e => appendLog(e.data))
      es.addEventListener('metrics', e => updateMetrics(JSON.parse(e.data)))
      es.addEventListener('status', e => updateStatus(e.data))
      es.addEventListener('end', () => es.close())
    """
    q: sync_queue.Queue = sync_queue.Queue()
    end_event: threading.Event = threading.Event()
    _task_queues[task_id] = (q, end_event)

    async def event_generator():
        try:
            yield "event: connected\ndata: \n\n"
            while True:
                try:
                    item = q.get(timeout=60)
                except sync_queue.Empty:
                    yield "event: heartbeat\ndata: \n\n"
                    continue

                if item == "__END__":
                    yield "event: end\ndata: \n\n"
                    break

                etype, edata = item
                yield f"event: {etype}\ndata: {edata}\n\n"
        finally:
            _task_queues.pop(task_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def emit_task_event(task_id: str, event_type: str, data: Any):
    """向 SSE 队列推送事件（线程安全，供 _run_agent_loop_background 调用）"""
    entry = _task_queues.get(task_id)
    if entry:
        q, _ = entry
        try:
            q.put_nowait((event_type, json.dumps(data, ensure_ascii=False)))
        except sync_queue.Full:
            pass


def emit_task_end(task_id: str):
    """通知 SSE 连接结束"""
    entry = _task_queues.get(task_id)
    if entry:
        _, end_event = entry
        end_event.set()
        try:
            entry[0].put_nowait("__END__")
        except sync_queue.Full:
            pass


# ============================================
# 辅助函数
# ============================================

def _create_task_log(db: Session, task_id: str, level: str, message: str):
    log = TaskLog(task_id=task_id, level=level, message=message)
    db.add(log)
    db.commit()
    # 推送到 SSE 实时流
    emit_task_event(task_id, "log", {"level": level, "message": message, "ts": datetime.now().strftime("%H:%M:%S")})


def _update_task_progress(db: Session, task: Task, progress: float, status: str = None):
    task.progress = progress
    if status:
        task.status = status
    db.commit()


def _run_agent_loop_background(task_id: str, description: str, class_names: List[str]):
    """
    后台运行 Agent 训练循环（真正的训练→评估→迭代流程）
    """
    from backend.core.database import SessionLocal

    db = SessionLocal()
    try:
        # 启动 Agent 训练循环
        loop = start_agent_training_loop(task_id, description, class_names)

        task = db.query(Task).filter(Task.task_id == task_id).first()
        if not task:
            return

        task.status = "training"
        task.started_at = datetime.utcnow()
        db.commit()

        # 训练循环进度回调
        def progress_callback(iteration_data: dict, current_iter: int, total_iters: int):
            # 计算总体进度
            iter_progress = (current_iter / total_iters) * 100
            task.progress = min(iter_progress * 0.9, 90)  # 留10%给最后收尾
            task.map50 = iteration_data.get("metrics", {}).get("map50")
            task.map50_95 = iteration_data.get("metrics", {}).get("map50_95")
            task.precision = iteration_data.get("metrics", {}).get("precision")
            task.recall = iteration_data.get("metrics", {}).get("recall")
            db.commit()

            # 记录日志
            for log_msg in iteration_data.get("logs", []):
                _create_task_log(db, task_id, "info", log_msg)

            # 推送指标更新（SSE）
            metrics = iteration_data.get("metrics", {})
            if metrics.get("map50"):
                emit_task_event(task_id, "metrics", {
                    "iteration": current_iter,
                    "total": total_iters,
                    "progress": round(min((current_iter / total_iters) * 100, 95), 1),
                    "map50": metrics.get("map50"),
                    "map50_95": metrics.get("map50_95"),
                    "precision": metrics.get("precision"),
                    "recall": metrics.get("recall"),
                    "train_loss": metrics.get("train_loss"),
                    "val_loss": metrics.get("val_loss"),
                })

            # 记录指标
            if iteration_data.get("metrics", {}).get("map50"):
                metric = TaskMetric(
                    task_id=task_id,
                    epoch=current_iter,
                    map50=iteration_data["metrics"].get("map50"),
                    map50_95=iteration_data["metrics"].get("map50_95"),
                    precision=iteration_data["metrics"].get("precision"),
                    recall=iteration_data["metrics"].get("recall"),
                    train_loss=iteration_data["metrics"].get("train_loss"),
                    val_loss=iteration_data["metrics"].get("val_loss"),
                )
                db.add(metric)
                db.commit()

        # 执行训练循环
        result = loop.run(progress_callback=progress_callback)

        # 训练结束，更新状态
        task = db.query(Task).filter(Task.task_id == task_id).first()
        if task:
            task.progress = 100.0
            task.status = "completed"
            task.completed_at = datetime.utcnow()

            # 保存最优结果
            best = result.get("best_metrics", {})
            task.map50 = best.get("map50")
            task.map50_95 = best.get("map50_95")
            task.precision = best.get("precision")
            task.recall = best.get("recall")
            task.output_model_path = result.get("final_model_path")

            _create_task_log(db, task_id, "info", f"🎉 训练完成！共迭代 {result['total_iterations']} 次，最佳 mAP50={best.get('map50', 0):.4f}")

            # 自动创建模型记录
            model = GeneratedModel(
                task_id=task_id,
                name=task.name,
                model_path=result.get("final_model_path", ""),
                model_type="yolov8",
                file_size="45.2 MB",
                map50=best.get("map50"),
                map50_95=best.get("map50_95"),
            )
            db.add(model)
            db.commit()
            emit_task_event(task_id, "status", {"status": "completed", "progress": 100})
            emit_task_end(task_id)

    except Exception as e:
        db = SessionLocal()
        task = db.query(Task).filter(Task.task_id == task_id).first()
        if task:
            task.status = "failed"
            task.error_message = str(e)
            _create_task_log(db, task_id, "error", f"❌ 训练出错：{str(e)}")
            db.commit()
            emit_task_event(task_id, "status", {"status": "failed", "error": str(e)})
            emit_task_end(task_id)
    finally:
        db.close()


# ============================================
# API 端点
# ============================================

@router.post("/")
def create_task(request: dict, db: Session = Depends(get_db)):
    """
    创建新训练任务

    {
        "name": "安全帽检测",
        "description": "检测未佩戴安全帽的人员",
        "data_path": "/data/helmet",
        "class_names": ["person", "helmet", "no_helmet"]
    }
    """
    task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    class_names = request.get("class_names", ["object"])
    if len(class_names) == 1 and class_names[0] == "object":
        # 尝试从描述中提取类别
        desc = request.get("description", "")
        if "安全帽" in desc or " helmet" in desc.lower():
            class_names = ["person", "helmet", "no_helmet"]
        elif "烟火" in desc or "fire" in desc.lower():
            class_names = ["fire", "smoke"]
        elif "越界" in desc or "intrusion" in desc.lower():
            class_names = ["person", "boundary"]
        else:
            class_names = ["object"]

    task = Task(
        task_id=task_id,
        name=request.get("name", request.get("description", "新任务")[:50]),
        description=request.get("description", ""),
        data_path=request.get("data_path", ""),
        status="pending",
        progress=0.0,
        yolo_model=settings.default_yolo_model,
        epochs=request.get("epochs", settings.default_epochs),
        batch_size=settings.default_batch_size,
        image_size=settings.default_image_size,
        training_config={
            "class_names": class_names,
            "target_map50": 0.85,
            "target_map95": 0.65,
        }
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    _create_task_log(db, task_id, "info", f"✅ 任务已创建：{task.name}")
    _create_task_log(db, task_id, "info", f"📋 检测类别：{', '.join(class_names)}")

    return {
        "success": True,
        "task_id": task_id,
        "status": "pending",
        "progress": 0,
        "message": f"任务已创建，类别: {', '.join(class_names)}",
        "class_names": class_names,
    }


@router.get("/")
def list_tasks(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    """获取任务列表"""
    tasks = db.query(Task).order_by(Task.created_at.desc()).offset(skip).limit(limit).all()
    return {
        "tasks": [t.to_dict() for t in tasks],
        "total": db.query(Task).count(),
    }


@router.get("/{task_id}")
def get_task(task_id: str, db: Session = Depends(get_db)):
    """获取任务详情"""
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task.to_dict()


@router.get("/{task_id}/iterations")
def get_task_iterations(task_id: str, db: Session = Depends(get_db)):
    """获取任务的迭代历史"""
    loop = get_agent_training_loop(task_id)
    if loop:
        return {
            "task_id": task_id,
            "current_iteration": len(loop.iterations),
            "status": loop.status,
            "best_metrics": loop.best_metrics,
            "iterations": [it.to_dict() for it in loop.iterations],
        }

    # 如果训练已完成，从数据库恢复
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    metrics = db.query(TaskMetric).filter(TaskMetric.task_id == task_id).order_by(TaskMetric.epoch).all()

    return {
        "task_id": task_id,
        "current_iteration": 1,
        "status": task.status,
        "best_metrics": {
            "map50": task.map50,
            "map50_95": task.map50_95,
            "precision": task.precision,
            "recall": task.recall,
        },
        "iterations": [{
            "iteration_id": f"{task_id}_iter_1",
            "config": task.training_config or {},
            "status": task.status,
            "metrics": {
                "map50": task.map50,
                "map50_95": task.map50_95,
                "precision": task.precision,
                "recall": task.recall,
            },
            "decision": "pass" if task.status == "completed" else "running",
        }],
    }


@router.post("/{task_id}/start")
def start_task(task_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """启动训练（Agent 训练循环）"""
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.status in ["training"]:
        return {"success": False, "message": "训练正在进行中"}

    # 获取类别
    class_names = task.training_config.get("class_names", ["object"]) if task.training_config else ["object"]

    task.status = "training"
    task.started_at = datetime.utcnow()
    db.commit()

    _create_task_log(db, task_id, "info", "🚀 开始 Agent 训练流程...")
    _create_task_log(db, task_id, "info", f"📦 模型: {task.yolo_model}, 轮数: {task.epochs}, 批次: {task.batch_size}")

    # 启动后台训练
    background_tasks.add_task(
        _run_agent_loop_background,
        task_id,
        task.description or task.name,
        class_names
    )

    return {
        "success": True,
        "message": "Agent 训练流程已启动，正在进行迭代优化...",
        "task_id": task_id,
    }


@router.post("/{task_id}/stop")
def stop_task(task_id: str, db: Session = Depends(get_db)):
    """停止训练"""
    from backend.services.training_loop import stop_agent_training_loop

    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    stop_agent_training_loop(task_id)
    task.status = "stopped"
    db.commit()

    _create_task_log(db, task_id, "warning", "⚠️ 训练已手动停止")
    emit_task_event(task_id, "status", {"status": "stopped"})
    emit_task_end(task_id)
    return {"success": True, "message": "训练已停止"}


@router.get("/{task_id}/logs")
def get_task_logs(task_id: str, lines: int = 200, db: Session = Depends(get_db)):
    """获取训练日志"""
    logs = db.query(TaskLog).filter(
        TaskLog.task_id == task_id
    ).order_by(TaskLog.timestamp.asc()).limit(lines).all()

    return {
        "task_id": task_id,
        "logs": [log.to_dict() for log in logs],
    }


@router.get("/{task_id}/metrics")
def get_task_metrics(task_id: str, db: Session = Depends(get_db)):
    """获取训练指标"""
    metrics = db.query(TaskMetric).filter(
        TaskMetric.task_id == task_id
    ).order_by(TaskMetric.epoch.asc()).all()

    return {
        "task_id": task_id,
        "metrics": [m.to_dict() for m in metrics],
    }


@router.delete("/{task_id}")
def delete_task(task_id: str, db: Session = Depends(get_db)):
    """删除任务"""
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 删除关联的日志和指标
    db.query(TaskLog).filter(TaskLog.task_id == task_id).delete()
    db.query(TaskMetric).filter(TaskMetric.task_id == task_id).delete()
    db.delete(task)
    db.commit()

    return {"success": True, "message": "任务已删除"}
