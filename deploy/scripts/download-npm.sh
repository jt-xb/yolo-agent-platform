#!/bin/bash
# download-npm.sh
# 在有网络的机器上执行，下载前端 npm 依赖到 node_modules/ 目录
# 用法: ./download-npm.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
FRONTEND_DIR="$PROJECT_DIR/frontend"
NPM_DIR="$PROJECT_DIR/node_modules"

echo "=== 下载前端 npm 依赖 ==="
echo "前端目录: $FRONTEND_DIR"
echo "输出目录: $NPM_DIR"

mkdir -p "$NPM_DIR"

cd "$FRONTEND_DIR"

# 安装依赖到本地 node_modules（而非全局）
npm install --legacy-peer-deps 2>&1 | tail -5

# 打包所有依赖为离线包
echo ""
echo "=== 打包 node_modules ==="
npm pack --legacy-peer-deps 2>&1 | tail -10

echo ""
echo "=== 下载完成 ==="
echo "node_modules 大小: $(du -sh "$NPM_DIR" | cut -f1)"
echo ""
echo "下一步：拷贝到目标服务器后，执行 npm install --legacy-peer-deps --offline 或直接使用已 build 的 dist/"
echo "建议：目标服务器使用前端 dist/ 静态文件，用 nginx 托管，无需 npm run dev"
