#!/bin/bash
# 一键运行脚本

echo "========================================="
echo "双塔模型 - 完整流程"
echo "========================================="

# 1. 准备数据
echo ""
echo "[1/3] 准备数据..."
python prepare_data.py --num_projects 10

if [ $? -ne 0 ]; then
    echo "数据准备失败！"
    exit 1
fi

# 2. 训练模型
echo ""
echo "[2/3] 训练模型..."
python train.py --device cpu --epochs 20 --batch_size 8

if [ $? -ne 0 ]; then
    echo "模型训练失败！"
    exit 1
fi

# 3. 评估模型
echo ""
echo "[3/3] 评估模型..."
python evaluate.py --device cpu --save_predictions

if [ $? -ne 0 ]; then
    echo "模型评估失败！"
    exit 1
fi

echo ""
echo "========================================="
echo "✓ 全部完成！"
echo "========================================="
echo "检查点: data/checkpoints/best_model.pt"
echo "结果: results/evaluation_results.json"
echo "========================================="

