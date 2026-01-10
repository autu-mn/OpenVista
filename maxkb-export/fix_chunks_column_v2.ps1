# MaxKB Database Fix Script: Fix chunks column type (PowerShell)
# Encoding: UTF-8

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "MaxKB Database Fix: Fix chunks column type" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker container exists
$containerExists = docker ps -a | Select-String "openvista-maxkb"
if (-not $containerExists) {
    Write-Host "Error: MaxKB container (openvista-maxkb) not found" -ForegroundColor Red
    Write-Host "Please ensure MaxKB is running" -ForegroundColor Red
    exit 1
}

# Check if container is running
$containerRunning = docker ps | Select-String "openvista-maxkb"
if (-not $containerRunning) {
    Write-Host "Warning: MaxKB container is not running, starting..." -ForegroundColor Yellow
    docker start openvista-maxkb
    Start-Sleep -Seconds 5
}

# Get script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$sqlFile = Join-Path $scriptDir "fix_chunks_column_v2.sql"

# Check if SQL file exists
if (-not (Test-Path $sqlFile)) {
    Write-Host "Error: SQL script file not found: $sqlFile" -ForegroundColor Red
    exit 1
}

# Copy SQL script to container
Write-Host "[1/3] Copying fix script to container..." -ForegroundColor Yellow
docker cp $sqlFile openvista-maxkb:/tmp/fix_chunks_column_v2.sql

if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Failed to copy script" -ForegroundColor Red
    exit 1
}

# Execute SQL script
Write-Host "[2/3] Executing database fix..." -ForegroundColor Yellow
docker exec openvista-maxkb psql -U root -d maxkb -f /tmp/fix_chunks_column_v2.sql

if ($LASTEXITCODE -eq 0) {
    Write-Host "[3/3] Cleaning up temporary files..." -ForegroundColor Yellow
    docker exec openvista-maxkb rm -f /tmp/fix_chunks_column_v2.sql
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "Fix completed successfully!" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Please restart MaxKB service to apply changes:" -ForegroundColor Yellow
    Write-Host "  docker restart openvista-maxkb" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Red
    Write-Host "Fix failed" -ForegroundColor Red
    Write-Host "============================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please check error messages and try again" -ForegroundColor Red
    exit 1
}

