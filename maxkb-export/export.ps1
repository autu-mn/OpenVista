# ============================================================
# OpenVista MaxKB 数据库导出脚本 (Windows)
# 正确处理二进制文件，避免 PowerShell 编码问题
# ============================================================

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackupFile = "$ScriptDir\db\maxkb_full.dump"
$ContainerName = "openvista-maxkb"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "    OpenVista MaxKB 数据库导出" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# 检查容器是否运行
Write-Host "[1/3] 检查 MaxKB 容器..." -ForegroundColor Yellow
$containerStatus = docker inspect $ContainerName --format='{{.State.Running}}' 2>$null
if ($containerStatus -ne "true") {
    Write-Host "✗ MaxKB 容器未运行" -ForegroundColor Red
    Write-Host "请先启动 MaxKB: docker start $ContainerName" -ForegroundColor Yellow
    exit 1
}
Write-Host "✓ MaxKB 容器正在运行" -ForegroundColor Green

# 在容器内执行导出（避免 PowerShell 编码问题）
Write-Host "[2/3] 导出数据库..." -ForegroundColor Yellow
Write-Host "  在容器内执行 pg_dump..."

# 关键：使用 -f 参数在容器内保存文件，而不是通过 PowerShell 重定向
docker exec $ContainerName pg_dump -U root -d maxkb --no-owner --no-acl -Fc -f /tmp/maxkb_export.dump
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ 数据库导出失败" -ForegroundColor Red
    exit 1
}

# 从容器复制文件到本地
Write-Host "[3/3] 复制备份文件..." -ForegroundColor Yellow
docker cp "${ContainerName}:/tmp/maxkb_export.dump" $BackupFile
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ 复制备份文件失败" -ForegroundColor Red
    exit 1
}

# 清理容器内的临时文件
docker exec $ContainerName rm -f /tmp/maxkb_export.dump

# 验证文件
$fileSize = (Get-Item $BackupFile).Length / 1MB
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "    导出完成！" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "备份文件: $BackupFile"
Write-Host "文件大小: $([math]::Round($fileSize, 2)) MB"
Write-Host ""

if ($fileSize -lt 1) {
    Write-Host "⚠ 警告: 备份文件过小，可能是空数据库" -ForegroundColor Yellow
} else {
    Write-Host "✓ 导出成功，文件大小正常" -ForegroundColor Green
}

