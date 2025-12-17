# DataPulse

GitHub 仓库生态画像分析平台

## 项目架构

```
DataPulse/
├── backend/                    # 后端服务 (Python Flask)
│   ├── Agent/                  # AI/MaxKB 层
│   │   ├── deepseek_client.py  # DeepSeek API 客户端
│   │   └── qa_agent.py         # 问答 Agent
│   │
│   ├── DataProcessor/          # 数据采集层
│   │   ├── crawl_monthly_data.py      # 主爬虫入口
│   │   ├── monthly_crawler.py         # 月度数据爬虫
│   │   ├── github_text_crawler.py     # GitHub 文本爬虫
│   │   ├── monthly_data_processor.py  # 数据处理器
│   │   ├── maxkb_uploader.py          # MaxKB 上传
│   │   └── data/                      # 爬取的数据
│   │
│   ├── LLM2TSA/                # 时序分析层
│   │   ├── predictor.py        # LLM 辅助时序预测
│   │   └── enhancer.py         # 时序增强器
│   │
│   ├── app.py                  # Flask API 入口
│   └── data_service.py         # 数据服务层
│
└── frontend/                   # 前端 (React + TypeScript)
    └── src/
        ├── App.tsx             # 主应用
        └── components/         # UI 组件
```

## 功能模块

### 1. 数据采集层 (DataProcessor/)
- 从 GitHub API 爬取仓库数据（Issues、PRs、Commits、Releases）
- 从 OpenDigger 获取 19 个指标（OpenRank、活跃度、Star数等）
- 按月份组织数据，生成时序数据
- Issue 分类统计（功能需求/Bug修复/社区咨询）
- 项目总体 AI 摘要

### 2. AI/MaxKB 层 (Agent/)
- 生成项目摘要（入门介绍）
- DeepSeek 大模型问答（项目使用方法、开发流程）
- MaxKB 知识库集成（上传文档供 RAG 检索）

### 3. 时序分析层 (LLM2TSA/)
- 双塔模型（时序特征 + 文本语义联合建模）
- LLM 辅助时序预测
- 指标趋势预测

### 4. 前端展示层 (frontend/)
- 首页：输入仓库名，触发爬取
- 时序分析：展示 OpenDigger 指标的时序图表
- Issue 分析：按月展示 Issue 关键词和分类

## 运行指南

### 1. 后端启动

```bash
cd backend
pip install -r requirements.txt
python app.py
```

### 2. 前端启动

```bash
cd frontend
npm install
npm run dev
```

### 3. 访问应用

打开浏览器访问 `http://localhost:3000`

## 配置说明

在 `backend/DataProcessor/` 目录下创建 `.env` 文件：

```env
GITHUB_TOKEN=your_github_token
DEEPSEEK_API_KEY=your_deepseek_api_key
```

## 使用流程

1. 在首页输入仓库所有者和仓库名（如 `pytorch/pytorch`）
2. 点击"开始分析"，等待爬取完成
3. 自动跳转到数据分析页面
4. 查看时序图表、Issue 分析等数据
