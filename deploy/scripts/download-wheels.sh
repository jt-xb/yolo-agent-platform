#!/bin/bash
# download-wheels.sh
# 在有网络的机器上执行，下载所有 pip wheel 包到 wheels/ 目录
# 目标架构: aarch64 (ARM Kylin)
# 用法: ./download-wheels.sh [python_version]
# 默认: Python 3.10, linux_aarch64

set -e

PYTHON_VERSION="${1:-3.10}"
ARCH="aarch64"   # 麒麟/ARM 服务器
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
WHEELS_DIR="$PROJECT_DIR/wheels"

echo "=== 下载 Python 依赖包 (ARM aarch64) ==="
echo "Python 版本: $PYTHON_VERSION"
echo "架构: $ARCH"
echo "输出目录: $WHEELS_DIR"

mkdir -p "$WHEELS_DIR"

cd "$PROJECT_DIR/backend"

# 记录哪些包没有 aarch64 wheel，需要 --no-binary
NO_BINARY_PKGS=""

# 分批下载：先只 binary
pip download \
    --python-version "$PYTHON_VERSION" \
    --platform "${ARCH}_manylinux2014" \
    --abi cp310 \
    --only-binary=:all: \
    --no-deps \
    -r requirements.txt \
    -d "$WHEELS_DIR" \
    2>&1 | grep -E "(Successfully|ERROR|Collecting)" | tail -30

# 下载带依赖的包（关键！）
pip download \
    --python-version "$PYTHON_VERSION" \
    --platform "${ARCH}_manylinux2014" \
    --abi cp310 \
    --only-binary=:all: \
    -r requirements.txt \
    -d "$WHEELS_DIR" \
    2>&1 | grep -E "(Successfully|ERROR|Collecting)" | tail -30

echo ""
echo "=== 尝试源码包（处理没有 binary 的包）==="
# 对于没有 aarch64 wheel 的包，尝试下载源码
for pkg in $(grep -v "^#" requirements.txt | grep -v "^$" | cut -d"=" -f1 | head -50); do
    if ! ls "$WHEELS_DIR"/${pkg}-*.whl >/dev/null 2>&1; then
        pip download \
            --python-version "$PYTHON_VERSION" \
            --platform "${ARCH}_manylinux2014" \
            --abi cp310 \
            --no-binary :all: \
            -d "$WHEELS_DIR" \
            "$pkg" \
            2>&1 | grep -v "Skipping" | tail -2 || true
    fi
done

echo ""
echo "=== 下载完成 ==="
echo "包数量: $(ls "$WHEELS_DIR" | wc -l)"
echo "总大小: $(du -sh "$WHEELS_DIR" | cut -f1)"
echo ""
echo "=== 在目标 ARM 服务器上安装 ==="
echo "  cd /opt/yolo-agent-platform"
echo "  python -m venv venv"
echo "  source venv/bin/activate"
echo "  pip install --no-index --find-links=deploy/wheels -r backend/requirements.txt"
