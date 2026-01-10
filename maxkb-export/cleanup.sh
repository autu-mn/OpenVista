#!/bin/bash
# ============================================================
# OpenVista MaxKB 清理脚本
# 彻底删除所有 MaxKB 相关的容器、卷和镜像
# ============================================================

echo ""
echo "============================================"
echo "    OpenVista MaxKB 清理"
echo "============================================"
echo ""

# 1. 停止并删除容器
echo "[1/3] 停止并删除容器..."
docker stop openvista-maxkb 2>/dev/null && echo "  ✓ 已停止 openvista-maxkb" || echo "  - 容器未运行"
docker rm -f openvista-maxkb 2>/dev/null && echo "  ✓ 已删除 openvista-maxkb" || echo "  - 容器不存在"

docker stop openvista-pg-temp 2>/dev/null
docker rm -f openvista-pg-temp 2>/dev/null

# 2. 删除数据卷
echo "[2/3] 删除数据卷..."
docker volume rm -f openvista_maxkb_postgres 2>/dev/null && echo "  ✓ 已删除 openvista_maxkb_postgres" || echo "  - 卷不存在"
docker volume rm -f openvista_maxkb_data 2>/dev/null && echo "  ✓ 已删除 openvista_maxkb_data" || echo "  - 卷不存在"

# 删除可能存在的其他相关卷
docker volume ls -q | grep -E "maxkb" | xargs -r docker volume rm -f 2>/dev/null

# 3. 删除镜像（可选）
echo "[3/3] 删除镜像..."
docker rmi registry.fit2cloud.com/maxkb/maxkb:v1.10.0-lts 2>/dev/null && echo "  ✓ 已删除 v1.10.0-lts 镜像" || echo "  - 镜像不存在"
docker rmi registry.fit2cloud.com/maxkb/maxkb:latest 2>/dev/null
docker rmi registry.fit2cloud.com/maxkb/maxkb 2>/dev/null

echo ""
echo "============================================"
echo "    清理完成！"
echo "============================================"
echo ""
echo "可以运行 ./install.sh 重新安装"
echo ""


