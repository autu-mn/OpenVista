#!/bin/bash
# ============================================================
# DataPulse 项目初始化脚本
# 队友 clone 后运行此脚本即可完成环境配置
# ============================================================

echo ""
echo "============================================"
echo "    DataPulse 项目初始化"
echo "============================================"
echo ""

# 1. 检查并安装 Git LFS
echo "[1/3] 检查 Git LFS..."
if ! command -v git-lfs &> /dev/null; then
    echo "  Git LFS 未安装，正在安装..."
    # 尝试自动安装
    if command -v apt-get &> /dev/null; then
        sudo apt-get install git-lfs -y
    elif command -v brew &> /dev/null; then
        brew install git-lfs
    else
        echo "  ✗ 请手动安装 Git LFS: https://git-lfs.github.com/"
        exit 1
    fi
fi
git lfs install
echo "✓ Git LFS 已就绪"

# 2. 下载大型模型文件
echo "[2/3] 下载 GitPulse 模型文件..."
git lfs pull
echo "✓ 模型文件已下载"

# 3. 验证模型文件
echo "[3/3] 验证模型文件..."
MODEL_FILE="backend/GitPulse/gitpulse_weights.pt"
if [ -f "$MODEL_FILE" ]; then
    SIZE=$(du -m "$MODEL_FILE" | cut -f1)
    if [ "$SIZE" -gt 100 ]; then
        echo "✓ 模型文件完整 (${SIZE} MB)"
    else
        echo "✗ 模型文件可能不完整，请重新运行 git lfs pull"
        exit 1
    fi
else
    echo "✗ 模型文件不存在"
    exit 1
fi

echo ""
echo "============================================"
echo "    初始化完成！"
echo "============================================"
echo ""
echo "接下来："
echo "  1. 后端: cd backend && pip install -r requirements.txt"
echo "  2. 前端: cd frontend && npm install"
echo "  3. 启动: 参考 README.md"
echo ""


