# 训练过程详解

## 核心区别：训练 vs 交叉验证

### 后处理方法（tsa-try）- 交叉验证

```
不需要训练！直接用滚动窗口交叉验证：

Fold 1: ████████████ → 预测3个月
        训练数据(12月)  测试(3月)

Fold 2:  ████████████ → 预测3个月
         训练数据(12月)  测试(3月)

Fold 3:   ████████████ → 预测3个月
          训练数据(12月)  测试(3月)

...

Fold 50:                ████████████ → 预测3个月
                        训练数据(12月)  测试(3月)

每个fold：
1. ARIMA 用训练数据拟合
2. 预测未来3个月
3. 调用 DeepSeek 调整
4. 计算误差
```

**特点**：
- ❌ 没有模型训练阶段
- ✅ 每个fold独立预测
- ✅ ARIMA/Prophet 每次重新拟合
- ✅ DeepSeek 每次调用 API

### 双塔模型 - 训练 + 验证

```
┌─────────────────────────────────────────────────────────┐
│  阶段1：训练阶段（Train）                                │
└─────────────────────────────────────────────────────────┘

将所有数据划分为 训练集(70%) / 验证集(15%) / 测试集(15%)

训练集（111个样本）：
  项目1: [样本1, 样本2, ..., 样本50]
  项目2: [样本1, 样本2, ..., 样本40]  
  项目3: [样本1, 样本2, ..., 样本21]

验证集（23个样本）：随机抽取
测试集（25个样本）：随机抽取

训练过程（每个Epoch）：
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Epoch 1/50:
  训练阶段：
    Batch 1: [样本1-32] → 前向传播 → 计算loss → 反向传播
    Batch 2: [样本33-64] → 前向传播 → 计算loss → 反向传播
    Batch 3: [样本65-96] → 前向传播 → 计算loss → 反向传播
    Batch 4: [样本97-111] → 前向传播 → 计算loss → 反向传播
    → 训练损失: 2.5
  
  验证阶段：
    用验证集评估 → 验证损失: 2.8
    → 保存最佳模型（如果loss更低）

Epoch 2/50:
  训练阶段：... (模型参数持续更新)
  验证阶段：验证损失: 2.4 ✓ 新的最佳模型！

...

Epoch 50/50:
  训练阶段：...
  验证阶段：验证损失: 1.2
  
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

训练完成！模型参数已经学习完毕

┌─────────────────────────────────────────────────────────┐
│  阶段2：测试阶段（Test）                                 │
└─────────────────────────────────────────────────────────┘

加载最佳模型（验证集loss最低的那个）

用测试集（25个样本）评估：
  样本1 → 预测 → 计算误差
  样本2 → 预测 → 计算误差
  ...
  样本25 → 预测 → 计算误差

最终报告：
  MAE: 1.2
  RMSE: 1.8
  R²: 0.75
```

**特点**：
- ✅ 有模型训练阶段（学习参数）
- ✅ 一次训练，永久使用
- ✅ 训练/验证/测试 三个独立集合
- ❌ 不是交叉验证

## 详细对比

| 维度 | 后处理方法 | 双塔模型 |
|------|-----------|---------|
| **方法类型** | 交叉验证 | 训练-验证-测试 |
| **数据划分** | 时间序列滚动窗口 | 随机划分（70/15/15） |
| **模型状态** | 每个fold重新拟合 | 训练一次，参数固定 |
| **评估方式** | 50+个fold的平均 | 单次测试集评估 |
| **训练时间** | 无需训练 | 需要训练（6-12小时） |
| **推理时间** | 每次2-5秒（调用API） | 每次<0.1秒 |
| **适用场景** | 单项目评估 | 多项目泛化 |

## 训练过程核心步骤

### 1. 数据准备（prepare_data.py）

```python
# 从多个项目构建样本
projects = ['X-lab2017/open-digger', 'microsoft/vscode', ...]

all_samples = []
for project in projects:
    # 滑动窗口构建样本
    for month in range(12, len(time_axis)-3):
        sample = {
            'time_series': last_12_months,  # [12, 17]
            'text': recent_3_months_events,
            'target': next_3_months_values  # [3]
        }
        all_samples.append(sample)

# 随机划分（打乱项目和时间）
train = 70% 
val = 15%
test = 15%
```

### 2. 训练循环（train.py）

```python
for epoch in range(50):
    # ========== 训练阶段 ==========
    model.train()
    for batch in train_loader:
        # 前向传播
        time_series = batch['time_series']  # [32, 12, 17]
        text_ids = batch['input_ids']       # [32, 512]
        target = batch['target']            # [32, 3]
        
        prediction = model(time_series, text_ids)  # [32, 3]
        loss = mse_loss(prediction, target)
        
        # 反向传播（更新参数）
        loss.backward()
        optimizer.step()
    
    # ========== 验证阶段 ==========
    model.eval()
    with torch.no_grad():
        for batch in val_loader:
            prediction = model(time_series, text_ids)
            val_loss += mse_loss(prediction, target)
    
    # ========== 保存最佳模型 ==========
    if val_loss < best_loss:
        torch.save(model.state_dict(), 'best_model.pt')
        best_loss = val_loss
```

### 3. 评估（evaluate.py）

```python
# 加载最佳模型
model.load_state_dict(torch.load('best_model.pt'))
model.eval()

# 在测试集上评估
for batch in test_loader:
    prediction = model(time_series, text_ids)
    # 计算MAE, RMSE, R²
```

## 为什么不用交叉验证？

### 交叉验证的问题（对深度学习）

1. **计算成本太高**
   ```
   50 folds × 50 epochs = 2500 次完整训练
   时间：2500 × 6小时 = 15000小时 = 625天！
   ```

2. **数据泄露风险**
   ```
   交叉验证会让同一个项目的不同月份
   出现在训练集和测试集中
   → 模型可能记住项目特征
   ```

3. **不符合深度学习范式**
   ```
   深度学习需要：
   - 大量数据一起训练（学习通用模式）
   - 固定的训练集/验证集/测试集
   - 早停（early stopping）需要验证集
   ```

### 训练-验证-测试的优势

1. **标准范式**
   ```
   这是所有深度学习模型的标准流程
   - ImageNet（图像分类）
   - BERT（自然语言处理）
   - AlphaGo（强化学习）
   都用这个方法
   ```

2. **效率高**
   ```
   训练一次（6-12小时）
   ↓
   永久使用（0.1秒/预测）
   ```

3. **学习泛化能力**
   ```
   从多个项目学习通用规律：
   "版本发布 → 活跃度提升"
   "重大Bug → 短期下降"
   "核心贡献者离开 → 长期影响"
   ```

## 什么时候需要交叉验证？

### 场景 1: 小数据集
```python
if num_samples < 100:
    # 数据太少，用K-fold交叉验证
    # 充分利用每个样本
    use_cross_validation()
```

### 场景 2: 传统机器学习
```python
# ARIMA, Prophet, XGBoost（浅层）
# 训练快，可以多次重复
for fold in range(k_folds):
    model = ARIMA()
    model.fit(train)
    model.predict(test)
```

### 场景 3: 超参数调优
```python
# 找最佳超参数时
for lr in [1e-3, 1e-4, 1e-5]:
    for hidden_dim in [64, 128, 256]:
        # 每个配置都用交叉验证评估
        cv_score = cross_validate(model, data)
```

## 我们的选择

**双塔模型**：训练-验证-测试（推荐）
- 159个样本（3个项目）
- 足够训练深度学习模型
- 学习跨项目的泛化规律

**后处理方法**：交叉验证
- 1个项目，65个月
- 适合传统时序模型
- 评估单项目性能

## 混合方案（可选）

如果想结合两者优势：

```python
# 1. 先用训练-验证-测试训练双塔模型
model = train_dual_tower(all_projects)

# 2. 再用交叉验证评估单个项目
for fold in rolling_window(target_project):
    prediction = model.predict(fold)
    # 评估在特定项目上的表现
```

这样既有泛化能力，又能细致评估！

## 总结

| 方法 | 适用场景 | 优势 | 劣势 |
|------|---------|------|------|
| **交叉验证** | 后处理方法 | 充分利用数据 | 无法学习跨项目规律 |
| **训练-验证-测试** | 双塔模型 | 学习泛化规律 | 需要较多数据 |

我们的双塔模型使用**训练-验证-测试**，这是深度学习的标准流程！





