#!/bin/bash
#
# 下载所有依赖包用于离线部署
# 在有网络连接的机器上运行，运行后将 packages/ 目录复制到部署服务器
#

set -e

DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
PACKAGES_DIR="${DEPLOY_DIR}/packages"

echo "========================================"
echo "  下载离线部署依赖包"
echo "========================================"
echo "下载目录: ${PACKAGES_DIR}/"
echo ""

mkdir -p "$PACKAGES_DIR"

# 下载 requirements.txt 中的包
pip3 download \
    -r "${DEPLOY_DIR}/requirements.txt" \
    --dest "$PACKAGES_DIR" \
    --no-deps \
    --platform manylinux2014_aarch64 \
    --python-version 39 \
    --only-binary=:all: \
    2>&1 | tee "${DEPLOY_DIR}/download.log" || {
    echo "部分包下载失败，尝试不限制平台..."
    pip3 download \
        -r "${DEPLOY_DIR}/requirements.txt" \
        --dest "$PACKAGES_DIR" \
        --no-deps \
        2>&1 | tee -a "${DEPLOY_DIR}/download.log"
}

# 单独处理 torch（非常大）
echo ""
echo "下载 PyTorch（可选，如已有则跳过）..."
if [ ! -f "${PACKAGES_DIR}/torch-2.2.0-cp39-cp39-manylinux2014_aarch64.whl" ]; then
    pip3 download \
        torch==2.2.0 \
        torchvision==0.17.0 \
        --dest "$PACKAGES_DIR" \
        --platform manylinux2014_aarch64 \
        --python-version 39 \
        --only-binary=:all: \
        2>&1 | tee -a "${DEPLOY_DIR}/download.log" || {
        echo "PyTorch aarch64 版本下载失败，尝试通用版本..."
        pip3 download \
            torch==2.2.0 \
            torchvision==0.17.0 \
            --dest "$PACKAGES_DIR" \
            --no-deps \
            2>&1 | tee -a "${DEPLOY_DIR}/download.log"
    }
else
    echo "PyTorch 已存在，跳过"
fi

echo ""
echo "========================================"
echo "  下载完成"
echo "========================================"
echo "包数量: $(ls $PACKAGES_DIR | wc -l)"
echo "总大小: $(du -sh $PACKAGES_DIR | cut -f1)"
echo ""
echo "请将 packages/ 目录复制到部署服务器的 deployment/ 目录下"
