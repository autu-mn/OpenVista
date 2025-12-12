# 双塔模型预测目标设计

## 当前问题

**现状**：只预测单一指标（community_engagement/activity/openrank）

**问题**：
1. ❌ 不能全面反映项目状态
2. ❌ 单一指标可能不够稳定
3. ❌ 没有利用双塔模型的多任务学习能力
4. ❌ 无法回答"项目会如何发展"的完整问题

## 更好的预测方案

### 方案 1: 多任务学习（推荐）

**同时预测多个关键指标**：

```python
输出维度：[batch_size, 预测窗口, 指标数量]

预测目标：
1. activity_score（活跃度）
2. community_engagement（社区参与度）
3. issues_count（Issue数量）
4. prs_count（PR数量）
5. contributors_count（贡献者数）

输出形状：[batch_size, 3, 5]
         ↑      ↑   ↑
        批次   3个月 5个指标
```

**优势**：
- ✅ 全面反映项目状态
- ✅ 多任务学习提升泛化能力
- ✅ 可以分析不同维度的变化

### 方案 2: 多维度预测

**预测数值 + 趋势 + 等级**：

```python
输出1：数值预测 [batch_size, 3]
  - activity_score 的未来值

输出2：趋势分类 [batch_size, 3]
  - 上升/下降/持平（3类）

输出3：活跃度等级 [batch_size, 3]
  - 高/中/低（3类）

总输出：[batch_size, 3, 3]
```

**优势**：
- ✅ 既有数值又有定性判断
- ✅ 更符合实际应用需求
- ✅ 可解释性更强

### 方案 3: 综合健康度评分（最推荐）

**预测一个综合指标，但包含多个维度**：

```python
项目健康度 = f(
    activity_score,      # 活跃度
    community_engagement, # 社区参与
    growth_rate,         # 增长率
    stability,           # 稳定性
    contributor_quality  # 贡献者质量
)

输出：[batch_size, 3]
```

**但训练时用多任务学习**：
```python
# 主任务：预测综合健康度
主损失 = MSE(健康度预测, 健康度真实值)

# 辅助任务：预测各个组件
辅助损失 = MSE(activity预测, activity真实值) + 
          MSE(community预测, community真实值) + ...

总损失 = 主损失 + 0.3 * 辅助损失
```

## 推荐方案：多任务学习

### 预测目标（5个核心指标）

```python
预测目标 = {
    'activity_score': '综合活跃度',
    'community_engagement': '社区参与度', 
    'issues_count': 'Issue数量',
    'prs_count': 'PR数量',
    'contributors_count': '贡献者数'
}

输出形状：[batch_size, 3, 5]
```

### 模型架构调整

```python
class DualTowerModel(nn.Module):
    def __init__(self):
        # ... 时序塔和文本塔不变 ...
        
        # 预测头（多任务）
        self.predictors = nn.ModuleDict({
            'activity': nn.Linear(128, 3),
            'community': nn.Linear(128, 3),
            'issues': nn.Linear(128, 3),
            'prs': nn.Linear(128, 3),
            'contributors': nn.Linear(128, 3),
        })
    
    def forward(self, time_series, text_input_ids, text_attention_mask):
        # ... 融合层不变 ...
        
        # 多任务预测
        predictions = {
            'activity': self.predictors['activity'](fused),
            'community': self.predictors['community'](fused),
            'issues': self.predictors['issues'](fused),
            'prs': self.predictors['prs'](fused),
            'contributors': self.predictors['contributors'](fused),
        }
        
        return predictions
```

### 损失函数

```python
def multi_task_loss(predictions, targets, weights=None):
    """
    predictions: dict of [batch, 3]
    targets: dict of [batch, 3]
    weights: dict of float (各任务权重)
    """
    if weights is None:
        weights = {
            'activity': 0.3,
            'community': 0.3,
            'issues': 0.15,
            'prs': 0.15,
            'contributors': 0.1
        }
    
    total_loss = 0
    for key in predictions:
        loss = mse_loss(predictions[key], targets[key])
        total_loss += weights[key] * loss
    
    return total_loss
```

## 为什么这样更好？

### 1. 更全面的评估

```
单一指标：
  "community_engagement 会从 3.5 升到 4.0"
  → 但不知道其他方面如何

多指标：
  "activity: 156 → 162 ✓
   community: 3.5 → 4.0 ✓
   issues: 45 → 50 ✓
   prs: 15 → 18 ✓
   contributors: 20 → 22 ✓"
  → 全面了解项目发展
```

### 2. 多任务学习优势

```
共享表示学习：
  - 时序塔和文本塔学到通用模式
  - 不同任务互相促进
  - 泛化能力更强

例如：
  学习到"版本发布 → 活跃度提升"
  这个知识对所有指标都有帮助
```

### 3. 实际应用价值

```
可以回答：
  ✓ "项目会变得更活跃吗？"（activity）
  ✓ "社区参与度会提升吗？"（community）
  ✓ "会有更多Issue吗？"（issues）
  ✓ "会有更多PR吗？"（prs）
  ✓ "贡献者会增加吗？"（contributors）

而不是只回答：
  "community_engagement 会变化"
```

## 实现建议

### 步骤1: 修改数据准备

```python
# prepare_data.py
targets = {
    'activity': timeseries_features['activity_score'],
    'community': timeseries_features['community_engagement'],
    'issues': timeseries_features['issues_count'],
    'prs': timeseries_features['prs_count'],
    'contributors': timeseries_features['contributors_count'],
}
```

### 步骤2: 修改模型

```python
# model.py
# 改为多任务预测头
```

### 步骤3: 修改训练

```python
# train.py
# 使用多任务损失函数
```

## 总结

**当前**：预测1个指标（community_engagement）
**改进**：预测5个核心指标（多任务学习）

**优势**：
- ✅ 更全面
- ✅ 更稳定
- ✅ 更实用
- ✅ 更好的泛化能力

需要我实现这个多任务学习版本吗？





