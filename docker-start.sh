#!/bin/bash
# OpenVista Docker 启动脚本

set -e

echo "=========================================="
echo "OpenVista Docker 部署启动脚本"
echo "=========================================="

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "错误: Docker 未安装，请先安装 Docker"
    exit 1
fi

# 检查 Docker Compose 是否安装
if ! command -v docker-compose &> /dev/null; then
    echo "错误: Docker Compose 未安装，请先安装 Docker Compose"
    exit 1
fi

# 检查 .env 文件
if [ ! -f .env ]; then
    echo "警告: .env 文件不存在，正在创建..."
    cat > .env << EOF
# GitHub API Token（必需）
GITHUB_TOKEN=your_github_token_here

# MaxKB AI API（可选）
MAXKB_AI_API=http://localhost:8080/api/application/{app_id}/chat/completions
MAXKB_API_KEY=your_maxkb_api_key

# Hugging Face 模型配置
USE_HUGGINGFACE=true
HUGGINGFACE_MODEL_ID=Osacato/Gitpulse
EOF
    echo "已创建 .env 文件，请编辑后填入正确的配置"
    echo "按 Enter 继续..."
    read
fi

# 构建并启动服务
echo ""
echo "正在构建 Docker 镜像..."
docker-compose build

echo ""
echo "正在启动服务..."
docker-compose up -d

echo ""
echo "等待服务启动..."
sleep 5

# 检查服务状态
echo ""
echo "服务状态:"
docker-compose ps

echo ""
echo "=========================================="
echo "部署完成！"
echo "=========================================="
echo ""
echo "访问地址:"
echo "  前端: http://localhost:3000"
echo "  后端: http://localhost:5000"
echo "  MaxKB: http://localhost:8080"
echo ""
echo "查看日志:"
echo "  docker-compose logs -f"
echo ""
echo "停止服务:"
echo "  docker-compose down"
echo ""



