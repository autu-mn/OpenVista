# CHAOSS 社区健康评估模块

## 概述

本模块基于 CHAOSS（Community Health Analytics Open Source Software）标准，对开源项目进行社区健康评估。评估方法采用**按月计算评分，然后去除异常值后取平均值**的策略，确保评分更加稳定和可靠。

## 核心特性

### 1. 按月计算评分
- 对每个月份单独计算 CHAOSS 评分
- 使用最近12个月的数据（如果不足12个月，使用所有可用数据）
- 每个月的评分包括：
  - 总体得分
  - 各维度得分（Activity、Contributors、Responsiveness、Quality、Risk、Community Interest）

### 2. 异常值检测与过滤
- 使用 **IQR（四分位距）方法**检测异常值
- 使用1.5倍IQR作为异常值阈值（标准统计方法）
- 自动去除异常值后计算最终评分
- 记录去除的异常值数量，便于分析

### 3. 数据质量检测
- 自动检测无效数据（None、NaN、Inf、负数等）
- 检测零值过多的情况（可能是数据缺失）
- 检测异常大幅变化（可能是数据错误）
- 数据质量得分低于30%的指标会被跳过

## 计算流程

```
1. 获取时序数据（从本地 timeseries_for_model 目录）
   ↓
2. 提取所有可用月份
   ↓
3. 选择最近12个月（或所有可用月份）
   ↓
4. 对每个月单独计算评分：
   - 提取该月的所有指标值
   - 对每个指标归一化（使用历史最大值）
   - 按维度聚合（加权平均）
   - 计算总体得分
   ↓
5. 收集所有月份的评分
   ↓
6. 使用IQR方法检测异常值
   ↓
7. 去除异常值后计算最终评分（平均值）
   ↓
8. 生成评价报告
```

## 评分方法

### 单月评分计算

1. **指标归一化**
   - 对每个指标，使用该指标的历史最大值进行归一化
   - 公式：`normalized_score = (current_value / historical_max) * 100`
   - 限制在0-100范围内

2. **维度得分计算**
   - 对每个维度，收集该维度下的所有指标
   - 使用加权平均：`dimension_score = Σ(normalized_score_i * weight_i) / Σ(weight_i)`
   - 权重设置：
     - OpenRank、活跃度：1.5
     - 贡献者、参与者：1.3
     - 其他指标：1.0

3. **总体得分计算**
   - 各维度得分的简单平均：`overall_score = Σ(dimension_score) / dimension_count`

### 最终评分计算

1. **收集月度评分**
   - 收集所有月份的总体得分和各维度得分

2. **异常值检测（IQR方法）**
   ```
   Q1 = 25%分位数
   Q3 = 75%分位数
   IQR = Q3 - Q1
   下界 = Q1 - 1.5 * IQR
   上界 = Q3 + 1.5 * IQR
   异常值 = 不在 [下界, 上界] 范围内的值
   ```

3. **最终评分**
   - 去除异常值后，计算剩余评分的平均值
   - 记录去除的异常值数量

## API 接口

### GET `/api/chaoss/<repo_key>`

获取仓库的 CHAOSS 评价结果。

**响应示例：**
```json
{
  "repo_key": "odoo/odoo",
  "time_range": {
    "start": "2014-05",
    "end": "2025-12",
    "total_months": 141,
    "evaluated_months": 12
  },
  "monthly_scores": [
    {
      "month": "2025-01",
      "score": {
        "overall_score": 75.3,
        "dimensions": {
          "Activity": {"score": 80.5, "metrics_count": 5},
          "Contributors": {"score": 70.2, "metrics_count": 3},
          ...
        }
      }
    },
    ...
  ],
  "final_scores": {
    "overall_score": 73.8,
    "overall_level": "良好",
    "dimensions": {
      "Activity": {
        "score": 78.2,
        "level": "良好",
        "monthly_count": 12,
        "outliers_removed": 1
      },
      ...
    }
  },
  "report": {
    "summary": "综合评分: 73.8分 (良好)",
    "recommendations": [
      "项目健康度良好，继续保持当前发展态势",
      ...
    ]
  }
}
```

### GET `/api/chaoss/<repo_key>/dimensions`

获取 CHAOSS 维度映射信息。

## 数据来源

**重要：本模块仅从本地数据加载，不进行任何API调用或数据爬取。**

- **OpenDigger 指标**：从 `timeseries_for_model/*.json` 中的 `opendigger_metrics` 读取
- **数据格式**：`{"OpenRank": 385.77, "活跃度": 928.6, ...}`

## 文件结构

```
CHAOSSEvaluation/
├── __init__.py              # 模块初始化
├── chaoss_mapper.py         # CHAOSS 维度映射
├── chaoss_calculator.py     # 评分计算器（按月计算+异常值过滤）
└── README.md               # 本文档
```

## 使用示例

```python
from CHAOSSEvaluation import CHAOSSEvaluator
from data_service import DataService

# 初始化
data_service = DataService()
evaluator = CHAOSSEvaluator(data_service)

# 评估仓库
result = evaluator.evaluate_repo('odoo/odoo')

# 查看结果
print(f"综合评分: {result['final_scores']['overall_score']}")
print(f"等级: {result['final_scores']['overall_level']}")
```

## 注意事项

1. **数据质量**：如果某个月份的数据质量过低（质量得分<30%），该月份会被跳过
2. **异常值处理**：使用IQR方法自动检测和过滤异常值，确保最终评分稳定可靠
3. **月份选择**：默认使用最近12个月的数据，如果数据不足则使用所有可用数据
4. **归一化基准**：每个指标使用自己的历史最大值进行归一化，确保不同指标之间的可比性

