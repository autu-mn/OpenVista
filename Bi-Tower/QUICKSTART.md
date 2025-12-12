# 快速开始指南

## 步骤 1: 安装依赖

```bash
cd Bi-Tower
pip install -r requirements.txt
```

**注意**: PyTorch 需要根据你的系统和是否有 GPU 选择合适的版本。

- **有 NVIDIA GPU**: 访问 https://pytorch.org/ 获取 CUDA 版本
- **只有 CPU**: 使用默认的 CPU 版本即可

## 步骤 2: 准备数据

### 方式 1: 使用现有数据（最快）

如果你已经用 `tsa-try` 爬取了数据：

```bash
python prepare_data.py
```

这会自动找到 `tsa-try/data/` 下的所有项目数据。

### 方式 2: 批量爬取OpenDigger项目（推荐）

配置文件中已包含21个热门项目，可以直接爬取：

```bash
# 爬取前10个项目
python crawl_projects.py --num_projects 10

# 爬取所有21个项目
python crawl_projects.py --all

# 爬取后自动准备训练数据
python crawl_projects.py --num_projects 20 --auto_prepare
```

### 方式 3: 指定项目数量

```bash
# 只使用前 10 个项目
python prepare_data.py --num_projects 10
```

### 预期输出

```
准备双塔模型训练数据
============================================================
[1] 找到 2 个项目:
  - X-lab2017_open-digger
  - microsoft_vscode

[2] 加载项目数据...
  ✓ 共构建 100 个样本

[3] 划分数据集...
  训练集: 70 样本 (70.0%)
  验证集: 15 样本 (15.0%)
  测试集: 15 样本 (15.0%)

✓ 数据准备完成！
```

## 步骤 3: 训练模型

### CPU 训练（6-12小时）

```bash
python train.py --device cpu --epochs 20 --batch_size 8
```

### GPU 训练（30分钟-2小时）

```bash
python train.py --device cuda --epochs 50 --batch_size 16
```

### 预期输出

```
开始训练
============================================================
  设备: cpu
  训练样本: 70
  验证样本: 15
  Batch大小: 8
  学习率: 0.0001
  训练轮数: 20
============================================================

Epoch 1/20: 100%|███████| 9/9 [00:45<00:00]
  Epoch 1/20
    训练损失: 3.2456
    验证损失: 2.8932
    ✓ 保存最佳模型 (val_loss=2.8932)

Epoch 2/20: 100%|███████| 9/9 [00:42<00:00]
  Epoch 2/20
    训练损失: 2.5123
    验证损失: 2.4567
    ✓ 保存最佳模型 (val_loss=2.4567)

...

训练完成
============================================================
  总耗时: 15.3 分钟
  最佳验证损失: 1.2345
============================================================
```

## 步骤 4: 评估模型

```bash
python evaluate.py --save_predictions
```

### 预期输出

```
评估测试集
============================================================

整体性能:
  MAE: 1.2345
  RMSE: 1.8901
  MAPE: 15.67
  R2: 0.7234

分horizon性能:
  Horizon 1:
    MAE: 1.1234
    RMSE: 1.6789
    MAPE: 12.34
    R2: 0.7890

  Horizon 2:
    MAE: 1.2456
    RMSE: 1.8901
    MAPE: 16.78
    R2: 0.7123

  Horizon 3:
    MAE: 1.3456
    RMSE: 2.0123
    MAPE: 18.90
    R2: 0.6789

✓ 评估完成
  结果已保存: results/evaluation_results.json
============================================================
```

## 步骤 5: 预测新项目

```bash
python predict.py --project X-lab2017/open-digger --show_text
```

### 预期输出

```
双塔模型预测 - X-lab2017/open-digger
============================================================

[1] 加载项目数据...
  ✓ 项目: X-lab2017/open-digger
  ✓ 数据范围: 2020-08 ~ 2025-12

[2] 准备模型输入...
  ✓ 时序数据: torch.Size([1, 12, 20])
  ✓ 文本长度: 356 字符
  ✓ 最近月份: ['2025-10', '2025-11', '2025-12']

[3] 加载模型...
  ✓ 从 epoch 20 加载

[4] 执行预测...

预测结果
============================================================
  未来第 1 个月: 156.82
  未来第 2 个月: 162.45
  未来第 3 个月: 168.13

文本事件
============================================================
2025-10: Issue - Enhanced data visualization features
2025-11: Release - v2.1.0
2025-12: Major performance improvements and bug fixes
============================================================
```

## 一键运行（全流程）

### Windows

```bash
run_all.bat
```

### Linux/Mac

```bash
chmod +x run_all.sh
./run_all.sh
```

## 常见问题

### Q1: 显存不足（CUDA out of memory）

**解决方案**: 减小 batch size

```bash
python train.py --device cuda --batch_size 4
```

### Q2: 数据准备失败

**原因**: `tsa-try/data/` 目录下没有数据

**解决方案**: 先运行数据爬取脚本

```bash
cd ../tsa-try
python crawl_complete_data.py
```

### Q3: 训练太慢

**原因**: CPU 训练较慢

**解决方案**:
1. 使用 GPU（如果有）
2. 减少 epoch 数量: `--epochs 10`
3. 减少数据量: `prepare_data.py --num_projects 5`

### Q4: 找不到模块

**原因**: 依赖未安装

**解决方案**:

```bash
pip install -r requirements.txt
```

如果是 transformers 下载慢，可以使用镜像：

```bash
pip install transformers -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### Q5: DistilBERT 下载慢

**解决方案**: 使用国内镜像

```bash
export HF_ENDPOINT=https://hf-mirror.com
```

或者手动下载后放到 `~/.cache/huggingface/` 目录。

## 下一步

1. **扩展数据集**: 爬取更多项目（50+个）
2. **调整超参数**: 尝试不同的学习率、batch size
3. **可视化结果**: 绘制训练曲线、预测对比图
4. **对比实验**: 与 tsa-try 中的后处理方法对比

## 文件说明

- `data/checkpoints/best_model.pt` - 最佳模型
- `data/checkpoints/last_model.pt` - 最新模型
- `results/training_history.json` - 训练历史
- `results/evaluation_results.json` - 评估结果
- `results/predictions.json` - 预测详情

## 需要帮助？

查看完整文档: `README.md`

