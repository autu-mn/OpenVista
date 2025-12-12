@echo off
REM 一键运行脚本 (Windows)

echo =========================================
echo 双塔模型 - 完整流程
echo =========================================

REM 1. 准备数据
echo.
echo [1/3] 准备数据...
python prepare_data.py --num_projects 10

if %errorlevel% neq 0 (
    echo 数据准备失败！
    exit /b 1
)

REM 2. 训练模型
echo.
echo [2/3] 训练模型...
python train.py --device cpu --epochs 20 --batch_size 8

if %errorlevel% neq 0 (
    echo 模型训练失败！
    exit /b 1
)

REM 3. 评估模型
echo.
echo [3/3] 评估模型...
python evaluate.py --device cpu --save_predictions

if %errorlevel% neq 0 (
    echo 模型评估失败！
    exit /b 1
)

echo.
echo =========================================
echo √ 全部完成！
echo =========================================
echo 检查点: data\checkpoints\best_model.pt
echo 结果: results\evaluation_results.json
echo =========================================
pause

