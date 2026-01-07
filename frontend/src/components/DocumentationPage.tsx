import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Book, ChevronRight, Zap, Award, Brain, Database, TrendingUp, Code } from 'lucide-react'

interface DocumentationPageProps {
  isOpen: boolean
  onClose: () => void
}

const docSections = [
  {
    id: 'overview',
    title: '项目概述',
    icon: Book,
    content: `## OpenVista 项目概述

OpenVista 是面向开源项目的数据分析平台，核心解决两个问题：一是如何客观评价一个开源项目的健康状态，二是如何预测项目未来的发展趋势。

### 我们做了什么

**1. 构建了完整的数据采集流程**

从 OpenDigger 获取 16 个核心指标的月度数据，从 GitHub API 补充仓库描述、README、Issue、PR 等文本信息。数据自动按月对齐，支持一键爬取任意 GitHub 仓库。

**2. 训练了 GitPulse 多模态预测模型**

不同于传统的 ARIMA、Prophet 等统计模型，GitPulse 使用 Transformer 架构编码时序特征，同时融合项目文本描述，实现了 R²=0.7559 的预测精度，方向准确率达到 86.68%。

**3. 实现了 CHAOSS 标准的健康评价体系**

将 OpenDigger 指标映射到 Linux 基金会 CHAOSS 框架的 6 个维度，通过加权平均、异常值处理、数据质量评估等方法，输出 0-100 的健康评分和具体改进建议。

**4. 集成了 AI 智能分析**

对接 DeepSeek API 和 MaxKB 知识库，支持自然语言问答、Issue 智能分类、预测结果归因解释。

### 技术栈

| 层级 | 技术选型 |
|-----|---------|
| 前端 | React 18 + TypeScript + Tailwind CSS + Framer Motion |
| 后端 | Python Flask + RESTful API |
| 模型 | PyTorch + Transformers (DistilBERT) |
| 数据源 | OpenDigger API + GitHub GraphQL API |
| AI | DeepSeek API + MaxKB 知识库 |`
  },
  {
    id: 'gitpulse',
    title: 'GitPulse 预测模型',
    icon: Zap,
    content: `## GitPulse 模型架构

GitPulse 是我们训练的多模态时序预测模型，结合 Transformer 时序编码和 DistilBERT 文本编码，对开源项目指标进行预测。

### 模型结构

\`\`\`
输入层:
├─ 时序输入: [batch, 128, 16]   # 128个月历史，16个指标
└─ 文本输入: [batch, 128]       # 项目描述 token

时序编码器 (TransformerTSEncoder):
├─ input_proj: Linear(16 → 128) + LayerNorm + Dropout
├─ pos_embedding: Parameter[1, 128, 128]  # 可学习位置编码
├─ encoder: TransformerEncoder(d_model=128, nhead=4, layers=2)
└─ 输出: [batch, 128, 128]

文本编码器 (TextEncoder):
├─ DistilBERT: 768维预训练表示 (冻结)
├─ attn_pool: 注意力池化 → [batch, 768]
├─ proj: Linear(768→256) + GELU + Linear(256→128)
└─ 输出: [batch, 128]

融合层 (AdaptiveFusion):
├─ 时序全局特征: ts_encoded.mean(dim=1) → [batch, 128]
├─ 门控权重: sigmoid(MLP([ts, text])) → [0.1, 0.3]
└─ 输出: ts * (1-w) + text * w

预测头:
├─ pred_head: Linear(128→256) + GELU + Linear(256→16)
├─ temporal_proj: Linear(128→32)  # 时间维度投影
└─ 输出: [batch, 32, 16]  # 32个月预测，16个指标
\`\`\`

### 关键设计

**1. 文本权重限制在 0.1-0.3**

通过实验发现，文本信息对预测的贡献有限，权重过高反而会引入噪声。AdaptiveFusion 层使用 sigmoid 门控，将文本权重限制在 [min_weight=0.1, max_weight=0.3] 范围内：

\`\`\`python
raw_weight = sigmoid(gate([ts_feat, text_feat]))
weight = 0.1 + 0.2 * raw_weight  # 限制在 0.1~0.3
output = ts_feat * (1 - weight) + text_feat * weight
\`\`\`

**2. Z-Score 标准化**

输入数据经过 Z-Score 标准化（减均值除标准差），输出再反标准化回原始尺度。这对数值范围差异大的指标（如 Star 数可能是几万，活跃度是 0-1）非常关键：

\`\`\`python
# 标准化
normalized = (data - mean) / std
# 反标准化
output = prediction * std + mean
\`\`\`

**3. 位置编码可学习**

不同于原始 Transformer 的正弦位置编码，我们使用可学习的位置嵌入，让模型自己学习时序位置的重要性：

\`\`\`python
self.pos_embedding = nn.Parameter(torch.randn(1, 128, 128) * 0.02)
\`\`\`

### 训练结果

| 指标 | 数值 | 说明 |
|-----|-----|------|
| R² | 0.7559 | 决定系数，越接近1越好 |
| MSE | 0.0755 | 均方误差（标准化后） |
| DA | 86.68% | 方向准确率 |
| TA@0.2 | 81.60% | 趋势准确率（20%容忍度） |

### 对比实验

| 模型 | R² | DA |
|-----|-----|-----|
| GitPulse (Transformer+Text) | 0.7559 | 86.68% |
| Transformer-Only | 0.6312 | 84.02% |
| GRU | 0.5847 | 81.45% |
| ARIMA | 0.4231 | 72.13% |

文本信息的加入使 R² 提升了约 0.12，说明项目描述、README 等信息确实对预测有帮助。`
  },
  {
    id: 'chaoss',
    title: 'CHAOSS 评价算法',
    icon: Award,
    content: `## CHAOSS 社区健康评价

CHAOSS (Community Health Analytics for Open Source Software) 是 Linux 基金会下的开源项目健康评估框架。我们将 OpenDigger 的 16 个指标映射到 CHAOSS 的 6 个评价维度。

### 维度与指标映射

| 维度 | 包含指标 | 权重 |
|-----|---------|------|
| Activity (活动度) | OpenRank, 活跃度, 变更请求, PR接受数, 新增Issue | 1.5, 1.5, 1.0, 1.0, 1.0 |
| Contributors (贡献者) | 参与者数, 贡献者, 新增贡献者 | 1.3, 1.3, 1.0 |
| Responsiveness (响应性) | 关闭Issue, Issue评论 | 1.0, 1.0 |
| Quality (代码质量) | PR审查, 代码新增行数, 代码删除行数, 代码变更总行数 | 1.0, 0.8, 0.8, 1.0 |
| Risk (风险) | 总线因子 | 1.0 |
| Community Interest (社区兴趣) | Star数, Fork数 | 1.0, 1.0 |

其中 OpenRank 和活跃度权重设为 1.5，因为它们是综合指标；参与者数和贡献者权重设为 1.3，因为贡献者多样性对项目健康非常重要。

### 评分计算流程

**第一步：月度评分**

对每个月独立计算各维度得分：

1. 提取该月所有可用指标值
2. 评估数据质量（非空率、异常值比例）
3. 百分位归一化：将指标值转换为在历史数据中的百分位排名

\`\`\`python
# 百分位归一化示例
percentile = (当前值在历史中的排名 / 历史数据点数) * 100
normalized_score = percentile  # 直接使用百分位作为 0-100 分数
\`\`\`

4. 对增长型指标（Star数、贡献者数等）的特殊处理：

\`\`\`python
# 使用 max(当前值, 最近3月均值)，避免短期波动导致成长期项目被低估
if metric_type in [GROWTH, INDEX]:
    recent_avg = mean(最近3个月的值)
    final_value = max(当前值, recent_avg)
\`\`\`

5. 应用数据质量折损：

\`\`\`python
# 质量 < 0.7 时开始折损
if quality < 0.7:
    penalty = (0.7 - quality) * 0.3  # 最多折损 21%
    score = score * (1 - penalty)
\`\`\`

6. 加权平均得到维度分数：

\`\`\`python
dimension_score = sum(metric_score * metric_weight) / sum(metric_weight)
dimension_score = max(30, dimension_score)  # 软下限 30 分
\`\`\`

**第二步：异常值处理**

使用 IQR (四分位距) 方法识别异常值：

\`\`\`python
Q1 = percentile(scores, 25)
Q3 = percentile(scores, 75)
IQR = Q3 - Q1

# 异常值边界
lower = Q1 - 1.5 * IQR
upper = Q3 + 1.5 * IQR

# Activity 维度波动大，使用 2.0 倍 IQR
if dimension == 'Activity':
    lower = Q1 - 2.0 * IQR
    upper = Q3 + 2.0 * IQR
\`\`\`

异常值不直接删除，而是降权到 0.3：

\`\`\`python
for score in monthly_scores:
    if lower <= score <= upper:
        weight = 1.0  # 正常值
    else:
        weight = 0.3  # 异常值降权
\`\`\`

**第三步：最终评分**

取最近 12 个月的加权平均：

\`\`\`python
final_score = sum(score * weight) / sum(weight)
overall_score = mean(各维度 final_score)
\`\`\`

### 评级标准

| 等级 | 分数范围 | 含义 |
|-----|---------|------|
| 优秀 | 80-100 | 社区活跃，各维度均衡发展 |
| 良好 | 60-79 | 整体健康，个别维度有改进空间 |
| 一般 | 40-59 | 存在明显短板 |
| 较差 | 20-39 | 多个维度需要重点改进 |
| 很差 | 0-19 | 项目可能处于停滞状态 |

### 改进建议生成

根据各维度得分自动生成建议：

- 分析薄弱维度（得分 < 50）
- 分析月度趋势（最近3个月 vs 前3个月）
- 识别维度组合问题（如活跃度高但响应性低）
- 考虑数据质量因素`
  },
  {
    id: 'data',
    title: '数据采集与处理',
    icon: Database,
    content: `## 数据采集流程

### 数据来源

**1. OpenDigger (X-Lab 开放实验室)**

OpenDigger 提供 GitHub 项目的月度指标数据，我们使用其中 16 个核心指标：

| 类别 | 指标 | API 字段 | 说明 |
|-----|-----|---------|------|
| 综合 | OpenRank | openrank | 基于协作网络的影响力排名 |
| 综合 | 活跃度 | activity | 整体活跃程度 (0-1) |
| 社区 | Star数 | stars | 累计 star 数 |
| 社区 | Fork数 | technical_fork | 累计 fork 数 |
| 社区 | 关注度 | attention | watch 数 |
| 贡献者 | 参与者数 | participants | 月度参与人数 |
| 贡献者 | 新增贡献者 | new_contributors | 新增贡献者 |
| 贡献者 | 贡献者 | contributors | 当月有提交的人数 |
| 贡献者 | 不活跃贡献者 | inactive_contributors | 当月无活动的历史贡献者 |
| 风险 | 总线因子 | bus_factor | 关键人员依赖度 |
| Issue | 新增Issue | issues_new | 新建 issue 数 |
| Issue | 关闭Issue | issues_closed | 关闭 issue 数 |
| Issue | Issue评论 | issue_comments | 评论数 |
| PR | 变更请求 | change_requests | 新建 PR 数 |
| PR | PR接受数 | change_requests_accepted | 合并 PR 数 |
| PR | PR审查 | change_requests_reviews | 审查数 |

**2. GitHub API**

补充文本信息用于 AI 分析和 GitPulse 文本编码：

- 仓库基本信息（描述、语言、License、Topics）
- README.md（中英文）
- Issue 列表（标题、正文、标签、状态）
- PR 列表
- 重要文档（CONTRIBUTING.md、CHANGELOG.md 等）

### 数据处理

**1. 时序对齐**

不同来源的数据按月份对齐，格式为 YYYY-MM：

\`\`\`json
{
  "2024-01": {
    "OpenRank": 4.76,
    "活跃度": 0.82,
    "Star数": 15234,
    ...
  },
  "2024-02": { ... }
}
\`\`\`

**2. 缺失值处理**

- 对于某月缺失的指标，不用 0 填充，直接跳过
- 评分时根据可用指标数计算数据质量
- 如果有效指标少于 30%，该月不参与评分

**3. 数据存储结构**

\`\`\`
DataProcessor/data/
└── owner_repo/
    └── monthly_data_20240107_123456/
        ├── raw_monthly_data.json      # 原始月度数据
        ├── timeseries_for_model/      # 给 GitPulse 的时序数据
        │   ├── 2024-01.json
        │   ├── 2024-02.json
        │   └── ...
        ├── text_for_maxkb/            # 给 MaxKB 的文本数据
        │   ├── README.md
        │   └── docs/
        └── project_summary.json       # 项目摘要
\`\`\`

### 爬取流程

用户点击"爬取数据"后的执行步骤：

1. **获取 OpenDigger 指标** (0-20%)
   - 调用 OpenDigger API 获取月度指标
   - 同时获取仓库基本信息和标签
   - 指标数据立即加载到内存，前端可以开始展示

2. **爬取描述文本** (20-40%)
   - 获取 README（支持中英文）
   - 获取重要文档文件
   - 上传到 MaxKB 知识库

3. **爬取时序文本** (40-70%)
   - 获取最近 N 个月的 Issue/PR
   - 按月分类整理
   - 提取热点 Issue 和关键词

4. **时序对齐与保存** (70-90%)
   - 合并时序指标和时序文本
   - 保存为标准格式
   - 生成项目摘要

5. **加载到服务** (90-100%)
   - 重新加载 DataService
   - 更新缓存`
  },
  {
    id: 'ai',
    title: 'AI 分析功能',
    icon: Brain,
    content: `## AI 智能分析

### 技术架构

\`\`\`
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   前端请求   │ ──▶ │  Flask API  │ ──▶ │ DeepSeek API│
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │MaxKB 知识库 │
                    │ (项目文档)  │
                    └─────────────┘
\`\`\`

### Issue 智能分析

**功能**：对项目 Issue 进行分类统计和问题摘要

**实现**：

1. 从 raw_monthly_data.json 提取 Issue 列表
2. 基于标签和关键词进行分类：
   - Bug：包含 bug、error、fix、crash 等
   - Feature：包含 feature、enhancement、request 等
   - Question：包含 question、help、how to 等
   - Other：其他

3. 调用 DeepSeek API 生成问题摘要：
\`\`\`python
prompt = f"""分析以下 GitHub 项目的 Issue：
项目: {repo_name}
Issue 列表: {issues_text}

请总结：
1. 主要问题类型
2. 高频问题及解决方案
3. 社区关注的热点
"""
\`\`\`

### 预测归因解释

**功能**：解释 GitPulse 预测结果的原因

**实现**：

1. 分析历史数据趋势（上升/下降/稳定）
2. 识别关键转折点
3. 结合 Issue/PR 事件进行归因
4. 生成自然语言解释

\`\`\`python
def generate_explanation(metric_name, historical_data, forecast_data, repo_context):
    # 趋势分析
    recent_trend = analyze_trend(historical_data[-6:])
    
    # 转折点检测
    change_points = detect_change_points(historical_data)
    
    # 生成 prompt
    prompt = f"""
    指标: {metric_name}
    历史趋势: {recent_trend}
    关键转折点: {change_points}
    项目背景: {repo_context}
    
    请解释预测结果的依据。
    """
    return call_deepseek(prompt)
\`\`\`

### MaxKB 知识库集成

**功能**：基于项目文档的问答

**流程**：

1. 爬取项目 README、文档、重要 Markdown 文件
2. 上传到 MaxKB，自动向量化
3. 用户提问时，MaxKB 检索相关文档
4. 结合检索结果生成回答

\`\`\`python
# 上传文档
def upload_to_maxkb(project_name, documents):
    for doc in documents:
        maxkb_client.upload_document(
            dataset_id=project_name,
            content=doc['content'],
            metadata={'type': doc['type']}
        )

# 问答
def answer_question(question, project_name):
    # 检索相关文档
    relevant_docs = maxkb_client.search(project_name, question)
    
    # 生成回答
    prompt = f"根据以下文档回答问题：\\n{relevant_docs}\\n问题：{question}"
    return call_deepseek(prompt)
\`\`\`

### 场景模拟

**功能**：在假设条件下预测项目走势

**支持的场景参数**：

| 参数 | 说明 | 范围 |
|-----|------|------|
| contributor_growth | 贡献者增长率调整 | -50% ~ +100% |
| activity_boost | 活跃度提升 | 0 ~ 2x |
| issue_response | Issue 响应改善 | 0 ~ 2x |

**实现**：

1. 执行基线预测
2. 根据场景参数调整历史数据
3. 重新预测
4. 对比基线和场景预测结果`
  },
  {
    id: 'visualization',
    title: '可视化设计',
    icon: TrendingUp,
    content: `## 可视化组件

### 分组时序图 (GroupedTimeSeriesChart)

**功能**：按类别展示多个指标的历史趋势

**设计要点**：

1. 指标分组：综合指标、社区兴趣、贡献者、Issue、PR
2. 每组独立 Y 轴，避免量级差异导致小指标被压扁
3. 支持 hover 显示详细数值
4. 支持点击切换指标显示/隐藏

\`\`\`typescript
// 数据格式
{
  "综合指标": {
    "OpenRank": {"2024-01": 4.76, "2024-02": 4.82, ...},
    "活跃度": {"2024-01": 0.82, "2024-02": 0.79, ...}
  },
  "社区兴趣": { ... }
}
\`\`\`

### 预测图表 (ForecastChart)

**功能**：展示历史数据 + 预测数据

**设计要点**：

1. 历史数据实线，预测数据虚线
2. 分界线标注"预测开始"
3. 置信区间半透明填充
4. 显示趋势方向和变化率

### CHAOSS 雷达图

**功能**：6 维度健康度可视化

**设计要点**：

1. 六边形雷达图
2. 各维度得分映射到 0-100 刻度
3. 颜色编码：绿色(优秀) → 红色(很差)
4. hover 显示具体分数和等级

### Issue 分类堆叠图

**功能**：展示 Issue 按类型的月度分布

**设计要点**：

1. 堆叠柱状图
2. 四种分类：Bug、Feature、Question、Other
3. 颜色区分：红色(Bug)、蓝色(Feature)、黄色(Question)、灰色(Other)
4. 点击柱状图显示该月详情

### 进度指示器 (ProgressIndicator)

**功能**：爬取数据时的进度展示

**设计要点**：

1. 与后端 SSE 推送对齐
2. 5 个步骤：获取指标 → 爬取文本 → 时序文本 → 对齐处理 → 加载完成
3. 根据 progress 百分比自动定位当前步骤
4. 完成的步骤显示绿色勾选`
  },
  {
    id: 'api',
    title: 'API 文档',
    icon: Code,
    content: `## 后端 API 接口

### 项目数据

**获取项目列表**
\`\`\`
GET /api/projects
返回: { projects: [...], default: "X-lab2017_open-digger" }
\`\`\`

**检查项目是否存在**
\`\`\`
GET /api/check_project?owner=pytorch&repo=pytorch
返回: { exists: true, projectName: "pytorch_pytorch", hasText: true }
\`\`\`

**获取分组时序数据**
\`\`\`
GET /api/timeseries/grouped/{owner}_{repo}
返回: {
  "综合指标": { "OpenRank": { "raw": {"2024-01": 4.76, ...} } },
  ...
}
\`\`\`

### GitPulse 预测

**获取预测数据**
\`\`\`
GET /api/forecast/{owner}_{repo}?months=12
返回: {
  available: true,
  predictions: {
    "Star数": { forecast: {...}, confidence: 0.75, trend: "up" },
    ...
  },
  model_info: { R2: 0.7559, MSE: 0.0755, DA: 0.8668 }
}
\`\`\`

**单指标预测**
\`\`\`
POST /api/predict/{owner}_{repo}
Body: { metric_name: "Star数", forecast_months: 6 }
返回: { forecast: {...}, confidence: 0.75, reasoning: "..." }
\`\`\`

**多指标联动预测**
\`\`\`
POST /api/predict/{owner}_{repo}/multi-metric
Body: { metric_names: ["Star数", "Fork数"], forecast_months: 6 }
返回: { results: { "Star数": {...}, "Fork数": {...} } }
\`\`\`

**预测 + 归因解释**
\`\`\`
POST /api/predict/{owner}_{repo}/explain
Body: { metric_name: "Star数", forecast_months: 6 }
返回: { prediction: {...}, explanation: {...} }
\`\`\`

**场景模拟**
\`\`\`
POST /api/predict/{owner}_{repo}/scenario
Body: {
  metric_name: "Star数",
  forecast_months: 6,
  scenario_params: { contributor_growth: 0.2 }
}
返回: { baseline: {...}, scenario: {...} }
\`\`\`

### CHAOSS 评价

**获取 CHAOSS 评分**
\`\`\`
GET /api/chaoss/{owner}_{repo}
返回: {
  final_scores: {
    overall_score: 72.5,
    overall_level: "良好",
    dimensions: {
      "Activity": { score: 78.3, level: "良好", monthly_count: 12 },
      ...
    }
  },
  monthly_scores: [...],
  report: { summary: "...", recommendations: [...] }
}
\`\`\`

### AI 分析

**Issue 智能分析**
\`\`\`
GET /api/issues/analyze/{owner}_{repo}
返回: {
  summary: "...",
  stats: { bug: 23, feature: 45, question: 12 },
  ai_enabled: true
}
\`\`\`

**AI 问答**
\`\`\`
POST /api/qa
Body: { question: "这个项目是做什么的？", project: "pytorch_pytorch" }
返回: { answer: "...", sources: [...] }
\`\`\`

### 数据爬取

**爬取仓库数据 (SSE)**
\`\`\`
GET /api/crawl?owner=pytorch&repo=pytorch&max_per_month=50

SSE 事件流:
data: {"type": "progress", "step": 1, "progress": 10, "message": "..."}
data: {"type": "metrics_ready", "projectName": "pytorch_pytorch"}
data: {"type": "complete", "outputDir": "..."}
\`\`\`

**重新加载数据**
\`\`\`
POST /api/reload
返回: { status: "ok", repos: [...] }
\`\`\``
  }
]

export default function DocumentationPage({ isOpen, onClose }: DocumentationPageProps) {
  const [activeSection, setActiveSection] = useState('overview')
  const currentSection = docSections.find(s => s.id === activeSection) || docSections[0]

  const renderContent = (content: string) => {
    const lines = content.trim().split('\n')
    const elements: React.ReactNode[] = []
    let inTable = false
    let tableRows: string[][] = []
    let tableHeaders: string[] = []
    let inCodeBlock = false
    let codeBlockContent: string[] = []
    let codeBlockLang = ''

    const flushTable = (idx: number) => {
      if (tableHeaders.length > 0) {
        elements.push(
          <div key={`table-${idx}`} className="my-4 overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b border-cyber-primary/30 bg-cyber-surface/30">
                  {tableHeaders.map((h, i) => (
                    <th key={i} className="px-3 py-2 text-left text-cyber-primary font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tableRows.map((row, i) => (
                  <tr key={i} className="border-b border-cyber-border/30 hover:bg-cyber-surface/20">
                    {row.map((cell, j) => (
                      <td key={j} className="px-3 py-2 text-cyber-text/80 font-mono text-xs">{cell}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      }
      inTable = false
      tableHeaders = []
      tableRows = []
    }

    const flushCodeBlock = (idx: number) => {
      if (codeBlockContent.length > 0) {
        elements.push(
          <div key={`code-${idx}`} className="my-4 rounded-lg bg-[#1a1a2e] border border-cyber-border overflow-hidden">
            {codeBlockLang && (
              <div className="px-3 py-1 bg-cyber-surface/50 border-b border-cyber-border text-xs text-cyber-muted font-mono">
                {codeBlockLang}
              </div>
            )}
            <pre className="p-4 overflow-x-auto text-sm leading-relaxed">
              <code className="text-cyber-text/90 font-mono">{codeBlockContent.join('\n')}</code>
            </pre>
          </div>
        )
      }
      inCodeBlock = false
      codeBlockContent = []
      codeBlockLang = ''
    }

    lines.forEach((line, idx) => {
      // 处理代码块
      if (line.startsWith('```')) {
        if (inCodeBlock) {
          flushCodeBlock(idx)
        } else {
          if (inTable) flushTable(idx)
          inCodeBlock = true
          codeBlockLang = line.slice(3).trim()
        }
        return
      }

      if (inCodeBlock) {
        codeBlockContent.push(line)
        return
      }

      // 处理表格
      if (line.startsWith('|') && line.endsWith('|')) {
        const cells = line.split('|').filter(c => c.trim() !== '')
        if (cells.every(c => c.trim().match(/^[-:]+$/))) {
          inTable = true
          return
        }
        if (!inTable) {
          tableHeaders = cells.map(c => c.trim())
          tableRows = []
        } else {
          tableRows.push(cells.map(c => c.trim()))
        }
        return
      } else if (inTable) {
        flushTable(idx)
      }

      // 标题
      if (line.startsWith('## ')) {
        elements.push(<h2 key={idx} className="text-xl font-bold text-cyber-primary mt-6 mb-3 pb-2 border-b border-cyber-border/50">{line.slice(3)}</h2>)
      } else if (line.startsWith('### ')) {
        elements.push(<h3 key={idx} className="text-base font-bold text-cyber-secondary mt-5 mb-2">{line.slice(4)}</h3>)
      } else if (line.startsWith('#### ')) {
        elements.push(<h4 key={idx} className="text-sm font-semibold text-cyber-text mt-3 mb-1">{line.slice(5)}</h4>)
      } else if (line.startsWith('**') && line.endsWith('**')) {
        // 独立的粗体行作为小标题
        elements.push(<div key={idx} className="font-semibold text-cyber-text mt-3 mb-1">{line.slice(2, -2)}</div>)
      } else if (line.match(/^\*\*\d+\.\s/)) {
        // 编号粗体项目
        const match = line.match(/^\*\*(\d+)\.\s(.+?)\*\*(.*)$/)
        if (match) {
          elements.push(
            <div key={idx} className="flex gap-2 my-2 ml-2">
              <span className="text-cyber-primary font-bold">{match[1]}.</span>
              <span><strong className="text-cyber-text">{match[2]}</strong>{match[3]}</span>
            </div>
          )
        }
      } else if (line.startsWith('- ')) {
        elements.push(
          <div key={idx} className="flex gap-2 my-1 ml-2">
            <span className="text-cyber-primary">•</span>
            <span className="text-cyber-text/85">{renderInline(line.slice(2))}</span>
          </div>
        )
      } else if (line.match(/^\d+\.\s/)) {
        const match = line.match(/^(\d+)\.\s(.*)$/)
        if (match) {
          elements.push(
            <div key={idx} className="flex gap-2 my-1 ml-2">
              <span className="text-cyber-secondary font-medium min-w-[1.2rem]">{match[1]}.</span>
              <span className="text-cyber-text/85">{renderInline(match[2])}</span>
            </div>
          )
        }
      } else if (line.trim()) {
        elements.push(<p key={idx} className="text-cyber-text/85 my-2 leading-relaxed">{renderInline(line)}</p>)
      }
    })

    if (inTable) flushTable(lines.length)
    if (inCodeBlock) flushCodeBlock(lines.length)

    return elements
  }

  const renderInline = (text: string): React.ReactNode => {
    // 处理行内代码和粗体
    const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/)
    return parts.map((part, i) => {
      if (part.startsWith('`') && part.endsWith('`')) {
        return <code key={i} className="px-1 py-0.5 bg-cyber-surface rounded text-cyber-primary text-xs font-mono">{part.slice(1, -1)}</code>
      }
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={i} className="text-cyber-text font-semibold">{part.slice(2, -2)}</strong>
      }
      return <span key={i}>{part}</span>
    })
  }

  if (!isOpen) return null

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 bg-cyber-bg/95 backdrop-blur-xl"
      >
        <div className="h-full flex">
          <aside className="w-64 bg-cyber-card/50 border-r border-cyber-border overflow-y-auto">
            <div className="p-4 border-b border-cyber-border flex items-center gap-2">
              <Book className="w-5 h-5 text-cyber-primary" />
              <span className="font-bold text-cyber-text">技术文档</span>
            </div>
            <nav className="p-2">
              {docSections.map((section) => {
                const Icon = section.icon
                const isActive = activeSection === section.id
                return (
                  <button
                    key={section.id}
                    onClick={() => setActiveSection(section.id)}
                    className={`w-full flex items-center gap-2 px-3 py-2 rounded mb-1 text-left text-sm transition-colors
                      ${isActive ? 'bg-cyber-primary/20 text-cyber-primary' : 'text-cyber-muted hover:bg-cyber-card hover:text-cyber-text'}`}
                  >
                    <Icon className="w-4 h-4" />
                    {section.title}
                    {isActive && <ChevronRight className="w-4 h-4 ml-auto" />}
                  </button>
                )
              })}
            </nav>
          </aside>

          <main className="flex-1 overflow-y-auto">
            <div className="sticky top-0 bg-cyber-bg/90 backdrop-blur border-b border-cyber-border flex items-center justify-between px-6 py-3 z-10">
              <h1 className="text-lg font-bold text-cyber-text flex items-center gap-2">
                {React.createElement(currentSection.icon, { className: "w-5 h-5 text-cyber-primary" })}
                {currentSection.title}
              </h1>
              <button onClick={onClose} className="p-2 text-cyber-muted hover:text-cyber-text rounded hover:bg-cyber-surface">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="max-w-4xl mx-auto p-6">
              <motion.div
                key={activeSection}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2 }}
              >
                {renderContent(currentSection.content)}
              </motion.div>
            </div>
          </main>
        </div>
      </motion.div>
    </AnimatePresence>
  )
}
