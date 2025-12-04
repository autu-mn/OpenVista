# DataPulse

## 功能特点

- **数据采集**：自动爬取 GitHub 仓库数据（Issues、PRs、Commits 等，但是有缺失值，issue、PR、commit太多了，用处不大）
- **可视化展示**：数据展示（不好看，不完善，有缺失）
- **模型集成**： MaxKB 知识库 + Deepseek 大语言模型 + ALI 分词模型（效果一般，还没接到前端）
- **时序分析**：未完成
- **Issue分析**：未完成
- **波动归因**：未完成
- **可解释性描述**：未完成
- **整体开源生态分析评级**：未完成

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

在 `backend/DataProcessor/` 目录下创建 `.env` 文件，然后填写必需字段
（这个发不了，Github会查得到，他看到了就push不上去了）


## 项目结构

```
DataPulse/
├── backend/                 # 后端服务
│   ├── Agent/              # AI 问答模块
│   ├── DataProcessor/      # 数据处理模块
│   ├── app.py             # Flask 应用入口
│   └── data_service.py    # 数据服务
├── frontend/               # 前端应用
│   └── src/
│       ├── components/    # React 组件
│       └── pages/         # 页面组件
└── README.md
```

## 使用说明

1. 在首页输入仓库所有者和仓库名
2. 点击"开始分析"，等待爬取完成
3. 自动跳转到数据分析页面
4. 查看时序、Issue等数据
