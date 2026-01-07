#!/bin/bash
# ============================================================
# OpenVista MaxKB 一键安装脚本 (Linux/Mac)
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_FILE="$SCRIPT_DIR/db/maxkb_full.dump"
MAXKB_IMAGE="registry.fit2cloud.com/maxkb/maxkb"

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
    echo "请确保 db/maxkb_full.dump 文件存在"
    exit 1
fi
FILE_SIZE=$(du -m "$BACKUP_FILE" | cut -f1)
echo "✓ 数据文件已就绪 (大小: ${FILE_SIZE} MB)"

# 检查备份文件大小
if [ "$FILE_SIZE" -lt 1 ]; then
    echo "⚠ 警告: 备份文件过小，可能是空数据库备份"
    echo "  请确保备份文件包含完整数据（通常 > 10MB）"
fi

# 清理旧容器
echo "[3/5] 准备环境..."
docker stop openvista-maxkb 2>/dev/null || true
docker rm openvista-maxkb 2>/dev/null || true
docker volume create openvista_maxkb_data > /dev/null 2>&1 || true
docker volume create openvista_maxkb_postgres > /dev/null 2>&1 || true
echo "✓ 环境已准备"

# 启动 MaxKB
echo "[4/5] 启动 MaxKB..."
docker run -d --name openvista-maxkb \
    -p 8080:8080 \
    -v openvista_maxkb_data:/opt/maxkb/model \
    -v openvista_maxkb_postgres:/var/lib/postgresql/data \
    -e DB_HOST=localhost \
    -e DB_PORT=5432 \
    -e DB_USER=root \
    -e DB_PASSWORD=MaxKB@123456 \
    -e DB_NAME=maxkb \
    $MAXKB_IMAGE > /dev/null

echo "  等待 MaxKB 初始化（约60秒）..."
sleep 60

# 检查服务是否启动
for i in {1..30}; do
    if curl -s http://localhost:8080 > /dev/null 2>&1; then
        echo "✓ MaxKB 启动成功"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "✗ MaxKB 启动超时"
        exit 1
    fi
    sleep 3
done

# 恢复数据库
echo "[5/5] 恢复数据库..."

# 复制备份文件到容器
docker cp "$BACKUP_FILE" openvista-maxkb:/tmp/backup.dump

# 使用 pg_restore 恢复
echo "  正在恢复数据（可能需要几分钟）..."
docker exec openvista-maxkb pg_restore -U root -d maxkb --clean --if-exists --no-owner /tmp/backup.dump 2>/dev/null || true

# 清理临时文件
docker exec openvista-maxkb rm -f /tmp/backup.dump

# 重启服务使配置生效
echo "  重启服务..."
docker restart openvista-maxkb > /dev/null
sleep 15

# 等待服务完全启动
for i in {1..20}; do
    if curl -s http://localhost:8080 > /dev/null 2>&1; then
        echo "✓ 数据库恢复完成"
        break
    fi
    sleep 3
done

# 完成
echo ""
echo "============================================"
echo "    安装完成！"
echo "============================================"
echo ""
echo "访问地址: http://localhost:8080"
echo ""
echo "如果备份包含用户数据，请使用备份中的账户登录。"
echo "如果是全新安装，请先注册一个新账户。"
echo ""
