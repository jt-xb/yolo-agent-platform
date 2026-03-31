#!/bin/bash
#
# YOLO自动化训推平台 - 部署脚本
# 适用于飞腾+麒麟信创服务器离线部署
#
# 使用方法:
#   ./deploy.sh                 # 交互式部署
#   ./deploy.sh --skip-packages # 跳过包安装（已有依赖）
#   ./deploy.sh --mysql        # 使用已有MySQL容器
#   ./deploy.sh --sqlite       # 使用SQLite（默认）
#

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
PACKAGES_DIR="${DEPLOY_DIR}/packages"

# 默认配置
USE_MYSQL=false
MYSQL_HOST="localhost"
MYSQL_PORT=3306
MYSQL_USER="root"
MYSQL_PASSWORD="yolo_platform"
MYSQL_DATABASE="yolo_platform"
SKIP_PACKAGES=false

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-packages)
            SKIP_PACKAGES=true
            shift
            ;;
        --mysql)
            USE_MYSQL=true
            shift
            ;;
        --sqlite)
            USE_MYSQL=false
            shift
            ;;
        --help|-h)
            echo "用法: $0 [选项]"
            echo "选项:"
            echo "  --skip-packages  跳过包安装（已有依赖）"
            echo "  --mysql          使用MySQL数据库"
            echo "  --sqlite         使用SQLite数据库（默认）"
            echo "  --help           显示此帮助信息"
            exit 0
            ;;
        *)
            echo "未知选项: $1"
            exit 1
            ;;
    esac
done

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  YOLO自动化训推平台 - 部署脚本${NC}"
echo -e "${GREEN}========================================${NC}"

# 1. 检查 Python
echo -e "\n${YELLOW}[1/6] 检查 Python 环境...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未找到 python3，请先安装 Python 3.9+${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "Python 版本: ${PYTHON_VERSION}"

# 2. 创建必要目录
echo -e "\n${YELLOW}[2/6] 创建目录结构...${NC}"
mkdir -p "${PROJECT_DIR}/data/models"
mkdir -p "${PROJECT_DIR}/data/datasets"
mkdir -p "${PROJECT_DIR}/data/logs"
mkdir -p "${PROJECT_DIR}/data/runs"
echo -e "数据目录: ${PROJECT_DIR}/data/"

# 3. 配置环境变量
echo -e "\n${YELLOW}[3/6] 配置环境变量...${NC}"
ENV_FILE="${PROJECT_DIR}/backend/.env"

if [ ! -f "$ENV_FILE" ]; then
    if [ -f "${DEPLOY_DIR}/.env.example" ]; then
        cp "${DEPLOY_DIR}/.env.example" "$ENV_FILE"
        echo -e "${YELLOW}已创建 ${ENV_FILE}，请根据需要修改${NC}"
    fi
fi

# 根据选项配置数据库
if [ "$USE_MYSQL" = true ]; then
    echo -e "${YELLOW}配置使用 MySQL 数据库...${NC}"
    # 检查 MySQL 连接
    echo -e "MySQL 配置:"
    echo -e "  主机: ${MYSQL_HOST}:${MYSQL_PORT}"
    echo -e "  数据库: ${MYSQL_DATABASE}"
    echo -e "  用户: ${MYSQL_USER}"

    # 设置 MySQL 环境变量（供 .env 使用）
    export MYSQL_HOST MYSQL_PORT MYSQL_USER MYSQL_PASSWORD MYSQL_DATABASE
else
    echo -e "${YELLOW}使用 SQLite 数据库（默认）...${NC}"
fi

# 4. 安装 Python 依赖
echo -e "\n${YELLOW}[4/6] 安装 Python 依赖...${NC}"

if [ "$SKIP_PACKAGES" = true ]; then
    echo -e "跳过包安装（--skip-packages）"
else
    if [ -d "$PACKAGES_DIR" ] && [ "$(ls -A $PACKAGES_DIR 2>/dev/null)" ]; then
        echo -e "从本地包安装: ${PACKAGES_DIR}/"
        pip3 install --no-index --find-links="$PACKAGES_DIR" -r "${DEPLOY_DIR}/requirements.txt" || {
            echo -e "${RED}本地包安装失败，尝试在线安装...${NC}"
            pip3 install -r "${DEPLOY_DIR}/requirements.txt"
        }
    else
        echo -e "${YELLOW}注意: packages/ 目录为空或不存在，尝试在线安装${NC}"
        echo -e "如需离线安装，请先在有网环境下运行: ${DEPLOY_DIR}/download_packages.sh"
        pip3 install -r "${DEPLOY_DIR}/requirements.txt"
    fi
fi

# 5. 下载 YOLO 预训练模型（可选）
echo -e "\n${YELLOW}[5/6] 检查 YOLO 模型...${NC}"
python3 -c "
from ultralytics import YOLO
import os
model_cache = os.path.expanduser('~/.cache/ultralytics/')
os.makedirs(model_cache, exist_ok=True)
print('YOLO 模型缓存目录:', model_cache)
" || echo -e "${YELLOW}警告: 无法检查 YOLO 模型，训练时将自动下载${NC}"

# 6. 启动服务
echo -e "\n${YELLOW}[6/6] 启动服务...${NC}"

# 进入后端目录
cd "${PROJECT_DIR}/backend"

# 设置 Python 路径
export PYTHONPATH="${PROJECT_DIR}"

# 启动命令
START_CMD="python3 -m uvicorn main:app --host 0.0.0.0 --port 8000"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  启动后端服务...${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "访问地址: http://<服务器IP>:8000"
echo -e "API文档:  http://<服务器IP>:8000/docs"
echo -e ""
echo -e "按 Ctrl+C 停止服务"
echo -e "${GREEN}========================================${NC}"

# 启动服务
$START_CMD
