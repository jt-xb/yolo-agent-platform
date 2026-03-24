"""
应用核心配置
"""
import os
from pathlib import Path
from typing import Optional

# 基础路径
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = DATA_DIR / "models"
DATASETS_DIR = DATA_DIR / "datasets"
LOGS_DIR = DATA_DIR / "logs"

# 确保目录存在
for d in [DATA_DIR, MODELS_DIR, DATASETS_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# 数据库
DATABASE_URL = f"sqlite:///{DATA_DIR}/yolo_platform.db"

# LLM 配置（使用外部API）
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")  # DeepSeek V3 API
LLM_API_BASE = os.getenv("LLM_API_BASE", "https://api.deepseek.com/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")  # TODO: 填入你的API Key

# MLU370 配置（暂时禁用，等卡到手再开）
MLU_DEVICE_ID = os.getenv("MLU_DEVICE_ID", "0")
USE_MLU = False  # 暂时禁用，用GPU/CPU跑演示

# 训练配置
DEFAULT_YOLO_MODEL = "yolov8n"  # 默认用nano版先跑通流程
DEFAULT_EPOCHS = 100
DEFAULT_BATCH_SIZE = 16
DEFAULT_IMAGE_SIZE = 640

# WebSocket
WS_HEARTBEAT_INTERVAL = 30

# 服务器配置
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))

class Settings:
    """应用设置"""
    project_name: str = "YOLO自动化训推平台"
    version: str = "0.1.0"
    debug: bool = os.getenv("DEBUG", "true").lower() == "true"
    
    # 路径
    base_dir: Path = BASE_DIR
    data_dir: Path = DATA_DIR
    models_dir: Path = MODELS_DIR
    datasets_dir: Path = DATASETS_DIR
    logs_dir: Path = LOGS_DIR
    
    # 数据库
    database_url: str = DATABASE_URL
    
    # LLM
    llm_model: str = LLM_MODEL
    llm_api_base: str = LLM_API_BASE
    llm_api_key: str = LLM_API_KEY
    
    # MLU
    use_mlu: bool = USE_MLU
    mlu_device_id: str = MLU_DEVICE_ID
    
    # 训练默认值
    default_yolo_model: str = DEFAULT_YOLO_MODEL
    default_epochs: int = DEFAULT_EPOCHS
    default_batch_size: int = DEFAULT_BATCH_SIZE
    default_image_size: int = DEFAULT_IMAGE_SIZE

    # 服务器配置
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", 8000))

settings = Settings()
