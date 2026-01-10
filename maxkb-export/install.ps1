# ============================================================
# OpenVista MaxKB 一键安装脚本 (Windows)
# ============================================================

$ErrorActionPreference = "Continue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackupFile = "$ScriptDir\db\maxkb_full.dump"
$MaxKBImage = "registry.fit2cloud.com/maxkb/maxkb"

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
    Write-Host "请确保 db/maxkb_full.dump 文件存在" -ForegroundColor Red
    exit 1
}
$fileSize = (Get-Item $BackupFile).Length / 1MB
Write-Host "✓ 数据文件已就绪 (大小: $([math]::Round($fileSize, 2)) MB)" -ForegroundColor Green

# 检查备份文件大小（如果太小说明是空备份）
if ($fileSize -lt 1) {
    Write-Host "⚠ 警告: 备份文件过小，可能是空数据库备份" -ForegroundColor Yellow
    Write-Host "  请确保备份文件包含完整数据（通常 > 10MB）" -ForegroundColor Yellow
}

# 清理旧容器和数据卷
Write-Host "[3/5] 准备环境..." -ForegroundColor Yellow
docker stop openvista-maxkb 2>$null
docker rm openvista-maxkb 2>$null
# 创建新的数据卷（不删除旧的，避免误删用户数据）
docker volume create openvista_maxkb_data 2>$null | Out-Null
docker volume create openvista_maxkb_postgres 2>$null | Out-Null
Write-Host "✓ 环境已准备" -ForegroundColor Green

# 启动 MaxKB
Write-Host "[4/5] 启动 MaxKB..." -ForegroundColor Yellow
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

Write-Host "  等待 MaxKB 初始化（约60秒）..."
Start-Sleep -Seconds 60

# 检查服务是否启动
$maxRetries = 30
for ($i = 1; $i -le $maxRetries; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8080" -TimeoutSec 3 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Write-Host "✓ MaxKB 启动成功" -ForegroundColor Green
            break
        }
    } catch {
        if ($i -eq $maxRetries) {
            Write-Host "✗ MaxKB 启动超时" -ForegroundColor Red
            exit 1
        }
        Start-Sleep -Seconds 3
    }
}

# 恢复数据库
Write-Host "[5/5] 恢复数据库..." -ForegroundColor Yellow

# 复制备份文件到容器
docker cp $BackupFile openvista-maxkb:/tmp/backup.dump
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ 复制备份文件失败" -ForegroundColor Red
    exit 1
}

# 先清理数据库中的所有表（确保干净状态）
Write-Host "  清理现有数据库..."
docker exec openvista-maxkb bash -c "psql -U root -d maxkb -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;' 2>/dev/null || true" | Out-Null

# 使用 pg_restore 恢复（--no-owner --no-acl 避免权限问题）
Write-Host "  正在恢复数据（可能需要几分钟）..."
docker exec openvista-maxkb bash -c "pg_restore -U root -d maxkb --no-owner --no-acl --verbose /tmp/backup.dump 2>&1 | grep -v 'ERROR' | tail -5" | Out-Null

# 清理临时文件
docker exec openvista-maxkb rm -f /tmp/backup.dump

# 重置管理员密码为默认值（备份中的密码可能不同）
Write-Host "  重置管理员密码..."
$passwordMd5 = "0df6c52f03e1c75504c7bb9a09c2a016"  # MaxKB@123456 的 MD5 哈希值
$sql = "UPDATE `"user`" SET password = '$passwordMd5' WHERE username = 'admin';"
echo $sql | docker exec -i openvista-maxkb psql -U root -d maxkb 2>$null | Out-Null

# 重启服务使配置生效
Write-Host "  重启服务..."
docker restart openvista-maxkb | Out-Null
Start-Sleep -Seconds 15

# 等待服务完全启动
for ($i = 1; $i -le 20; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8080" -TimeoutSec 3 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Write-Host "✓ 数据库恢复完成" -ForegroundColor Green
            break
        }
    } catch {
        Start-Sleep -Seconds 3
    }
}

# 完成
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "    安装完成！" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "访问地址: " -NoNewline; Write-Host "http://localhost:8080" -ForegroundColor Cyan
Write-Host ""
Write-Host "默认登录凭据：" -ForegroundColor Yellow
Write-Host "  用户名: admin" -ForegroundColor Yellow
Write-Host "  密码:   MaxKB@123456" -ForegroundColor Yellow
Write-Host ""
Write-Host "提示: 如果备份中包含其他用户，请使用备份中的账户登录。" -ForegroundColor Cyan
Write-Host ""
