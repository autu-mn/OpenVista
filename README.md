# OpenVista

GitHub 仓库生态画像分析平台

## 项目架构

```
OpenVista/
├── backend/                    # 后端服务 (Python Flask)
│   ├── Agent/                  # AI/MaxKB 层
│   │   ├── maxkb_client.py     # MaxKB AI 客户端
│   │   ├── deepseek_client.py  # DeepSeek API 客户端（备用）
│   │   ├── qa_agent.py         # 问答 Agent
│   │   └── prediction_explainer.py  # 预测解释生成器
│   │
│   ├── DataProcessor/          # 数据采集层
│   │   ├── crawl_monthly_data.py      # 主爬虫入口
│   │   ├── monthly_crawler.py         # 月度数据爬虫
│   │   ├── github_text_crawler.py     # GitHub 文本爬虫
│   │   ├── monthly_data_processor.py  # 数据处理器
│   │   ├── maxkb_uploader.py          # MaxKB 上传
│   │   └── data/                      # 爬取的数据
│   │
│   ├── GitPulse/               # 时序分析层（GitPulse 预测模块）
│   │   └── predictor.py        # GitPulse 预测适配器
│   │
│   ├── app.py                  # Flask API 入口
│   └── data_service.py         # 数据服务层
│
├── GitPulse/                   # GitPulse 核心模型
│   ├── model/                  # 模型定义
│   │   └── multimodal_ts_v4_1.py  # CondGRU+Text 模型
│   ├── predict/                # 预测脚本
│   │   ├── models/best_model.pt   # 训练好的模型权重
│   │   └── predict_single_repo.py
│   ├── training/               # 训练脚本
│   └── paper/                  # 论文相关
│
└── frontend/                   # 前端 (React + TypeScript + Tailwind)
    └── src/
        ├── App.tsx             # 主应用
        └── components/         # UI 组件
            ├── MultiMetricPrediction.tsx  # 多指标预测图表
            ├── PredictionExplanation.tsx  # AI 归因解释
            ├── ScenarioSimulator.tsx      # 场景模拟器
            └── ...
```

## 功能模块

### 1. 数据采集层 (DataProcessor/)
- 从 GitHub API 爬取仓库数据（Issues、PRs、Commits、Releases）
- 从 OpenDigger 获取 16 个指标（OpenRank、活跃度、Star数等）
- 按月份组织数据，生成时序数据
- Issue 分类统计（功能需求/Bug修复/社区咨询）
- 项目总体 AI 摘要

### 2. AI/MaxKB 层 (Agent/)
- **MaxKB 知识库问答**：使用 MAXKB_AI_API 进行智能问答
- 生成项目摘要（入门介绍）
- DeepSeek 大模型问答（备用方案）
- 预测归因解释生成

### 3. 时序分析层 (GitPulse/)
- **GitPulse 多模态时序预测模型**（条件 GRU + 文本融合）
- 同时预测 16 个指标的未来走势（最多 32 个月）
- 结合项目描述、Issue 统计等文本信息
- 模型性能：MSE=0.0886, R²=0.70, DA=67.28%

支持的 16 个指标：
- OpenRank、活跃度、Star数、Fork数、关注度、参与者数
- 新增贡献者、贡献者、不活跃贡献者、总线因子
- 新增Issue、关闭Issue、Issue评论
- 变更请求、PR接受数、PR审查

### 4. 前端展示层 (frontend/)
- **首页**：输入仓库名，触发爬取
- **时序分析**：展示 OpenDigger 指标的时序图表
- **单指标预测**：预测单个指标的未来趋势
- **多指标预测**：同时预测多个指标，双轴对比展示
- **场景模拟**：调整假设参数（如新增贡献者数量），查看预测变化
- **AI 归因解释**：LLM 生成预测理由、关键事件、风险提示
- **Issue 分析**：按月展示 Issue 关键词和分类

## 环境配置

在项目根目录创建 `.env` 文件：

```env
# GitHub API Token（必需）
GITHUB_TOKEN=your_github_token

# MaxKB AI API（推荐，用于智能问答）
MAXKB_AI_API=http://your-maxkb-server/api/application/{app_id}/chat/completions
MAXKB_API_KEY=your_maxkb_api_key  # 如果需要认证

# DeepSeek API（备用）
DEEPSEEK_API_KEY=your_deepseek_api_key
```

## 运行指南

### 1. 后端启动

```bash
cd backend
pip install -r requirements.txt
python app.py
```

后端将运行在 `http://localhost:5000`

日志文件位于 `backend/logs/openvista.log`

### 2. 前端启动

```bash
cd frontend
npm install
npm run dev
```

前端将运行在 `http://localhost:3000`

### 3. 访问应用

打开浏览器访问 `http://localhost:3000`

## 使用流程

1. 在首页输入仓库所有者和仓库名（如 `X-lab2017/open-digger`）
2. 点击"开始分析"，等待爬取完成
3. 自动跳转到数据分析页面
4. 查看时序图表、Issue 分析等数据
5. 在"数据分析"标签页选择预测模式：
   - **单指标预测**：选择一个指标进行详细预测
   - **多指标预测**：同时预测多个指标进行对比
   - **场景模拟**：调整假设参数查看影响

## 示例仓库

我们以 **X-lab2017/open-digger** 作为示例仓库，该仓库包含：
- 65 个月的历史数据（2020-08 至 2025-12）
- 16 个 OpenDigger 指标
- 完整的 Issue 分类和文本数据

详细使用示例请参考：`GitPulse/EXAMPLE_X-lab2017_open-digger.md`

## 项目命名说明

| 名称 | 层级 | 说明 |
|------|------|------|
| **OpenVista** | 平台级 | 整个 GitHub 仓库生态画像分析平台 |
| **GitPulse** | 模型级 | 核心多模态时序预测模型（CondGRU+Text） |

## 技术栈

- **后端**：Python, Flask, PyTorch, Transformers (DistilBERT)
- **前端**：React, TypeScript, Tailwind CSS, Recharts, Framer Motion
- **AI**：MaxKB 知识库, DeepSeek API（备用）
- **数据源**：GitHub API, OpenDigger

## License

MIT License


- **后端**：Python, Flask, PyTorch, Transformers (DistilBERT)
- **前端**：React, TypeScript, Tailwind CSS, Recharts, Framer Motion
- **AI**：MaxKB 知识库, DeepSeek API（备用）
- **数据源**：GitHub API, OpenDigger

## License

MIT License
