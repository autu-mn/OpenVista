@echo off
chcp 65001 >nul
echo.
echo ============================================
echo     DataPulse 项目初始化
echo ============================================
echo.

:: 1. 检查 Git LFS
echo [1/3] 检查 Git LFS...
git lfs version >nul 2>&1
if %errorlevel% neq 0 (
    echo   Git LFS 未安装，请先安装:
    echo   下载地址: https://git-lfs.github.com/
    echo   或使用: winget install GitHub.GitLFS
    pause
    exit /b 1
)
git lfs install
echo √ Git LFS 已就绪

:: 2. 下载大型模型文件
echo [2/3] 下载 GitPulse 模型文件...
git lfs pull
echo √ 模型文件已下载

:: 3. 验证模型文件
echo [3/3] 验证模型文件...
if exist "backend\GitPulse\gitpulse_weights.pt" (
    for %%A in ("backend\GitPulse\gitpulse_weights.pt") do set SIZE=%%~zA
    echo √ 模型文件存在
) else (
    echo × 模型文件不存在，请重新运行 git lfs pull
    pause
    exit /b 1
)

echo.
echo ============================================
echo     初始化完成！
echo ============================================
echo.
echo 接下来:
echo   1. 后端: cd backend ^&^& pip install -r requirements.txt
echo   2. 前端: cd frontend ^&^& npm install
echo   3. 启动: 参考 README.md
echo.
pause


