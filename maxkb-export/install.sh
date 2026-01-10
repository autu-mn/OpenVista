#!/bin/bash
# ============================================================
# OpenVista MaxKB 一键安装脚本
# 方案：使用 MaxKB 内置数据库，启动后恢复数据
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_FILE="$SCRIPT_DIR/db/maxkb_full.dump"
MAXKB_IMAGE="registry.fit2cloud.com/maxkb/maxkb:v2.3.1"

echo ""
echo "============================================"
echo "    OpenVista MaxKB 一键安装"
echo "============================================"
echo ""

# 检查 Docker
echo "[1/5] 检查 Docker..."
if ! docker info > /dev/null 2>&1; then
    echo "✗ Docker 未安装或未运行"
    exit 1
fi
echo "✓ Docker 已就绪"

# 检查备份文件
echo "[2/5] 检查数据文件..."
if [ ! -f "$BACKUP_FILE" ]; then
    echo "✗ 数据库备份不存在: $BACKUP_FILE"
    exit 1
fi
FILE_SIZE=$(du -m "$BACKUP_FILE" | cut -f1)
echo "✓ 数据文件已就绪 (大小: ${FILE_SIZE} MB)"

# 清理
echo "[3/5] 清理旧环境..."
docker stop openvista-maxkb openvista-postgres 2>/dev/null || true
docker rm -f openvista-maxkb openvista-postgres 2>/dev/null || true
docker network rm openvista-net 2>/dev/null || true
docker volume rm -f openvista_maxkb_data openvista_pg_data openvista_maxkb_model 2>/dev/null || true
sleep 2
echo "✓ 环境已清理"

# 启动 MaxKB
echo "[4/5] 启动 MaxKB..."
docker volume create openvista_maxkb_data > /dev/null
docker run -d --name openvista-maxkb \
    -p 8080:8080 \
    -v openvista_maxkb_data:/opt/maxkb/data \
    $MAXKB_IMAGE > /dev/null

echo "  等待 MaxKB 完全启动..."
echo "  （首次启动需要初始化数据库，请耐心等待约90秒）"

# 等待 MaxKB 内置的 PostgreSQL 就绪
for i in {1..60}; do
    if docker exec openvista-maxkb pg_isready -U root -d maxkb > /dev/null 2>&1; then
        echo "  ✓ 数据库已就绪"
        break
    fi
    sleep 3
done

# 等待 MaxKB Web 服务就绪
for i in {1..30}; do
    if curl -s http://localhost:8080 > /dev/null 2>&1; then
        echo "  ✓ Web 服务已就绪"
        break
    fi
    sleep 3
done

# 恢复数据库
echo "[5/5] 恢复数据库..."
docker cp "$BACKUP_FILE" openvista-maxkb:/tmp/backup.dump

# 清空现有数据并恢复备份
echo "  正在恢复数据..."
docker exec openvista-maxkb psql -U root -d maxkb -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" 2>/dev/null || true
docker exec openvista-maxkb pg_restore -U root -d maxkb --no-owner --no-acl /tmp/backup.dump 2>/dev/null || true
docker exec openvista-maxkb rm -f /tmp/backup.dump

# 验证
TABLE_COUNT=$(docker exec openvista-maxkb psql -U root -d maxkb -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | tr -d ' ')
DOC_COUNT=$(docker exec openvista-maxkb psql -U root -d maxkb -t -c "SELECT COUNT(*) FROM document;" 2>/dev/null | tr -d ' ')
echo "  ✓ 已恢复 ${TABLE_COUNT:-0} 个表，${DOC_COUNT:-0} 个文档"

# 重启 MaxKB 使数据生效
echo "  重启服务..."
docker restart openvista-maxkb > /dev/null
sleep 15

# 等待服务恢复
for i in {1..30}; do
    if curl -s http://localhost:8080 > /dev/null 2>&1; then
        echo "✓ MaxKB 启动成功"
        break
    fi
    sleep 3
done

echo ""
echo "============================================"
echo "    安装完成！"
echo "============================================"
echo ""
echo "访问地址: http://localhost:8080"
echo "使用备份中的账户登录"
echo ""
