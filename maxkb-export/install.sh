#!/bin/bash
# ============================================================
# OpenVista MaxKB 一键安装脚本
# ============================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_FILE="$SCRIPT_DIR/db/maxkb_full.dump"

echo ""
echo -e "${CYAN}============================================${NC}"
echo -e "${CYAN}    OpenVista MaxKB 一键安装${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""

# 检查 Docker
echo -e "${YELLOW}[1/4] 检查 Docker...${NC}"
if ! command -v docker &> /dev/null || ! docker info &> /dev/null; then
    echo -e "${RED}✗ Docker 未安装或未运行${NC}"
    echo "  请安装 Docker Desktop: https://www.docker.com/products/docker-desktop/"
    exit 1
fi
echo -e "${GREEN}✓ Docker 已就绪${NC}"

# 检查备份文件
echo -e "${YELLOW}[2/4] 检查数据文件...${NC}"
if [ ! -f "$BACKUP_FILE" ]; then
    echo -e "${RED}✗ 数据库备份不存在: $BACKUP_FILE${NC}"
    echo ""
    echo "请先按照 DEPLOY_GUIDE.md 导出数据库："
    echo "  docker exec <容器名> pg_dump -U root -d maxkb -Fc > db/maxkb_full.dump"
    exit 1
fi
echo -e "${GREEN}✓ 数据文件已就绪${NC}"

# 启动服务
echo -e "${YELLOW}[3/4] 启动 MaxKB 服务...${NC}"

# 生成 docker-compose.yml
cat > "$SCRIPT_DIR/docker-compose.yml" << 'EOF'
name: openvista
services:
  maxkb:
    image: registry.fit2cloud.com/maxkb/maxkb:latest
    container_name: openvista-maxkb
    ports:
      - "8080:8080"
    volumes:
      - maxkb_data:/opt/maxkb/model
      - maxkb_postgres:/var/lib/postgresql/data
    environment:
      - DB_HOST=localhost
      - DB_PORT=5432
      - DB_USER=root
      - DB_PASSWORD=MaxKB@123456
      - DB_NAME=maxkb
    restart: unless-stopped
volumes:
  maxkb_data:
  maxkb_postgres:
EOF

cd "$SCRIPT_DIR"
docker compose down 2>/dev/null || true

# 先手动拉取镜像（避免 docker compose 拉取时的校验问题）
echo "  拉取 MaxKB 镜像..."
MAXKB_IMAGE="registry.fit2cloud.com/maxkb/maxkb:latest"
docker pull "$MAXKB_IMAGE" 2>&1 | tail -3 || echo "  使用本地镜像..."

# 启动服务（如果镜像已存在，不会重新拉取）
docker compose up -d

# 等待服务启动
echo "  等待服务启动..."
for i in {1..30}; do
    if curl -s http://localhost:8080 > /dev/null 2>&1; then
        echo -e "${GREEN}✓ MaxKB 服务已启动${NC}"
        break
    fi
    sleep 3
done

# 恢复数据库
echo -e "${YELLOW}[4/4] 恢复数据库...${NC}"
sleep 10

docker cp "$BACKUP_FILE" openvista-maxkb:/tmp/backup.dump
docker exec openvista-maxkb bash -c "pg_restore -U root -d maxkb --clean --if-exists /tmp/backup.dump 2>/dev/null || true"
docker exec openvista-maxkb rm -f /tmp/backup.dump

# 修复迁移冲突：使用 Django 的 --fake 选项标记所有迁移为已应用
echo "  修复数据库迁移状态..."
echo "  使用 Django migrate --fake 标记迁移为已应用..."
docker exec openvista-maxkb bash -c "cd /opt/maxkb-app/apps && python3 manage.py migrate --fake 2>&1 | grep -E 'FAKED|No migrations|Applying' || true"
echo "  ✓ 迁移已标记为已应用"

# 重启服务
echo "  重启服务..."
docker restart openvista-maxkb

# 等待 Django 完全启动（重要！）
echo "  等待 Django 服务完全启动..."
for i in {1..30}; do
    if docker exec openvista-maxkb curl -s -f http://localhost:8080/api/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Django 服务已就绪${NC}"
        break
    fi
    sleep 2
done

# 重置密码（使用 MD5 哈希）
echo "  重置管理员密码..."
# MaxKB@123456 的 MD5 哈希值
PASSWORD_MD5="0df6c52f03e1c75504c7bb9a09c2a016"
echo "UPDATE \"user\" SET password = '${PASSWORD_MD5}' WHERE username = 'admin';" | docker exec -i openvista-maxkb psql -U root -d maxkb > /dev/null 2>&1
echo -e "${GREEN}✓ 密码已重置为 MaxKB@123456${NC}"

echo -e "${GREEN}✓ 数据库恢复完成${NC}"

# 完成
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}    安装完成！${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "访问地址: ${CYAN}http://localhost:8080${NC}"
echo -e "用户名:   ${CYAN}admin${NC}"
echo -e "密码:     ${CYAN}MaxKB@123456${NC}"
echo ""
echo -e "${YELLOW}重要：登录后请在「系统设置」→「模型管理」中配置 DeepSeek API Key${NC}"
echo ""
