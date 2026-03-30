# YOLO Agent Platform

基于大模型 Agent 的 YOLO 自动化训推一体化 Web 平台，支持完全离线环境下从任务输入到模型部署的全流程。

## Features

### Dataset Management
- **图片浏览**：支持训练集/验证集/测试集过滤，已标注/未标注状态过滤
- **手动标注**：画框标注，实时预览，支持上一张/下一张导航
- **类别管理**：在线添加/删除检测类别，自动同步到 YOLO 格式标注文件
- **视频抽帧**：上传视频自动按帧间隔抽取图片，支持 MP4/AVI/MOV/MKV
- **自动标注**：基于 Grounding DINO + SAM 的 AI 自动标注
- **Label Studio 集成**：一键同步数据集到 Label Studio，导出标注结果

### Model Training
- **Agent 训练循环**：大模型自动决策训练参数和迭代优化流程
- **实时监控**：SSE 推送训练日志、指标（mAP50、mAP50-95、Precision、Recall）
- **停止/恢复**：支持中途停止训练，保留已生成模型
- **增量训练**：支持基于预训练模型继续训练

### Model Management
- 模型仓库存储所有生成的模型
- 一键部署到本地推理服务
- 支持 YOLOv8 全系列模型

## Tech Stack

| Layer | Tech |
|-------|------|
| Frontend | Vue 3 + Element Plus |
| Backend | FastAPI + Uvicorn |
| Database | SQLite |
| Agent | LangChain (ReAct) |
| LLM | DeepSeek V3.2 |
| Training | Ultralytics YOLO |
| Real-time | SSE (Server-Sent Events) |
| Container | Docker + Docker Compose |

## Project Structure

```
yolo-agent-platform/
├── backend/
│   ├── agents/               # LLM Agent core
│   ├── routers/             # API routes
│   │   ├── tasks.py         # Task management
│   │   ├── datasets.py      # Dataset management
│   │   ├── models.py        # Model management
│   │   └── label_studio.py  # Label Studio integration
│   ├── services/
│   │   ├── training_loop.py # Agent training loop
│   │   └── label_studio.py  # Label Studio sync/export
│   └── main.py              # FastAPI entry
├── frontend/
│   └── src/
│       ├── views/
│       │   ├── DatasetsView.vue  # Dataset browsing & annotation
│       │   ├── TasksView.vue     # Training tasks
│       │   └── ModelsView.vue    # Model management
│       └── api/
└── docker/
```

## Quick Start

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
PYTHONPATH=. python -m uvicorn backend.main:app --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Visit http://localhost:5173

### 3. Docker

```bash
cd docker
docker-compose up -d
```

Visit http://localhost:3000

## API Endpoints

### Tasks
- `POST /api/tasks/` — Create task
- `GET /api/tasks/` — List tasks
- `GET /api/tasks/{id}` — Get task details
- `POST /api/tasks/{id}/start` — Start training
- `POST /api/tasks/{id}/stop` — Stop training
- `GET /api/tasks/{id}/stream` — SSE real-time logs

### Datasets
- `GET /api/datasets/all` — List all datasets
- `POST /api/datasets/create` — Create dataset
- `GET /api/datasets/{id}/images` — List images with split/status filters
- `POST /api/datasets/upload-images` — Upload images
- `GET /api/datasets/{id}/meta` — Get dataset metadata (class names)
- `PUT /api/datasets/{id}/meta` — Update dataset metadata
- `POST /api/datasets/video-extract` — Extract frames from video
- `POST /api/datasets/dino-sam-auto-label` — AI auto-labeling

### Models
- `GET /api/models/` — List models
- `POST /api/models/deploy` — Deploy model for inference

## Annotation Workflow

1. Select a dataset → switch to "浏览图片" tab
2. Use split/status filters to find target images
3. Click an image → enable "标注模式"
4. Add classes via the class manager panel
5. Draw bounding boxes on the image
6. Click "保存标注" → saved as YOLO format

## Label Studio Integration

1. Enable Label Studio tab → enter URL and API Key → test connection
2. Select dataset → enter class names → choose split (train/val/test)
3. Click "一键同步到 Label Studio"
4. Annotate in Label Studio → export annotations back
