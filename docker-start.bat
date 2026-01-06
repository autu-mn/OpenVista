@echo off
REM OpenVista Docker 启动脚本 (Windows)

echo ==========================================
echo OpenVista Docker 部署启动脚本
echo ==========================================

REM 检查 Docker 是否安装
where docker >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo 错误: Docker 未安装，请先安装 Docker Desktop
    pause
    exit /b 1
)

REM 检查 Docker Compose 是否安装
where docker-compose >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo 错误: Docker Compose 未安装
    pause
    exit /b 1
)

REM 检查 .env 文件
if not exist .env (
    echo 警告: .env 文件不存在，正在创建...
    (
        echo # GitHub API Token（必需）
        echo GITHUB_TOKEN=your_github_token_here
        echo.
        echo # MaxKB AI API（可选）
        echo MAXKB_AI_API=http://localhost:8080/api/application/{app_id}/chat/completions
        echo MAXKB_API_KEY=your_maxkb_api_key
        echo.
        echo # Hugging Face 模型配置
        echo USE_HUGGINGFACE=true
        echo HUGGINGFACE_MODEL_ID=Osacato/Gitpulse
    ) > .env
    echo 已创建 .env 文件，请编辑后填入正确的配置
    pause
)

REM 构建并启动服务
echo.
echo 正在构建 Docker 镜像...
docker-compose build

echo.
echo 正在启动服务...
docker-compose up -d

echo.
echo 等待服务启动...
timeout /t 5 /nobreak >nul

REM 检查服务状态
echo.
echo 服务状态:
docker-compose ps

echo.
echo ==========================================
echo 部署完成！
echo ==========================================
echo.
echo 访问地址:
echo   前端: http://localhost:3000
echo   后端: http://localhost:5000
echo   MaxKB: http://localhost:8080
echo.
echo 查看日志:
echo   docker-compose logs -f
echo.
echo 停止服务:
echo   docker-compose down
echo.

pause



