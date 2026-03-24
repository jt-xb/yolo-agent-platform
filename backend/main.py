"""
FastAPI 应用入口
YOLO自动化训推平台 - 后端服务
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi import WebSocket
import json

from backend.core.config import settings
from backend.core.database import init_db
from backend.routers import tasks
from backend.routers import datasets, models, inference_api


# ============================================
# WebSocket 管理
# ============================================

class ConnectionManager:
    """WebSocket 连接管理器"""
    
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, task_id: str):
        await websocket.accept()
        if task_id not in self.active_connections:
            self.active_connections[task_id] = []
        self.active_connections[task_id].append(websocket)
    
    def disconnect(self, websocket: WebSocket, task_id: str):
        if task_id in self.active_connections:
            if websocket in self.active_connections[task_id]:
                self.active_connections[task_id].remove(websocket)
    
    async def send_to_task(self, task_id: str, message: dict):
        """向特定任务的所有连接发送消息"""
        if task_id in self.active_connections:
            for connection in self.active_connections[task_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    pass
    
    async def broadcast(self, message: dict):
        """广播到所有连接"""
        for task_id in self.active_connections:
            await self.send_to_task(task_id, message)


manager = ConnectionManager()


# ============================================
# 生命周期管理
# ============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    print(f"🚀 {settings.project_name} v{settings.version}")
    print(f"📁 数据目录: {settings.data_dir}")
    print(f"🔧 MLU支持: {settings.use_mlu}")
    
    # 初始化数据库
    init_db()
    print("✅ 数据库初始化完成")
    
    yield
    
    # 关闭时
    print("👋 应用关闭")


# ============================================
# FastAPI 应用
# ============================================

app = FastAPI(
    title=settings.project_name,
    version=settings.version,
    description="基于大模型Agent的YOLO自动化训推一体化Web平台",
    lifespan=lifespan,
)

# CORS 配置（允许前端开发服务器访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件目录（用于模型下载等）
app.mount("/static", StaticFiles(directory=str(settings.data_dir)), name="static")

# 注册路由
app.include_router(tasks.router)
app.include_router(models.router)
app.include_router(inference_api.router)
app.include_router(datasets.router)


# ============================================
# WebSocket 端点
# ============================================

@app.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    """WebSocket 连接用于实时训练监控"""
    await manager.connect(websocket, task_id)
    try:
        while True:
            # 接收客户端消息（通常用于心跳）
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                pass
    except Exception:
        manager.disconnect(websocket, task_id)


# ============================================
# 系统状态端点
# ============================================

@app.get("/api/system/status")
async def get_system_status():
    """获取系统状态"""
    # TODO: 实现真实的系统监控
    return {
        "status": "online",
        "version": settings.version,
        "gpu_available": True,
        "gpu_name": "MLU370" if settings.use_mlu else "NVIDIA GPU",
        "gpu_memory_total": 16384,  # MB
        "gpu_memory_used": 4096,
        "llm_model": settings.llm_model,
        "llm_status": "ready",
    }


@app.get("/api/system/metrics")
async def get_system_metrics():
    """获取系统指标"""
    # TODO: 实现真实指标采集
    return {
        "cpu_percent": 45.2,
        "memory_percent": 62.8,
        "gpu_percent": 78.5,
        "gpu_memory_percent": 45.2,
        "disk_percent": 33.1,
    }


# ============================================
# 健康检查
# ============================================

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "service": settings.project_name}


@app.get("/")
async def root():
    """根路径"""
    return {
        "service": settings.project_name,
        "version": settings.version,
        "docs": "/docs",
    }


# ============================================
# 主入口
# ============================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info",
    )
