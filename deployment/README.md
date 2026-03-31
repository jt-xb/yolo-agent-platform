# YOLO自动化训推平台 - 离线部署指南

## 目录结构

```
deployment/
├── deploy.sh              # 主部署脚本
├── download_packages.sh    # 下载离线依赖脚本
├── requirements.txt        # Python 依赖列表
├── .env.example           # 环境变量模板
├── docker-compose.yml     # MySQL 容器配置（可选）
├── yolo-agent.service    # Systemd 服务配置（Linux）
├── packages/              # 离线依赖包（需运行 download_packages.sh 下载）
└── README.md              # 本文件
```

## 部署步骤

### 方式一：使用 SQLite（推荐新手）

```bash
# 1. 上传项目到服务器
scp -r yolo-agent-platform user@server:/path/to/

# 2. SSH 登录服务器
ssh user@server

# 3. 进入部署目录
cd /path/to/yolo-agent-platform/deployment

# 4. 复制并配置环境变量
cp .env.example ../backend/.env
# 编辑 ../backend/.env，配置 LLM_API_KEY 和 LLM_API_BASE

# 5. 运行部署脚本
chmod +x deploy.sh
./deploy.sh
```

### 方式二：使用已有 MySQL 容器

```bash
# 1. 确保 MySQL 容器正常运行
# 2. 配置 .env
cp .env.example ../backend/.env
# 编辑 .env 中的 DATABASE_URL 指向你的 MySQL

# 3. 部署
./deploy.sh --mysql
```

### 方式三：创建新的 MySQL 容器

```bash
# 1. 启动 MySQL 容器
docker-compose up -d

# 2. 配置 .env（自动使用 docker-compose 中的 MySQL）
cp .env.example ../backend/.env

# 3. 部署
./deploy.sh --mysql
```

## 离线包下载（在一台有网络的机器上操作）

```bash
# 在有网络的机器上运行
chmod +x download_packages.sh
./download_packages.sh

# 将生成的 packages/ 目录复制到部署服务器
scp -r packages user@server:/path/to/yolo-agent-platform/deployment/
```

## 服务管理（Linux with systemd）

```bash
# 安装服务
sudo cp yolo-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable yolo-agent

# 启动服务
sudo systemctl start yolo-agent

# 查看状态
sudo systemctl status yolo-agent

# 查看日志
journalctl -u yolo-agent -f
```

## 验证部署

```bash
# 检查服务状态
curl http://localhost:8000/health

# 查看 API 文档
# 浏览器访问 http://服务器IP:8000/docs
```

## 常见问题

### 1. 依赖包安装失败
```bash
# 尝试手动安装
pip3 install --no-index --find-links=./packages -r requirements.txt
```

### 2. MySQL 连接失败
```bash
# 检查 MySQL 是否运行
docker ps | grep mysql
# 或
mysql -h localhost -u root -p

# 测试连接
curl http://localhost:8000/api/tasks/
```

### 3. 端口被占用
```bash
# 修改 .env 中的 PORT
# 或杀掉占用进程
lsof -i :8000
kill -9 <PID>
```

### 4. YOLO 模型下载慢/失败
模型会在首次训练时自动下载。如需预下载：
```python
from ultralytics import YOLO
model = YOLO('yolov8n.pt')
```

## 目录权限

确保部署用户对以下目录有读写权限：
```bash
chmod -R 755 /path/to/yolo-agent-platform/data/
chmod -R 755 /path/to/yolo-agent-platform/backend/
```
