# 预训练模型策略

## 现状分析

### ✅ 我们已经使用的预训练模型

#### 1. 文本塔（DistilBERT）
```python
# 66M 参数，预训练在大规模文本语料上
self.text_encoder = DistilBertModel.from_pretrained('distilbert-base-uncased')

# 冻结参数，不需要训练
for param in self.text_encoder.parameters():
    param.requires_grad = False
```

**优势**：
- ✅ 已在海量文本上预训练
- ✅ 理解自然语言语义
- ✅ 66M 参数，但**完全冻结**，不占训练资源
- ✅ 推理速度快

#### 2. 实际训练参数

| 组件 | 参数量 | 是否训练 |
|------|--------|---------|
| 文本编码器 (DistilBERT) | 66M | ❌ 冻结 |
| 时序编码器 (LSTM) | ~200K | ✅ 训练 |
| 融合层 (MLP) | ~100K | ✅ 训练 |
| 预测头 (MLP) | ~500 | ✅ 训练 |
| **总计** | **66.3M** | **只训练 300K** |

**结论**：我们只需要训练 **0.45%** 的参数！

## 🚀 进一步优化方案

### 方案 1: 使用更好的文本预训练模型

#### 可选模型对比

| 模型 | 参数量 | 性能 | 推荐场景 |
|------|--------|------|---------|
| **DistilBERT** (当前) | 66M | ⭐⭐⭐⭐ | 平衡选择 |
| TinyBERT | 14M | ⭐⭐⭐ | 极度轻量 |
| MiniLM | 22M | ⭐⭐⭐⭐ | 速度优先 |
| RoBERTa-base | 125M | ⭐⭐⭐⭐⭐ | 效果优先 |
| DeBERTa-v3-small | 44M | ⭐⭐⭐⭐⭐ | 最佳平衡 |

#### 推荐：DeBERTa-v3-small
```python
# 44M 参数，比 DistilBERT 更强
model_name = 'microsoft/deberta-v3-small'

# 性能提升：
# - 更好的注意力机制
# - 更强的语义理解
# - 参数更少
```

### 方案 2: 时序预训练模型（可选）

#### 可用的时序预训练模型

**问题**：目前没有针对"开源项目时序"的专门预训练模型

**可选方案**：

1. **不使用预训练**（推荐）
   - 时序特征简单（20维）
   - LSTM 参数少（200K）
   - 从头训练效果已经不错

2. **Lag-Llama**（实验性）
   ```python
   # Hugging Face 上的时序预训练模型
   from lag_llama import LagLlamaForPrediction
   
   # 但是：
   # - 参数很大（~300M）
   # - 不一定适合我们的场景
   # - 训练反而更慢
   ```

3. **TimeGPT**（商业）
   - 性能最好
   - 但需要付费 API
   - 不适合学术研究

### 方案 3: 迁移学习策略

#### 3.1 在大规模项目上预训练

```python
# 步骤1：在 50+ 个项目上预训练整个双塔模型
# 步骤2：在特定项目上 fine-tune

# 这样可以：
# ✓ 学到通用的"开源项目发展模式"
# ✓ 在新项目上快速适应（只需少量数据）
# ✓ 效果更好
```

#### 3.2 多任务学习

```python
# 同时训练多个任务：
# 1. 预测未来数值
# 2. 预测趋势方向（上升/下降）
# 3. 预测活跃度等级

# 优势：
# ✓ 共享表示学习
# ✓ 提高泛化能力
```

## 💡 立即可用的优化

### 优化 1: 切换到 DeBERTa（更强）

```python
# config.py
TEXT_MODEL_NAME = 'microsoft/deberta-v3-small'  # 从 distilbert 切换

# 优势：
# - 参数更少（44M vs 66M）
# - 性能更好（+2-3% 准确度）
# - 速度相近
```

### 优化 2: 使用领域自适应的预训练模型

```python
# 如果有在 GitHub 文本上预训练的模型
TEXT_MODEL_NAME = 'microsoft/codebert-base'  # 理解代码和技术文本

# 或者
TEXT_MODEL_NAME = 'sentence-transformers/all-MiniLM-L6-v2'  # 语义相似度优化
```

## 🎯 推荐配置

### 配置 1: 轻量级（最快）
```python
TEXT_MODEL_NAME = 'sentence-transformers/all-MiniLM-L6-v2'  # 22M
TIME_HIDDEN_DIM = 64  # 减少 LSTM 维度
FUSION_HIDDEN_DIM = 128

# 总训练参数: ~150K
# 训练时间: 3-5 小时 (CPU)
```

### 配置 2: 平衡型（推荐）
```python
TEXT_MODEL_NAME = 'microsoft/deberta-v3-small'  # 44M
TIME_HIDDEN_DIM = 128
FUSION_HIDDEN_DIM = 256

# 总训练参数: ~300K
# 训练时间: 6-8 小时 (CPU)
```

### 配置 3: 高性能（最好效果）
```python
TEXT_MODEL_NAME = 'microsoft/deberta-v3-base'  # 86M
TIME_HIDDEN_DIM = 256
FUSION_HIDDEN_DIM = 512

# 总训练参数: ~800K
# 训练时间: 12-15 小时 (CPU)
```

## 📊 性能对比（预期）

| 配置 | 训练参数 | 训练时间 | MAE | 适用场景 |
|------|---------|---------|-----|---------|
| 轻量级 | 150K | 3-5h | ~1.5 | 快速验证 |
| 平衡型 | 300K | 6-8h | ~1.2 | 日常使用 |
| 高性能 | 800K | 12-15h | ~1.0 | 最佳效果 |

## 🔧 实现代码

我可以为你创建：
1. `config_variants.py` - 不同配置预设
2. `model_variants.py` - 支持多种预训练模型
3. `transfer_learning.py` - 迁移学习脚本

需要我实现这些优化吗？

