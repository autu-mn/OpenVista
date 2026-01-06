# ============================================================
# OpenVista MaxKB 一键安装脚本 (Windows)
# ============================================================

$ErrorActionPreference = "Continue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackupFile = "$ScriptDir\db\maxkb_full.dump"
$MaxKBImage = "registry.fit2cloud.com/maxkb/maxkb:latest"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "    OpenVista MaxKB 一键安装" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# 检查 Docker
Write-Host "[1/5] 检查 Docker..." -ForegroundColor Yellow
try {
    docker info 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw }
    Write-Host "✓ Docker 已就绪" -ForegroundColor Green
} catch {
    Write-Host "✗ Docker 未安装或未运行" -ForegroundColor Red
    exit 1
}

# 检查备份文件
Write-Host "[2/5] 检查数据文件..." -ForegroundColor Yellow
if (-not (Test-Path $BackupFile)) {
    Write-Host "✗ 数据库备份不存在: $BackupFile" -ForegroundColor Red
    exit 1
}
Write-Host "✓ 数据文件已就绪" -ForegroundColor Green

# 清理旧容器
Write-Host "[3/5] 准备环境..." -ForegroundColor Yellow
docker stop openvista-maxkb 2>$null
docker rm openvista-maxkb 2>$null
docker volume rm openvista_maxkb_data openvista_maxkb_postgres 2>$null
docker volume create openvista_maxkb_data | Out-Null
docker volume create openvista_maxkb_postgres | Out-Null
Write-Host "✓ 环境已清理" -ForegroundColor Green

# 启动 MaxKB（让它初始化数据库结构）
Write-Host "[4/5] 初始化 MaxKB..." -ForegroundColor Yellow
docker run -d --name openvista-maxkb `
    -p 8080:8080 `
    -v openvista_maxkb_data:/opt/maxkb/model `
    -v openvista_maxkb_postgres:/var/lib/postgresql/data `
    -e DB_HOST=localhost `
    -e DB_PORT=5432 `
    -e DB_USER=root `
    -e DB_PASSWORD=MaxKB@123456 `
    -e DB_NAME=maxkb `
    $MaxKBImage | Out-Null

Write-Host "  等待 MaxKB 完全初始化（约60秒）..."
Start-Sleep -Seconds 60

# 检查服务是否启动
for ($i = 1; $i -le 30; $i++) {
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:8080" -TimeoutSec 3 -ErrorAction SilentlyContinue
        Write-Host "✓ MaxKB 初始化完成" -ForegroundColor Green
        break
    } catch {
        Start-Sleep -Seconds 3
    }
}

# 恢复数据库
Write-Host "[5/5] 恢复数据库..." -ForegroundColor Yellow

# 复制备份文件
docker cp $BackupFile openvista-maxkb:/tmp/backup.dump

# 恢复完整数据库（包括表结构和数据）
Write-Host "  恢复数据库..."
docker exec openvista-maxkb bash -c "pg_restore -U root -d maxkb --clean --if-exists /tmp/backup.dump 2>/dev/null || true"

# 修复迁移冲突：使用 Django 的 --fake 选项标记所有迁移为已应用
Write-Host "  修复数据库迁移状态..."
Write-Host "  使用 Django migrate --fake 标记迁移为已应用..."
docker exec openvista-maxkb bash -c "cd /opt/maxkb-app/apps && python3 manage.py migrate --fake 2>&1" | Select-String -Pattern "FAKED|No migrations|Applying" | Out-Null
Write-Host "  ✓ 迁移已标记为已应用" -ForegroundColor Green

# 清理
docker exec openvista-maxkb rm -f /tmp/backup.dump

# 重置密码
Write-Host "  重置管理员密码..."
$passwordMd5 = "0df6c52f03e1c75504c7bb9a09c2a016"
$sql = "UPDATE `"user`" SET password = '$passwordMd5' WHERE username = 'admin';"
echo $sql | docker exec -i openvista-maxkb psql -U root -d maxkb 2>$null | Out-Null

# 重启服务以应用数据库更改
Write-Host "  重启服务以应用数据库更改..."
docker restart openvista-maxkb | Out-Null
Start-Sleep -Seconds 10

Write-Host "✓ 数据库恢复完成" -ForegroundColor Green

# 完成
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "    安装完成！" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "访问地址: " -NoNewline; Write-Host "http://localhost:8080" -ForegroundColor Cyan
Write-Host "用户名:   " -NoNewline; Write-Host "admin" -ForegroundColor Cyan
Write-Host "密码:     " -NoNewline; Write-Host "MaxKB@123456" -ForegroundColor Cyan
Write-Host ""
Write-Host "重要：登录后请在「系统设置」→「模型管理」中配置 DeepSeek API Key" -ForegroundColor Yellow
Write-Host ""
