#!/bin/bash
# ============================================================
# OpenVista MaxKB 数据库导出脚本 (Linux/Mac)
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_FILE="$SCRIPT_DIR/db/maxkb_full.dump"
CONTAINER_NAME="openvista-maxkb"

echo ""
echo "============================================"
echo "    OpenVista MaxKB 数据库导出"
echo "============================================"
echo ""

# 检查容器是否运行
echo "[1/3] 检查 MaxKB 容器..."
if ! docker inspect "$CONTAINER_NAME" --format='{{.State.Running}}' 2>/dev/null | grep -q "true"; then
    echo "✗ MaxKB 容器未运行"
    echo "请先启动 MaxKB: docker start $CONTAINER_NAME"
    exit 1
fi
echo "✓ MaxKB 容器正在运行"

# 在容器内执行导出
echo "[2/3] 导出数据库..."
echo "  在容器内执行 pg_dump..."
docker exec "$CONTAINER_NAME" pg_dump -U root -d maxkb --no-owner --no-acl -Fc -f /tmp/maxkb_export.dump

# 从容器复制文件到本地
echo "[3/3] 复制备份文件..."
docker cp "${CONTAINER_NAME}:/tmp/maxkb_export.dump" "$BACKUP_FILE"

# 清理容器内的临时文件
docker exec "$CONTAINER_NAME" rm -f /tmp/maxkb_export.dump

# 验证文件
FILE_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)

echo ""
echo "============================================"
echo "    导出完成！"
echo "============================================"
echo ""
echo "备份文件: $BACKUP_FILE"
echo "文件大小: $FILE_SIZE"
echo ""
echo "✓ 导出成功"

