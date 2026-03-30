# 离线部署指南 — YOLO Agent Platform

本文档说明如何在完全离线的海光/麒麟服务器（**ARM aarch64** + 麒麟 OS + MLU370）上部署本平台。

> **目标架构**: ARM a86_64 (aarch64) + 麒麟 OS（基于 Ubuntu Ports）

---

## 部署方式选择

| 方式 | 适用场景 | 复杂度 |
|------|----------|--------|
| **Docker Compose** | 有 Docker 环境 | 简单 ⭐ 推荐 |
| **Shell 脚本** | 直接部署，无 Docker | 中等 |

---

## 方式一：Docker Compose 部署（推荐）

### 1. 准备阶段（在有网络的机器上）

```bash
# 克隆项目（或拷贝项目文件夹）
git clone https://github.com/jt-xb/yolo-agent-platform.git
cd yolo-agent-platform

# 下载离线镜像包（在一台能联网的 x86_64 Linux 上执行）
cd deploy/scripts
chmod +x save-images.sh
./save-images.sh
# 执行后会在 deploy/images/ 目录下保存所有镜像 tar 包
```

### 2. 部署阶段（在目标离线服务器上）

```bash
# 拷贝整个项目文件夹到目标服务器
scp -r yolo-agent-platform root@<目标服务器>:/opt/

# 加载镜像
cd /opt/yolo-agent-platform/deploy/scripts
chmod +x load-images.sh
./load-images.sh

# 配置
cd /opt/yolo-agent-platform/deploy
cp config/.env.offline config/.env
# 编辑 config/.env，填入必要配置

# 启动
cd /opt/yolo-agent-platform/deploy
docker compose -f docker/docker-compose.offline.yml up -d
```

访问 `http://<服务器IP>:3000`

---

## 方式二：Shell 脚本直接部署

### 1. 准备阶段（在有网络的机器上）

**推荐：一键准备所有离线资源**

```bash
git clone https://github.com/jt-xb/yolo-agent-platform.git
cd yolo-agent-platform/deploy/scripts
chmod +x *.sh

# 一键准备（下载 wheels + npm + 模型 + Docker 镜像）
# 默认目标架构: aarch64 (ARM Kylin)
./prepare-offline.sh

# x86_64 Linux 服务器准备:
# ./prepare-offline.sh x86_64
```

**或分步执行：**

```bash
cd yolo-agent-platform/deploy/scripts
chmod +x *.sh

# 下载 pip wheel 包（默认 ARM aarch64，或指定 x86_64）
./download-wheels.sh 3.10 aarch64

# 下载前端 npm 包
./download-npm.sh

# 下载模型权重（用于自动标注）
./download-models.sh

# 构建并打包 Docker 镜像（需要 Docker）
./save-images.sh
```

### 2. 部署阶段（在目标离线服务器上）

```bash
# 拷贝整个项目到目标服务器
scp -r yolo-agent-platform root@<目标服务器>:/opt/

# 安装依赖
cd /opt/yolo-agent-platform/deploy/scripts
chmod +x install-offline.sh
./install-offline.sh

# 启动后端
cd /opt/yolo-agent-platform
source venv/bin/activate
PYTHONPATH=. nohup python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 > data/logs/backend.log 2>&1 &

# 启动前端
cd /opt/yolo-agent-platform/frontend
nohup npm run preview -- --port 5173 --host 0.0.0.0 > ../data/logs/frontend.log 2>&1 &

# 或用 nginx 托管 dist（推荐生产环境）
```

---

## 目录结构

```
deploy/
├── scripts/
│   ├── prepare-offline.sh      # ⭐ 一键准备所有离线资源（推荐）
│   ├── save-images.sh          # 保存 Docker 镜像为 tar 包
│   ├── load-images.sh          # 加载 Docker 镜像
│   ├── download-wheels.sh      # 下载 pip wheel 包（离线用）
│   ├── download-npm.sh         # 下载 npm 包（离线用）
│   ├── download-models.sh       # 下载 YOLO/SAM/DINO 模型权重
│   ├── install-offline.sh       # 一键安装离线依赖
│   └── start.sh                # 启动服务脚本
├── config/
│   ├── .env.offline          # 离线环境变量模板
│   └── nginx.conf            # Nginx 配置（生产环境用）
├── wheels/                   # pip wheel 包（准备阶段生成）
├── node_modules/             # npm 包（准备阶段生成）
├── images/                   # Docker 镜像 tar 包（准备阶段生成）
├── models/                   # AI 模型权重（准备阶段生成）
│   ├── yolov8n.pt            # YOLOv8 nano
│   ├── grounding-dino/       # Grounding DINO
│   └── sam/                  # SAM (Segment Anything)
└── docker/
    ├── Dockerfile.offline     # 离线版后端镜像
    └── docker-compose.offline.yml  # 离线版编排
```

---

## 环境配置说明

### .env 配置项

```bash
# 基础配置
LLM_API_KEY=           # 留空 = 离线模式（使用规则引擎）
LLM_API_BASE=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
USE_MLU=false          # true = 使用 MLU370，需要安装寒武纪 SDK
DATA_DIR=/opt/yolo-agent-platform/data

# 服务器配置
BACKEND_PORT=8000
FRONTEND_PORT=3000
```

### MLU370 加速（可选）

如需启用 MLU370 加速：

```bash
# 1. 安装寒武纪 Pytorch SDK
#    参考: https://www.cambricon.com/docs/pytorch/index.html

# 2. 修改 .env
USE_MLU=true
MLU_DEVICE_ID=0

# 3. 修改 backend/core/config.py
USE_MLU = True  # 改为 True
```

---

## 功能可用性（离线 vs 在线）

| 功能 | 离线可用 | 说明 |
|------|----------|------|
| 前端界面 | ✅ | 纯静态，无网络依赖 |
| 数据集管理 | ✅ | 本地文件处理 |
| 手动标注 | ✅ | 全部本地 |
| 视频抽帧 | ✅ | OpenCV 本地处理 |
| YOLO 训练（CPU/GPU） | ✅ | Ultralytics YOLO |
| YOLO 训练（MLU370） | ⚠️ | 需安装寒武纪 SDK |
| Agent 智能调参 | ❌ | 需联网（DeepSeek API） |
| 规则引擎调参 | ✅ | 自动回退，不需联网 |
| 自动标注（DINO+SAM） | ⚠️ | 需提前下载模型权重 |
| 推理服务 | ✅ | 本地 YOLO 推理 |
| Label Studio | ⚠️ | 需 Label Studio 运行 |

---

## 端口说明

| 端口 | 服务 | 说明 |
|------|------|------|
| 3000 | Nginx / 前端 | Web UI |
| 8000 | 后端 API | FastAPI |
| 8080 | Label Studio | 可选 |

---

## 常见问题

**Q: 启动后端报 `ModuleNotFoundError`？**
> 确认执行了 `install-offline.sh`，且激活了虚拟环境 `source venv/bin/activate`

**Q: 前端无法连接后端？**
> 确认后端在 8000 端口启动，检查防火墙 `firewall-cmd --add-port=8000/tcp`

**Q: 训练报 CUDA 错误？**
> 确认 .env 中 `USE_MLU=false`，且未安装 MLU 时不要启用 MLU 模式

**Q: 如何查看日志？**
```bash
tail -f /opt/yolo-agent-platform/data/logs/backend.log
tail -f /opt/yolo-agent-platform/data/logs/frontend.log
```
