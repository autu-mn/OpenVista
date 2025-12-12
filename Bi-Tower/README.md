# 双塔模型（Dual-Tower Model）实现

基于时序数据和文本数据的联合预测模型。

## 架构说明

```
┌──────────────────────────────────────────────────────┐
│                    训练阶段                           │
└──────────────────────────────────────────────────────┘

【时序塔】                        【文本塔】
   ↓                                ↓
时序数据                          文本数据
[1.2, 3.4, 5.6, ...]             "Issue增多，PR活跃..."
   ↓                                ↓
时序编码器                        LLM编码器
(LSTM/Transformer)                (DistilBERT)
   ↓                                ↓
时序向量 [h1]                     文本向量 [h2]
(128维)                           (768维)
   │                                │
   └────────────┬──────────────────┘
                ↓
          融合层 (Fusion)
        [concat + MLP]
                ↓
         联合表示 [h]
                ↓
          预测头 (MLP)
                ↓
         未来3个月预测值
```

## 特点

- **轻量级设计**：使用 DistilBERT（66M参数）而非 BERT-large
- **高效训练**：冻结文本编码器，只训练融合层和预测头
- **支持CPU/GPU**：可在普通电脑上运行
- **小数据友好**：10-20个项目数据即可开始实验

## 文件结构

```
Bi-Tower/
├── README.md              # 本文档
├── config.py              # 配置文件
├── model.py               # 双塔模型定义
├── dataset.py             # 数据加载器
├── prepare_data.py        # 数据准备脚本
├── train.py               # 训练脚本
├── evaluate.py            # 评估脚本
├── predict.py             # 预测脚本
├── requirements.txt       # Python依赖
├── data/                  # 数据目录
│   ├── raw/              # 原始数据
│   ├── processed/        # 处理后的数据
│   └── checkpoints/      # 模型检查点
└── results/              # 实验结果
```

## 快速开始

### 1. 安装依赖

```bash
cd Bi-Tower
pip install -r requirements.txt
```

### 2. 准备数据

```bash
# 批量爬取多个项目数据
python prepare_data.py --num_projects 10
```

### 3. 训练模型

```bash
# CPU训练（6-12小时）
python train.py --device cpu --epochs 20

# GPU训练（30分钟-2小时）
python train.py --device cuda --epochs 50
```

### 4. 评估模型

```bash
python evaluate.py --checkpoint data/checkpoints/best_model.pt
```

### 5. 预测

```bash
python predict.py --project X-lab2017/open-digger --checkpoint data/checkpoints/best_model.pt
```

## 数据要求

- **最少**：10个项目，每个50个月 → 500个样本
- **推荐**：20个项目 → 1000个样本
- **理想**：50+个项目 → 2500+个样本

## 可用的OpenDigger项目（21个）

配置文件中已包含21个OpenDigger已知仓库：

**编程语言与编译器**：NixOS/nixpkgs, llvm/llvm-project, pytorch/pytorch, flutter/flutter, zed-industries/zed

**开发工具与平台**：microsoft/vscode, microsoft/winget-pkgs, godotengine/godot, elastic/kibana, grafana/grafana

**框架与库**：home-assistant/core, odoo/odoo, zephyrproject-rtos/zephyr, vllm-project/vllm

**其他**：X-lab2017/open-digger, digitalinnovationone/dio-lab-open-source, 等

## 性能预期

### 小规模实验（10个项目）
- 训练时间（CPU）：6-12小时
- 训练时间（GPU）：30分钟-2小时
- 预期效果：可能不如后处理方法（数据不足）
- 价值：验证架构可行性

### 中等规模（50个项目）
- 训练时间（GPU）：3-6小时
- 预期效果：与后处理方法持平或略好
- 价值：真实评估双塔模型优势

### 大规模（100+项目）
- 训练时间（GPU）：12-24小时
- 预期效果：显著优于后处理方法
- 价值：发布预训练模型

## 与现有方法对比

| 维度 | 后处理方法 | 双塔模型 |
|------|-----------|---------|
| 训练需求 | 无 | 有 |
| 数据需求 | 1个项目 | 10+个项目 |
| 训练时间 | 0 | 6-12小时 (CPU) |
| 推理速度 | 慢（需调用LLM API） | 快（本地推理） |
| 可解释性 | 高（提供reasoning） | 低（黑盒） |
| 效果上限 | 受限于Prompt | 更高（端到端学习） |
| 适用场景 | 快速原型、小数据 | 大规模应用 |

## 技术细节

### 模型参数量
```
时序编码器 (LSTM): ~200K
文本编码器 (DistilBERT, 冻结): 66M (不训练)
融合层: ~100K
预测头: ~500
总计训练参数: ~300K
```

### 内存需求
```
模型大小: ~260MB
训练时显存: 2-4GB (batch_size=16)
推理时显存: 0.5-1GB
CPU内存: 8GB+
```

## 常见问题

### Q: 为什么选择 DistilBERT 而不是 BERT？
A: DistilBERT 只有 66M 参数（BERT-base 110M），但保留了 97% 的性能，更适合在普通电脑上运行。

### Q: 为什么冻结文本编码器？
A: 减少训练参数，加快训练速度，防止小数据集上过拟合。

### Q: 可以用 CPU 训练吗？
A: 可以，但训练时间较长（6-12小时 vs 30分钟-2小时）。

### Q: 10个项目数据够吗？
A: 够做概念验证，但效果可能不如后处理方法。建议至少50个项目。

### Q: 如何获取更多数据？
A: 使用 OpenDigger API 批量爬取热门项目（30000+可选）。

## 后续改进方向

1. **数据增强**：扩展到100+个项目
2. **模型优化**：尝试 Transformer 时序编码器
3. **多任务学习**：同时预测多个指标
4. **迁移学习**：预训练后fine-tune特定项目
5. **可解释性**：添加 Attention 可视化

## 参考资料

- [DistilBERT](https://huggingface.co/docs/transformers/model_doc/distilbert)
- [PyTorch LSTM](https://pytorch.org/docs/stable/generated/torch.nn.LSTM.html)
- [OpenDigger API](https://github.com/X-lab2017/open-digger)

