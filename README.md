# YOLO自动化训推平台

基于大模型Agent的YOLO自动化训推一体化Web平台，支持完全离线环境下从任务输入到模型部署的全流程。

## 项目结构

```
yolo-agent-platform/
├── backend/                 # FastAPI 后端
│   ├── agents/             # 大模型Agent核心
│   │   └── trainer_agent.py # 训练流程Agent (LangChain ReAct)
│   ├── models/             # Pydantic 数据模型
│   │   ├── task.py         # 任务模型
│   │   └── dataset.py      # 数据集模型
│   ├── routers/           # API路由
│   │   ├── tasks.py        # 任务管理API
│   │   ├── datasets.py      # 数据管理API
│   │   ├── models.py        # 模型管理API
│   │   └── websocket.py     # WebSocket实时通信
│   ├── services/          # 业务逻辑服务
│   │   ├── task_service.py  # 任务服务
│   │   ├── training_service.py # 训练服务
│   │   └── yolo_service.py   # YOLO相关服务
│   ├── core/              # 核心配置
│   │   ├── config.py       # 应用配置
│   │   ├── database.py     # 数据库连接
│   │   └── llm.py          # LLM调用封装
│   └── main.py            # FastAPI 入口
├── frontend/              # Vue3 + Element Plus 前端
├── docker/               # Docker 相关文件
│   ├── backend.Dockerfile
│   ├── frontend.Dockerfile
│   └── docker-compose.yml
└── docs/                 # 文档
```

## 核心模块说明

### 1. 任务管理 (Task Management)
- 用户提交任务描述（自然语言）
- Agent自动解析任务、创建训练配置、启动训练
- 全流程状态跟踪

### 2. 数据管理 (Data Management)
- 支持图片/视频数据上传或本地路径指定
- 自动标注（基于视觉模型）
- 标注结果可视化与人工校验

### 3. 模型训练 (Model Training)
- 基于LangChain ReAct Agent自动决策训练流程
- 训练参数由Agent根据任务描述推荐
- 实时日志与指标监控（WebSocket推送）

### 4. 模型管理 (Model Management)
- 模型仓库：存储所有生成的模型
- 一键部署到本地推理服务

### 5. 系统设置 (System Settings)
- 离线模型管理
- 算力资源监控（GPU/MLU）
- 用户管理（可选）

## 技术栈

| 层级 | 技术选型 |
|------|---------|
| 前端框架 | Vue 3 + Element Plus |
| 后端框架 | FastAPI + Uvicorn |
| 数据库 | SQLite |
| Agent框架 | LangChain (ReAct) |
| LLM | DeepSeek V3.2 |
| 训练框架 | Ultralytics YOLO |
| 加速卡 | MLU370 (寒武纪) |
| 实时通信 | WebSocket |
| 容器化 | Docker + Docker Compose |

## 开发环境

- Python 3.10+
- Node.js 18+
- MLU370 SDK (Cambricon Pytorch SDK)
- Docker & Docker Compose

## 快速启动

### 1. 配置 API Key

复制配置模板并填入你的 DeepSeek API Key：
```bash
cd backend
cp .env.example .env
# 编辑 .env，填入 LLM_API_KEY
```

### 2. 本地开发（前端演示模式）

**后端：**
```bash
cd backend
pip install -r requirements.txt
python main.py
```

**前端（新终端）：**
```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173 即可看到前端界面。

### 3. Docker 部署
```bash
cd docker
docker-compose up -d
```

访问 http://localhost:3000

### 4. MLU370 加速（等卡到手后）
在 `.env` 中设置 `USE_MLU=true`，同时确保安装了寒武纪 SDK。

## Agent 工具设计

Agent可用工具：
1. `create_training_task` - 创建训练任务
2. `start_training` - 启动训练
3. `stop_training` - 停止训练
4. `get_training_logs` - 获取训练日志
5. `get_training_metrics` - 获取训练指标
6. `download_model` - 下载模型
7. `deploy_model` - 部署模型

## License

MIT
