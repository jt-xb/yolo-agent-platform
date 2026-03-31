"""
任务管理 API 路由
"""
import os
import uuid
import time
import threading
import asyncio
import queue as sync_queue
import json
from pathlib import Path
from datetime import datetime
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Body
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from backend.core.database import get_db, Task, TaskLog, TaskMetric, TaskIteration, GeneratedModel
from backend.core.config import settings
from backend.services.training_loop import (
    start_agent_training_loop,
    get_agent_training_loop,
)

router = APIRouter(prefix="/api/tasks", tags=["任务管理"])

# ============================================
# SSE 实时日志：每 task_id 独立队列
# ============================================

# task_id → (sync_queue.Queue, threading.Event)
_task_queues: dict[str, tuple[sync_queue.Queue, threading.Event]] = {}
_streams_lock = threading.Lock()


def _get_or_create_queue(task_id: str) -> tuple[sync_queue.Queue, threading.Event]:
    """获取或创建 SSE 队列（线程安全）"""
    with _streams_lock:
        if task_id not in _task_queues:
            q = sync_queue.Queue(maxsize=500)
            ev = threading.Event()
            _task_queues[task_id] = (q, ev)
        return _task_queues[task_id]


def _close_queue(task_id: str):
    """关闭并清理 SSE 队列"""
    with _streams_lock:
        if task_id in _task_queues:
            q, ev = _task_queues.pop(task_id)
            ev.set()
            try:
                q.put_nowait("__END__")
            except:
                pass


@router.get("/{task_id}/stream")
async def stream_task_events(task_id: str):
    """
    SSE 实时流：推送训练日志、指标、状态更新
    每个任务 ID 独立队列，第二次打开也能正常接收。
    """
    # 先关闭旧的队列（如果存在）
    _close_queue(task_id)

    # 重新创建新队列
    q, ev = _get_or_create_queue(task_id)

    async def event_generator():
        yield "event: connected\ndata: \n\n"
        last_heartbeat = time.time()
        try:
            while True:
                try:
                    item = q.get(timeout=5)
                    last_heartbeat = time.time()
                except sync_queue.Empty:
                    yield "event: heartbeat\ndata: \n\n"
                    continue

                if item == "__END__":
                    yield "event: end\ndata: \n\n"
                    break

                etype, edata = item
                yield f"event: {etype}\ndata: {edata}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            _close_queue(task_id)

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
    """向 SSE 队列推送事件（线程安全）"""
    entry = _task_queues.get(task_id)
    if entry:
        q, _ = entry
        try:
            q.put_nowait((event_type, json.dumps(data, ensure_ascii=False, default=str)))
        except sync_queue.Full:
            pass


def emit_task_end(task_id: str):
    """通知 SSE 连接结束（异步清理）"""
    entry = _task_queues.get(task_id)
    if entry:
        _, end_event = entry
        end_event.set()
        try:
            entry[0].put_nowait("__END__")
        except sync_queue.Full:
            pass
        threading.Thread(target=_close_queue, args=(task_id,), daemon=True).start()


# ============================================
# 辅助函数
# ============================================

def _create_task_log(db: Session, task_id: str, level: str, message: str):
    """写日志到 DB + 推 SSE"""
    log = TaskLog(task_id=task_id, level=level, message=message)
    db.add(log)
    db.commit()
    emit_task_event(task_id, "log", {
        "type": "log",
        "level": level,
        "message": message,
        "timestamp": datetime.now().isoformat(),
    })


def _run_agent_loop_background(task_id: str, description: str, class_names: List[str], dataset_id: str = None, pretrained_model: str = ""):
    """后台运行 Agent 训练循环"""
    from backend.core.database import SessionLocal
    db = SessionLocal()
    try:
        loop = start_agent_training_loop(task_id, description, class_names, dataset_id)
        task = db.query(Task).filter(Task.task_id == task_id).first()
        if not task:
            return
        task.status = "training"
        task.started_at = datetime.utcnow()
        db.commit()

        def progress_callback(iteration_data: dict, current_iter: int, total_iters: int):
            db2 = SessionLocal()
            try:
                iter_progress = (current_iter / total_iters) * 100
                task2 = db2.query(Task).filter(Task.task_id == task_id).first()
                if task2:
                    task2.progress = min(iter_progress * 0.9, 90)
                    task2.map50 = iteration_data.get("metrics", {}).get("map50")
                    task2.map50_95 = iteration_data.get("metrics", {}).get("map50_95")
                    task2.precision = iteration_data.get("metrics", {}).get("precision")
                    task2.recall = iteration_data.get("metrics", {}).get("recall")
                    db2.commit()

                for log_msg in iteration_data.get("logs", []):
                    _create_task_log(db2, task_id, "info", log_msg)

                metrics = iteration_data.get("metrics", {})
                if metrics.get("map50"):
                    emit_task_event(task_id, "metrics", {
                        "type": "metric",
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

                if metrics.get("map50"):
                    metric = TaskMetric(
                        task_id=task_id, epoch=current_iter, iteration=current_iter,
                        map50=metrics.get("map50"), map50_95=metrics.get("map50_95"),
                        precision=metrics.get("precision"), recall=metrics.get("recall"),
                        train_loss=metrics.get("train_loss"), val_loss=metrics.get("val_loss"),
                    )
                    db2.add(metric)

                    iter_record = TaskIteration(
                        task_id=task_id, iteration=current_iter,
                        yolo_model=iteration_data.get("config", {}).get("yolo_model", ""),
                        epochs=iteration_data.get("config", {}).get("epochs", 0),
                        batch_size=iteration_data.get("config", {}).get("batch_size", 0),
                        map50=metrics.get("map50"), map50_95=metrics.get("map50_95"),
                        precision=metrics.get("precision"), recall=metrics.get("recall"),
                        decision=iteration_data.get("decision", "pass"),
                        config_snapshot=iteration_data.get("config", {}),
                    )
                    db2.add(iter_record)
                    db2.commit()
            finally:
                db2.close()

        result = loop.run(progress_callback=progress_callback)

        task = db.query(Task).filter(Task.task_id == task_id).first()
        if task:
            final_status = result.get("status", "completed")
            task.progress = 100.0
            task.status = final_status
            task.completed_at = datetime.utcnow()
            if final_status != "stopped":
                best = result.get("best_metrics", {})
                task.map50 = best.get("map50")
                task.map50_95 = best.get("map50_95")
                task.precision = best.get("precision")
                task.recall = best.get("recall")
                task.output_model_path = result.get("final_model_path")
                total_iters = result.get("total_iterations", 0)
                _create_task_log(db, task_id, "info", f"🎉 训练完成！共迭代 {total_iters} 次，最佳 mAP50={best.get('map50', 0):.4f}")
                if result.get("final_model_path"):
                    model = GeneratedModel(
                        task_id=task_id, name=task.name,
                        model_path=result.get("final_model_path", ""),
                        model_type="yolov8", file_size="45.2 MB",
                        map50=best.get("map50"), map50_95=best.get("map50_95"),
                    )
                    db.add(model)
            else:
                _create_task_log(db, task_id, "info", "⚠️ 训练已停止")
            db.commit()
            emit_task_event(task_id, "status", {"type": "status", "status": final_status, "progress": 100})
            emit_task_end(task_id)
    except Exception as e:
        import traceback
        task = db.query(Task).filter(Task.task_id == task_id).first()
        if task:
            task.status = "failed"
            task.error_message = str(e)
            _create_task_log(db, task_id, "error", f"❌ 训练出错：{str(e)}")
            _create_task_log(db, task_id, "error", f"详细：{traceback.format_exc()[-500:]}")
            db.commit()
            emit_task_event(task_id, "status", {"type": "status", "status": "failed", "error": str(e)})
            emit_task_end(task_id)
    finally:
        db.close()


def _run_regular_training_background(task_id: str, dataset_id: str = None, pretrained_model: str = ""):
    """常规训练后台函数（单次 YOLO 训练 + 流式输出每轮指标）"""
    from backend.core.database import SessionLocal
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.task_id == task_id).first()
        if not task:
            return

        task.status = "training"
        task.started_at = datetime.utcnow()
        db.commit()

        # 数据集路径
        if dataset_id:
            dataset_path = Path(settings.data_dir) / "datasets" / dataset_id
            if not dataset_path.exists():
                dataset_path = Path("/tmp") / dataset_id
        else:
            dataset_path = Path("/tmp/yolo_demo_dataset")
        data_yaml = dataset_path / "data.yaml"
        if not data_yaml.exists():
            data_yaml = "/tmp/yolo_demo_dataset/data.yaml"

        model_name = task.yolo_model or "yolov8n"
        model_path = pretrained_model if (pretrained_model and os.path.exists(pretrained_model)) else f"{model_name}.pt"

        _create_task_log(db, task_id, "info", f"🔥 开始训练: {model_name}, {task.epochs} epochs, batch={task.batch_size or 8}")
        emit_task_event(task_id, "status", {"type": "status", "status": "training", "progress": 0})

        from ultralytics import YOLO
        model = YOLO(model_path)
        loop = start_agent_training_loop(task_id, task.description or task.name, task.training_config or {}, dataset_id)
        loop.status = "training"

        def on_epoch_end_callback(trainer):
            """每 epoch：写 DB（保证 getTaskLogs 能查到）+ 推 SSE（流式展示）"""
            epoch = trainer.epoch
            total = trainer.epochs

            metrics_dict = getattr(trainer, 'metrics', {}) or {}
            if not isinstance(metrics_dict, dict):
                metrics_dict = {}

            map50_ep = (metrics_dict.get('metrics/mAP50(B)') or metrics_dict.get('map50') or metrics_dict.get('mAP50', 0.0))
            loss_ep = (metrics_dict.get('train/box_loss') or getattr(trainer, 'loss', 0.0) or 0.0)
            try:
                map50_ep = float(map50_ep) if map50_ep else 0.0
                loss_ep = float(loss_ep) if loss_ep else 0.0
            except (ValueError, TypeError):
                map50_ep = loss_ep = 0.0

            progress_pct = int((epoch + 1) / total * 100)
            now = datetime.now()  # 统一时间戳
            ts = now.isoformat()
            log_msg = f"[{now.strftime('%H:%M:%S')}] Epoch {epoch+1}/{total}: loss={loss_ep:.4f}, mAP50={map50_ep:.4f}"

            # 写 DB（保证 getTaskLogs 能查到完整日志）
            db2 = SessionLocal()
            try:
                metric = TaskMetric(
                    task_id=task_id, epoch=epoch + 1,
                    map50=map50_ep, map50_95=0.0,
                    train_loss=loss_ep, val_loss=0.0,
                )
                db2.add(metric)
                db2.commit()

                log = TaskLog(task_id=task_id, level="info", message=log_msg, timestamp=now)
                db2.add(log)
                db2.commit()
            finally:
                db2.close()

            # 推 SSE（流式输出）
            emit_task_event(task_id, "log", {
                "type": "log", "message": log_msg,
                "timestamp": ts, "level": "info",
            })
            emit_task_event(task_id, "metrics", {
                "type": "metrics",
                "epoch": epoch + 1, "total_epochs": total,
                "map50": map50_ep, "loss": loss_ep, "train_loss": loss_ep,
                "progress": progress_pct,
            })
            emit_task_event(task_id, "status", {
                "type": "status", "status": "training", "progress": progress_pct,
                "map50": map50_ep,
            })

        model.callbacks['on_fit_epoch_end'].append(on_epoch_end_callback)

        results = model.train(
            data=str(data_yaml),
            epochs=min(task.epochs, 100),
            batch=min(task.batch_size or 8, 16),
            imgsz=min(task.image_size or 640, 640),
            device='cpu',
            project=str(settings.models_dir),
            name=task_id,
            exist_ok=True,
            verbose=False,
            save=True,
            plots=True,
            patience=20,
        )

        # 解析最终结果
        if hasattr(results, 'results_dict'):
            rd = results.results_dict
            map50 = round(rd.get('metrics/mAP50(B)', 0), 4)
            map50_95 = round(rd.get('metrics/mAP50-95(B)', 0), 4)
            precision_val = round(rd.get('metrics/precision(B)', 0), 4)
            recall_val = round(rd.get('metrics/recall(B)', 0), 4)
        else:
            try:
                map50 = round(float(results.box.map50), 4)
                map50_95 = round(float(results.box.map), 4)
                precision_val = round(float(results.box.mp), 4)
                recall_val = round(float(results.box.mr), 4)
            except Exception:
                map50 = map50_95 = precision_val = recall_val = 0.0

        task = db.query(Task).filter(Task.task_id == task_id).first()
        if task:
            task.status = "completed"
            task.progress = 100.0
            task.map50 = map50
            task.map50_95 = map50_95
            task.precision = precision_val
            task.recall = recall_val
            task.completed_at = datetime.utcnow()

            best_model = settings.models_dir / task_id / "weights" / "best.pt"
            last_model = settings.models_dir / task_id / "weights" / "last.pt"
            if best_model.exists():
                task.output_model_path = str(best_model)
            elif last_model.exists():
                task.output_model_path = str(last_model)

            if task.output_model_path and os.path.exists(task.output_model_path):
                size_bytes = os.path.getsize(task.output_model_path)
                model_file_size = f"{size_bytes / (1024*1024):.1f} MB" if size_bytes > 1024*1024 else f"{size_bytes / 1024:.1f} KB"
            else:
                model_file_size = "unknown"

            db.commit()
            _create_task_log(db, task_id, "info", f"🎉 训练完成！mAP50={map50:.4f}")
            emit_task_event(task_id, "status", {"type": "status", "status": "completed", "progress": 100, "map50": map50})
            emit_task_end(task_id)

            if task.output_model_path:
                model_record = GeneratedModel(
                    task_id=task_id, name=task.name,
                    model_path=task.output_model_path,
                    model_type="yolov8", file_size=model_file_size,
                    map50=map50, map50_95=map50_95,
                )
                db.add(model_record)
                db.commit()

    except Exception as e:
        import traceback
        task = db.query(Task).filter(Task.task_id == task_id).first()
        if task:
            task.status = "failed"
            task.error_message = str(e)
            _create_task_log(db, task_id, "error", f"❌ 训练出错：{str(e)}")
            _create_task_log(db, task_id, "error", f"详细：{traceback.format_exc()[-500:]}")
            db.commit()
            emit_task_event(task_id, "status", {"type": "status", "status": "failed", "error": str(e)})
            emit_task_end(task_id)
    finally:
        db.close()


# ============================================
# API 端点
# ============================================

@router.post("/")
def create_task(request: dict, db: Session = Depends(get_db)):
    """创建新训练任务"""
    task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    class_names = request.get("class_names", ["object"])
    if len(class_names) == 1 and class_names[0] == "object":
        desc = request.get("description", "")
        if "安全帽" in desc or " helmet" in desc.lower():
            class_names = ["person", "helmet", "no_helmet"]
        elif "烟火" in desc or "fire" in desc.lower():
            class_names = ["fire", "smoke"]
        elif "越界" in desc or "intrusion" in desc.lower():
            class_names = ["person", "boundary"]
        else:
            class_names = ["object"]

    dataset_id = request.get("dataset_id", "")
    data_path = str(settings.data_dir / "datasets" / dataset_id) if dataset_id else request.get("data_path", "")
    pretrained_model = request.get("pretrained_model", "")
    training_type = request.get("training_type", "regular")

    task = Task(
        task_id=task_id,
        name=request.get("name", (request.get("description", "") or "新任务")[:50]),
        description=request.get("description", ""),
        data_path=data_path,
        status="pending",
        progress=0.0,
        yolo_model=request.get("yolo_model", settings.default_yolo_model),
        epochs=request.get("epochs", settings.default_epochs),
        batch_size=request.get("batch_size", settings.default_batch_size),
        image_size=request.get("image_size", settings.default_image_size),
        training_type=training_type,
        training_config={
            "class_names": class_names,
            "target_map50": 0.85,
            "target_map95": 0.65,
            "pretrained_model": pretrained_model,
        }
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    _create_task_log(db, task_id, "info", f"✅ 任务已创建：{task.name}")
    _create_task_log(db, task_id, "info", f"📋 检测类别：{', '.join(class_names)}")

    return {
        "success": True, "task_id": task_id, "status": "pending", "progress": 0,
        "message": f"任务已创建，类别: {', '.join(class_names)}", "class_names": class_names,
    }


@router.get("/")
def list_tasks(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    tasks = db.query(Task).order_by(Task.created_at.desc()).offset(skip).limit(limit).all()
    return {"tasks": [t.to_dict() for t in tasks], "total": db.query(Task).count()}


@router.get("/{task_id}")
def get_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    result = task.to_dict()
    last_iter = db.query(TaskIteration).filter(
        TaskIteration.task_id == task_id
    ).order_by(TaskIteration.iteration.desc()).first()
    if last_iter:
        result["actual_config"] = {
            "yolo_model": last_iter.yolo_model,
            "epochs": last_iter.epochs,
            "batch_size": last_iter.batch_size,
            "config_snapshot": last_iter.config_snapshot,
        }
    else:
        result["actual_config"] = None
    return result


@router.get("/{task_id}/iterations")
def get_task_iterations(task_id: str, db: Session = Depends(get_db)):
    loop = get_agent_training_loop(task_id)
    if loop:
        return {
            "task_id": task_id,
            "current_iteration": len(loop.iterations),
            "status": loop.status,
            "best_metrics": loop.best_metrics,
            "iterations": [it.to_dict() for it in loop.iterations],
        }

    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    iterations_db = db.query(TaskIteration).filter(
        TaskIteration.task_id == task_id
    ).order_by(TaskIteration.iteration).all()

    if iterations_db:
        iterations = [{
            "iteration_id": f"{task_id}_iter_{it.iteration}",
            "iteration": it.iteration,
            "config": it.config_snapshot or {},
            "yolo_model": it.yolo_model,
            "epochs": it.epochs,
            "batch_size": it.batch_size,
            "status": "completed",
            "metrics": {"map50": it.map50, "map50_95": it.map50_95, "precision": it.precision, "recall": it.recall},
            "decision": it.decision,
        } for it in iterations_db]
        return {
            "task_id": task_id, "current_iteration": len(iterations_db),
            "status": task.status,
            "best_metrics": {"map50": task.map50, "map50_95": task.map50_95, "precision": task.precision, "recall": task.recall},
            "iterations": iterations,
        }

    metrics = db.query(TaskMetric).filter(TaskMetric.task_id == task_id).order_by(TaskMetric.epoch).all()
    return {
        "task_id": task_id, "current_iteration": 1, "status": task.status,
        "best_metrics": {"map50": task.map50, "map50_95": task.map50_95, "precision": task.precision, "recall": task.recall},
        "iterations": [{
            "iteration_id": f"{task_id}_iter_1", "iteration": 1,
            "config": task.training_config or {},
            "yolo_model": task.yolo_model, "epochs": task.epochs, "batch_size": task.batch_size,
            "status": task.status,
            "metrics": {"map50": task.map50, "map50_95": task.map50_95, "precision": task.precision, "recall": task.recall},
            "decision": "pass" if task.status == "completed" else ("running" if task.status == "training" else "stopped"),
        }],
    }


@router.post("/{task_id}/start")
def start_task(task_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """启动训练"""
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status in ["training", "paused"]:
        return {"success": False, "message": "训练正在进行中"}
    from backend.services.training_loop import get_agent_training_loop
    if get_agent_training_loop(task_id):
        return {"success": False, "message": "训练正在进行中，请先停止"}

    class_names = task.training_config.get("class_names", ["object"]) if task.training_config else ["object"]
    dataset_id = Path(task.data_path).name if task.data_path else None
    pretrained_model = task.training_config.get("pretrained_model", "") if task.training_config else ""

    task.status = "training"
    task.started_at = datetime.utcnow()
    db.commit()

    if task.training_type == "agent":
        _create_task_log(db, task_id, "info", "🚀 开始 Agent 智能训练流程...")
        _create_task_log(db, task_id, "info", f"📦 模型: {task.yolo_model}, 轮数: {task.epochs}, 批次: {task.batch_size}")
        background_tasks.add_task(_run_agent_loop_background, task_id, task.description or task.name, class_names, dataset_id, pretrained_model)
        return {"success": True, "message": "Agent 训练流程已启动，正在进行迭代优化...", "task_id": task_id, "training_type": "agent"}
    else:
        _create_task_log(db, task_id, "info", "🚀 开始常规训练...")
        _create_task_log(db, task_id, "info", f"📦 模型: {task.yolo_model}, 轮数: {task.epochs}, 批次: {task.batch_size}")
        background_tasks.add_task(_run_regular_training_background, task_id, dataset_id, pretrained_model)
        return {"success": True, "message": "常规训练已启动...", "task_id": task_id, "training_type": "regular"}


@router.post("/{task_id}/stop")
def stop_task(task_id: str, db: Session = Depends(get_db)):
    from backend.services.training_loop import stop_agent_training_loop
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    stop_agent_training_loop(task_id)
    task.status = "stopped"
    db.commit()
    _create_task_log(db, task_id, "warning", "⚠️ 训练已手动停止")
    emit_task_event(task_id, "status", {"type": "status", "status": "stopped"})
    emit_task_end(task_id)
    return {"success": True, "message": "训练已停止"}


@router.post("/{task_id}/pause")
def pause_task(task_id: str, db: Session = Depends(get_db)):
    from backend.services.training_loop import pause_agent_training_loop
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    ok = pause_agent_training_loop(task_id)
    if ok:
        task.status = "paused"
        db.commit()
        _create_task_log(db, task_id, "info", "⏸️ 训练已暂停")
        emit_task_event(task_id, "status", {"type": "status", "status": "paused"})
        return {"success": True, "message": "训练已暂停"}
    return {"success": False, "message": "训练不在运行中，无法暂停"}


@router.post("/{task_id}/resume")
def resume_task(task_id: str, db: Session = Depends(get_db)):
    from backend.services.training_loop import resume_agent_training_loop
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    ok = resume_agent_training_loop(task_id)
    if ok:
        task.status = "training"
        db.commit()
        _create_task_log(db, task_id, "info", "▶️ 训练已恢复")
        emit_task_event(task_id, "status", {"type": "status", "status": "training"})
        return {"success": True, "message": "训练已恢复"}
    return {"success": False, "message": "训练不在暂停中，无法恢复"}


@router.post("/{task_id}/decision")
def submit_task_decision(task_id: str, body: dict = Body(...)):
    from backend.services.training_loop import submit_user_decision
    decision = body.get("decision", "stop")
    ok = submit_user_decision(task_id, decision)
    if not ok:
        raise HTTPException(status_code=400, detail="任务不在等待决策状态")
    return {"success": True, "decision": decision}


@router.get("/{task_id}/decision")
def get_task_decision(task_id: str):
    from backend.services.training_loop import get_pending_decision
    info = get_pending_decision(task_id)
    if info is None:
        return {"waiting": False}
    return info


@router.get("/{task_id}/logs")
def get_task_logs(task_id: str, lines: int = 200, db: Session = Depends(get_db)):
    """获取训练日志（从 DB 读取，保证完整性）"""
    logs = db.query(TaskLog).filter(
        TaskLog.task_id == task_id
    ).order_by(TaskLog.timestamp.asc()).limit(lines).all()
    return {"task_id": task_id, "logs": [log.to_dict() for log in logs]}


@router.get("/{task_id}/metrics")
def get_task_metrics(task_id: str, db: Session = Depends(get_db)):
    """获取训练指标"""
    metrics = db.query(TaskMetric).filter(
        TaskMetric.task_id == task_id
    ).order_by(TaskMetric.epoch.asc()).all()
    return {"task_id": task_id, "metrics": [m.to_dict() for m in metrics]}


@router.delete("/{task_id}")
def delete_task(task_id: str, db: Session = Depends(get_db)):
    """删除任务"""
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    db.query(TaskLog).filter(TaskLog.task_id == task_id).delete()
    db.query(TaskMetric).filter(TaskMetric.task_id == task_id).delete()
    db.delete(task)
    db.commit()
    return {"success": True, "message": "任务已删除"}
