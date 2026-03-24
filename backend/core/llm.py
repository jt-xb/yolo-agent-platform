"""
LLM 调用封装
支持 DeepSeek V3 等模型
"""
import os
import json
from typing import Dict, List, Optional, Any, Iterator, Union
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage, AIMessage, BaseMessage
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler

from backend.core.config import settings


class LLMService:
    """LLM 服务封装（延迟初始化）"""

    def __init__(self):
        self.model_name = settings.llm_model
        self.api_base = settings.llm_api_base
        self.api_key = settings.llm_api_key
        self._llm = None
        self._llm_no_stream = None

    @property
    def llm(self):
        if self._llm is None:
            self._llm = ChatOpenAI(
                temperature=0.7,
                openai_api_key=self.api_key,
                openai_api_base=self.api_base,
                model=self.model_name,
                streaming=True,
                callbacks=[StreamingStdOutCallbackHandler()],
                request_timeout=30,
            )
        return self._llm

    @property
    def llm_no_stream(self):
        if self._llm_no_stream is None:
            self._llm_no_stream = ChatOpenAI(
                temperature=0.7,
                openai_api_key=self.api_key,
                openai_api_base=self.api_base,
                model=self.model_name,
                streaming=False,
                request_timeout=30,
            )
        return self._llm_no_stream
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        stream: bool = False,
    ) -> str:
        """
        通用对话接口
        
        messages: [{"role": "user", "content": "..."}]
        """
        langchain_messages = self._convert_messages(messages)
        
        if stream:
            # 流式响应（主要用于终端调试）
            response = self.llm.invoke(langchain_messages)
            return response.content
        else:
            response = self.llm_no_stream.invoke(langchain_messages)
            return response.content
    
    def chat_with_system(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.7,
    ) -> str:
        """带系统提示词的对话"""
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ]
        response = self.llm_no_stream.invoke(messages)
        return response.content
    
    def _convert_messages(self, messages: List[Dict[str, str]]) -> List:
        """将字典格式消息转换为 LangChain 消息"""
        result = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                result.append(SystemMessage(content=content))
            elif role == "assistant":
                result.append(AIMessage(content=content))
            else:  # user
                result.append(HumanMessage(content=content))
        
        return result


# 全局实例
_llm_service: Optional[LLMService] = None

def get_llm_service() -> LLMService:
    """获取 LLM 服务单例"""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service


# ============================================
# Agent 工具函数 - 连接实际训练系统
# ============================================

def create_training_task_tool(task_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    创建训练任务工具

    Args:
        task_id: 任务ID
        config: 训练配置，包含:
            - yolo_model: YOLO模型版本 (yolov8n/m/s/l/x)
            - epochs: 训练轮数
            - batch_size: 批次大小
            - image_size: 图片尺寸
            - class_names: 类别列表
            - task_name: 任务名称
            - data_path: 数据路径

    Returns:
        {"success": bool, "message": str, "task_id": str}
    """
    from backend.core.database import SessionLocal, Task
    from datetime import datetime

    db = SessionLocal()
    try:
        task = Task(
            task_id=task_id,
            name=config.get("task_name", f"任务_{task_id[:8]}"),
            description=config.get("task_description", ""),
            data_path=config.get("data_path", ""),
            status="pending",
            progress=0.0,
            yolo_model=config.get("yolo_model", "yolov8n"),
            epochs=config.get("epochs", 100),
            batch_size=config.get("batch_size", 16),
            image_size=config.get("image_size", 640),
            training_config={
                "class_names": config.get("class_names", ["object"]),
            }
        )
        db.add(task)
        db.commit()

        return {
            "success": True,
            "message": f"训练任务 {task_id} 已创建，检测类别: {', '.join(config.get('class_names', ['object']))}",
            "task_id": task_id,
        }
    except Exception as e:
        db.rollback()
        return {
            "success": False,
            "message": f"创建任务失败: {str(e)}",
            "task_id": task_id,
        }
    finally:
        db.close()


def start_training_tool(task_id: str) -> Dict[str, Any]:
    """
    启动训练工具

    Args:
        task_id: 任务ID

    Returns:
        {"success": bool, "message": str, "pid": int}
    """
    from backend.core.database import SessionLocal, Task
    from backend.services.training_loop import start_agent_training_loop, get_agent_training_loop
    from datetime import datetime

    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.task_id == task_id).first()
        if not task:
            return {"success": False, "message": f"任务 {task_id} 不存在", "pid": -1}

        if task.status == "training":
            return {"success": False, "message": "训练正在进行中", "pid": -1}

        # 获取类别
        class_names = task.training_config.get("class_names", ["object"]) if task.training_config else ["object"]

        # 更新状态
        task.status = "training"
        task.started_at = datetime.utcnow()
        db.commit()

        # 启动训练循环（返回loop实例）
        loop = start_agent_training_loop(task_id, task.description or task.name, class_names)

        return {
            "success": True,
            "message": f"任务 {task_id} 训练已启动，Agent 开始迭代优化...",
            "pid": 1,  # 标记为运行中
            "task_id": task_id,
        }
    except Exception as e:
        db.rollback()
        return {"success": False, "message": f"启动训练失败: {str(e)}", "pid": -1}
    finally:
        db.close()


def stop_training_tool(task_id: str) -> Dict[str, Any]:
    """
    停止训练工具

    Args:
        task_id: 任务ID

    Returns:
        {"success": bool, "message": str}
    """
    from backend.core.database import SessionLocal, Task
    from backend.services.training_loop import stop_agent_training_loop

    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.task_id == task_id).first()
        if not task:
            return {"success": False, "message": f"任务 {task_id} 不存在"}

        # 停止训练循环
        stop_agent_training_loop(task_id)

        # 更新状态
        task.status = "stopped"
        db.commit()

        return {"success": True, "message": f"任务 {task_id} 训练已停止"}
    except Exception as e:
        db.rollback()
        return {"success": False, "message": f"停止训练失败: {str(e)}"}
    finally:
        db.close()


def get_training_logs_tool(task_id: str, lines: int = 100) -> Dict[str, Any]:
    """
    获取训练日志工具

    Args:
        task_id: 任务ID
        lines: 返回最近多少行

    Returns:
        {"success": bool, "logs": List[Dict], "total": int}
    """
    from backend.core.database import SessionLocal, TaskLog

    db = SessionLocal()
    try:
        logs = db.query(TaskLog).filter(
            TaskLog.task_id == task_id
        ).order_by(TaskLog.timestamp.desc()).limit(lines).all()

        log_list = [log.to_dict() for log in logs]
        log_list.reverse()  # 按时间正序

        return {
            "success": True,
            "logs": log_list,
            "total": len(log_list),
        }
    except Exception as e:
        return {"success": False, "logs": [], "message": str(e)}
    finally:
        db.close()


def get_training_metrics_tool(task_id: str) -> Dict[str, Any]:
    """
    获取训练指标工具

    Args:
        task_id: 任务ID

    Returns:
        {"success": bool, "metrics": {...}}
    """
    from backend.core.database import SessionLocal, Task, TaskMetric
    from backend.services.training_loop import get_agent_training_loop

    db = SessionLocal()
    try:
        # 首先尝试从运行中的训练循环获取
        loop = get_agent_training_loop(task_id)
        if loop and loop.current_iteration:
            iteration = loop.current_iteration
            return {
                "success": True,
                "metrics": {
                    "current_epoch": len(loop.iterations),
                    "total_epochs": loop.requirements.max_iterations,
                    "train_loss": iteration.train_loss,
                    "val_loss": iteration.val_loss,
                    "map50": iteration.map50,
                    "map50_95": iteration.map50_95,
                    "precision": iteration.precision,
                    "recall": iteration.recall,
                    "status": loop.status,
                },
            }

        # 否则从数据库获取
        task = db.query(Task).filter(Task.task_id == task_id).first()
        if not task:
            return {"success": False, "metrics": {}, "message": "任务不存在"}

        # 获取最新指标
        latest_metric = db.query(TaskMetric).filter(
            TaskMetric.task_id == task_id
        ).order_by(TaskMetric.epoch.desc()).first()

        if latest_metric:
            return {
                "success": True,
                "metrics": {
                    "current_epoch": latest_metric.epoch,
                    "total_epochs": task.epochs,
                    "train_loss": latest_metric.train_loss,
                    "val_loss": latest_metric.val_loss,
                    "map50": latest_metric.map50,
                    "map50_95": latest_metric.map50_95,
                    "precision": latest_metric.precision,
                    "recall": latest_metric.recall,
                    "status": task.status,
                    "progress": task.progress,
                },
            }

        # 如果没有指标记录，返回任务当前状态
        return {
            "success": True,
            "metrics": {
                "current_epoch": 0,
                "total_epochs": task.epochs,
                "train_loss": None,
                "val_loss": None,
                "map50": task.map50,
                "map50_95": task.map50_95,
                "precision": task.precision,
                "recall": task.recall,
                "status": task.status,
                "progress": task.progress,
            },
        }
    except Exception as e:
        return {"success": False, "metrics": {}, "message": str(e)}
    finally:
        db.close()


def download_model_tool(task_id: str) -> Dict[str, Any]:
    """
    下载模型工具

    Args:
        task_id: 任务ID

    Returns:
        {"success": bool, "download_url": str, "file_size": str, "model_path": str}
    """
    from backend.core.database import SessionLocal, Task, GeneratedModel

    db = SessionLocal()
    try:
        # 查找生成的模型
        model = db.query(GeneratedModel).filter(GeneratedModel.task_id == task_id).first()
        if model:
            return {
                "success": True,
                "download_url": f"/api/models/{model.id}/download",
                "file_size": model.file_size or "未知",
                "model_path": model.model_path,
            }

        # 如果没有模型记录，检查任务是否有输出路径
        task = db.query(Task).filter(Task.task_id == task_id).first()
        if task and task.output_model_path:
            return {
                "success": True,
                "download_url": f"/api/tasks/{task_id}/download",
                "file_size": task.output_model_size or "未知",
                "model_path": task.output_model_path,
            }

        return {
            "success": False,
            "message": f"任务 {task_id} 没有可下载的模型",
        }
    except Exception as e:
        return {"success": False, "message": f"获取下载信息失败: {str(e)}"}
    finally:
        db.close()


def deploy_model_tool(task_id: str) -> Dict[str, Any]:
    """
    部署模型工具

    Args:
        task_id: 任务ID

    Returns:
        {"success": bool, "message": str, "endpoint": str}
    """
    from backend.core.database import SessionLocal, GeneratedModel

    db = SessionLocal()
    try:
        model = db.query(GeneratedModel).filter(GeneratedModel.task_id == task_id).first()
        if not model:
            return {"success": False, "message": f"任务 {task_id} 没有可部署的模型"}

        if model.is_deployed:
            return {
                "success": True,
                "message": "模型已经部署",
                "endpoint": f"http://localhost:8000/infer/{model.id}",
            }

        # 标记为已部署
        from datetime import datetime
        model.is_deployed = True
        model.deployed_at = datetime.utcnow()
        db.commit()

        return {
            "success": True,
            "message": f"模型 {task_id} 已部署上线",
            "endpoint": f"http://localhost:8000/infer/{model.id}",
        }
    except Exception as e:
        db.rollback()
        return {"success": False, "message": f"部署失败: {str(e)}"}
    finally:
        db.close()
