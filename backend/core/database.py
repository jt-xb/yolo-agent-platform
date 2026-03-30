"""
数据库连接与模型定义
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, ForeignKey, Boolean, JSON
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.core.config import settings

# 创建数据库引擎
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # SQLite 需要
    poolclass=StaticPool,  # SQLite 单线程用
)

# 创建 Session 工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基类
Base = declarative_base()

def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """初始化数据库"""
    Base.metadata.create_all(bind=engine)


class Task(Base):
    """训练任务模型"""
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)  # 用户描述，如"检测未佩戴安全帽"
    status = Column(String(32), default="pending")  # pending, data_processing, training, completed, failed
    progress = Column(Float, default=0.0)  # 0.0 - 100.0
    
    # 数据配置
    data_path = Column(String(512), nullable=True)  # 数据存储路径
    data_total = Column(Integer, default=0)  # 总数据量
    data_annotated = Column(Integer, default=0)  # 已标注量
    data_unannotated = Column(Integer, default=0)  # 未标注量
    
    # 训练配置
    yolo_model = Column(String(64), default=settings.default_yolo_model)
    epochs = Column(Integer, default=settings.default_epochs)
    batch_size = Column(Integer, default=settings.default_batch_size)
    image_size = Column(Integer, default=settings.default_image_size)
    training_type = Column(String(16), default="agent")  # "agent" | "regular"
    training_config = Column(JSON, default={})  # Agent生成的其他配置
    
    # 模型输出
    output_model_path = Column(String(512), nullable=True)  # 最佳模型路径
    output_model_size = Column(String(64), nullable=True)  # 模型文件大小
    
    # 评估指标
    map50 = Column(Float, nullable=True)
    map50_95 = Column(Float, nullable=True)
    precision = Column(Float, nullable=True)
    recall = Column(Float, nullable=True)
    
    # 错误信息
    error_message = Column(Text, nullable=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # 关联
    logs = relationship("TaskLog", back_populates="task", cascade="all, delete-orphan")
    metrics = relationship("TaskMetric", back_populates="task", cascade="all, delete-orphan")
    iterations = relationship("TaskIteration", back_populates="task", cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            "id": self.id,
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "progress": self.progress,
            "data_path": self.data_path,
            "data_total": self.data_total,
            "data_annotated": self.data_annotated,
            "data_unannotated": self.data_unannotated,
            "yolo_model": self.yolo_model,
            "epochs": self.epochs,
            "batch_size": self.batch_size,
            "image_size": self.image_size,
            "training_type": self.training_type,
            "training_config": self.training_config,
            "output_model_path": self.output_model_path,
            "output_model_size": self.output_model_size,
            "map50": self.map50,
            "map50_95": self.map50_95,
            "precision": self.precision,
            "recall": self.recall,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class TaskLog(Base):
    """任务日志"""
    __tablename__ = "task_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(64), ForeignKey("tasks.task_id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    level = Column(String(16), default="info")  # debug, info, warning, error
    message = Column(Text, nullable=False)
    
    # 关联
    task = relationship("Task", back_populates="logs")
    
    def to_dict(self):
        return {
            "id": self.id,
            "task_id": self.task_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "level": self.level,
            "message": self.message,
        }


class TaskMetric(Base):
    """任务训练指标"""
    __tablename__ = "task_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(64), ForeignKey("tasks.task_id"), nullable=False)
    epoch = Column(Integer, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Loss
    train_loss = Column(Float, nullable=True)
    val_loss = Column(Float, nullable=True)
    
    # 指标
    map50 = Column(Float, nullable=True)
    map50_95 = Column(Float, nullable=True)
    precision = Column(Float, nullable=True)
    recall = Column(Float, nullable=True)
    
    # 资源
    gpu_memory_mb = Column(Float, nullable=True)
    
    # 关联
    task = relationship("Task", back_populates="metrics")
    
    def to_dict(self):
        return {
            "id": self.id,
            "task_id": self.task_id,
            "epoch": self.epoch,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "train_loss": self.train_loss,
            "val_loss": self.val_loss,
            "map50": self.map50,
            "map50_95": self.map50_95,
            "precision": self.precision,
            "recall": self.recall,
            "gpu_memory_mb": self.gpu_memory_mb,
        }


class TaskIteration(Base):
    """训练迭代配置记录"""
    __tablename__ = "task_iterations"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(64), ForeignKey("tasks.task_id"), nullable=False)
    iteration = Column(Integer, nullable=False)
    yolo_model = Column(String(32), nullable=True)
    epochs = Column(Integer, nullable=True)
    batch_size = Column(Integer, nullable=True)
    map50 = Column(Float, nullable=True)
    map50_95 = Column(Float, nullable=True)
    precision = Column(Float, nullable=True)
    recall = Column(Float, nullable=True)
    decision = Column(String(32), nullable=True)
    config_snapshot = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="iterations")

    def to_dict(self):
        return {
            "id": self.id,
            "task_id": self.task_id,
            "iteration": self.iteration,
            "yolo_model": self.yolo_model,
            "epochs": self.epochs,
            "batch_size": self.batch_size,
            "map50": self.map50,
            "map50_95": self.map50_95,
            "precision": self.precision,
            "recall": self.recall,
            "decision": self.decision,
            "config_snapshot": self.config_snapshot,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Dataset(Base):
    """数据集"""
    __tablename__ = "datasets"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(256), nullable=False)
    path = Column(String(512), nullable=False)
    total_images = Column(Integer, default=0)
    annotated_images = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "total_images": self.total_images,
            "annotated_images": self.annotated_images,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class GeneratedModel(Base):
    """生成的模型"""
    __tablename__ = "generated_models"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(64), ForeignKey("tasks.task_id"), nullable=False)
    name = Column(String(256), nullable=False)
    model_path = Column(String(512), nullable=False)
    model_type = Column(String(32), default="yolov8")
    file_size = Column(String(64), nullable=True)  # 如 "25.6 MB"

    # 指标
    map50 = Column(Float, nullable=True)
    map50_95 = Column(Float, nullable=True)

    # 状态
    is_deployed = Column(Boolean, default=False)
    deployed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "task_id": self.task_id,
            "name": self.name,
            "model_path": self.model_path,
            "model_type": self.model_type,
            "file_size": self.file_size,
            "map50": self.map50,
            "map50_95": self.map50_95,
            "is_deployed": self.is_deployed,
            "deployed_at": self.deployed_at.isoformat() if self.deployed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class LLMConfig(Base):
    """LLM 配置"""
    __tablename__ = "llm_config"

    id = Column(Integer, primary_key=True, index=True)
    api_key = Column(String(256), nullable=True)
    api_base = Column(String(512), nullable=True)
    model = Column(String(64), nullable=True)
    enabled = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "api_key": self.api_key or "",
            "api_base": self.api_base or "",
            "model": self.model or "",
            "enabled": self.enabled,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
