# OpenVista 使用指南

本指南面向零基础用户，从零开始配置和运行 OpenVista 项目。

---

## 目录

1. [环境要求](#一环境要求)
2. [安装步骤](#二安装步骤)
3. [配置 API Token](#三配置-api-token)
4. [安装 GitPulse 模型](#四安装-gitpulse-模型可选但推荐)
5. [配置 MaxKB 知识库](#五配置-maxkb-知识库可选)
6. [启动项目](#六启动项目)
7. [常见问题](#七常见问题-qa)

---

## 一、环境要求

| 软件 | 版本要求 | 用途 | 下载地址 |
|-----|---------|------|---------|
| Python | 3.8 - 3.12 | 后端运行 | https://www.python.org/downloads/ |
| Node.js | 16+ | 前端运行 | https://nodejs.org/ |
| Git | 任意版本 | 代码管理 | https://git-scm.com/ |
| Docker Desktop | 任意版本 | MaxKB 知识库（可选） | https://www.docker.com/products/docker-desktop/ |

### 检查环境

打开终端（Windows 用 PowerShell），运行：

```bash
python --version    # 应显示 Python 3.8+
node --version      # 应显示 v16+
npm --version       # 应显示 8+
git --version       # 应显示 git version x.x.x
```

---

## 二、安装步骤

### 2.1 克隆或下载项目

```bash
# 如果是压缩包，解压到任意目录
# 如果是 Git，克隆仓库：
git clone <仓库地址>
cd DataPulse
```

### 2.2 安装后端依赖

```bash
# 进入后端目录
cd backend

# 创建虚拟环境（推荐）
python -m venv venv

# 激活虚拟环境
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# Windows CMD:
.\venv\Scripts\activate.bat
# Linux/Mac:
source venv/bin/activate

# 安装依赖
pip install flask flask-cors requests python-dotenv jieba pandas numpy

# 如果需要 Prophet（时序分析，可选）：
pip install prophet
```

### 2.3 安装前端依赖

```bash
# 回到项目根目录
cd ..
cd frontend

# 安装依赖
npm install
```

---

## 三、配置 API Token

### 3.1 创建环境变量文件

在 `backend` 目录下创建 `.env` 文件：

```bash
cd backend
# Windows:
echo. > .env
# Linux/Mac:
touch .env
```

### 3.2 获取 GitHub Token（必须）

**为什么需要？** GitHub API 有速率限制，未认证请求每小时只能 60 次，配置 Token 后可达 5000 次。

**获取步骤：**

1. 登录 GitHub，点击右上角头像 → Settings
2. 左侧菜单最下方 → Developer settings
3. Personal access tokens → Tokens (classic) → Generate new token (classic)
4. 勾选权限：`repo`（读取公开仓库）、`read:user`
5. 点击 Generate token，复制生成的 token

**配置到 .env 文件：**

```env
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 3.3 获取 DeepSeek API Key（可选，用于 AI 分析）

**为什么需要？** AI 智能摘要、Issue 分析、预测归因解释等功能需要。

**获取步骤：**

1. 访问 https://platform.deepseek.com/
2. 注册/登录账号
3. 进入 API Keys 页面，创建新的 API Key
4. 复制 API Key

**配置到 .env 文件：**

```env
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 3.4 完整的 .env 文件示例

```env
# GitHub Token（必须）
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# DeepSeek API（可选，用于 AI 分析）
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# MaxKB 配置（可选，用于知识库问答）
MAXKB_URL=http://localhost:8080
MAXKB_USERNAME=admin
MAXKB_PASSWORD=MaxKB@123456
MAXKB_KNOWLEDGE_ID=你的知识库ID
MAXKB_API_KEY=你的API密钥
```

---

## 四、安装 GitPulse 模型（可选但推荐）

GitPulse 是我们训练的时序预测模型，用于预测项目未来趋势。

### 4.1 安装 PyTorch

**CPU 版本（通用）：**

```bash
pip install torch torchvision torchaudio
```

**GPU 版本（NVIDIA 显卡，更快）：**

访问 https://pytorch.org/get-started/locally/ 选择你的配置，获取安装命令。

例如 CUDA 11.8：
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### 4.2 安装 Transformers

```bash
pip install transformers
```

### 4.3 验证安装

```bash
python -c "import torch; print('PyTorch:', torch.__version__)"
python -c "from transformers import DistilBertModel; print('Transformers OK')"
```

### 4.4 模型权重文件

模型权重文件 `gitpulse_weights.pt` 已包含在 `backend/GitPulse/` 目录中，无需额外下载。

---

## 五、配置 MaxKB 知识库（可选）

MaxKB 是用于项目文档问答的知识库系统。如果不需要 AI 问答功能，可以跳过此步骤。

### 5.1 安装 Docker Desktop

1. 下载 Docker Desktop: https://www.docker.com/products/docker-desktop/
2. 安装并启动
3. 确保 Docker 正在运行（系统托盘有图标）

### 5.2 启动 MaxKB 容器

**方式一：使用项目提供的配置**

```bash
# 在项目根目录
docker compose -f docker-compose.maxkb.yml up -d
```

**方式二：直接运行**

```bash
docker run -d \
  --name openvista-maxkb \
  -p 8080:8080 \
  -v maxkb_data:/opt/maxkb/model \
  -v maxkb_postgres:/var/lib/postgresql/data \
  1panel/maxkb:latest
```

### 5.3 初始化 MaxKB

1. 等待 1-2 分钟，容器启动完成
2. 访问 http://localhost:8080
3. 使用默认账号登录：
   - 用户名：`admin`
   - 密码：`MaxKB@123456`

### 5.4 配置 MaxKB

1. **创建知识库**
   - 点击"知识库" → "创建知识库"
   - 填写名称（如 "OpenVista"）
   - 记下知识库 ID（URL 中的 ID）

2. **配置模型**
   - 点击"模型管理" → "添加模型"
   - 选择 "DeepSeek"
   - 填入你的 DeepSeek API Key
   - 模型选择 `deepseek-chat`

3. **获取 API 密钥**
   - 点击"API 密钥" → "创建密钥"
   - 复制生成的密钥

4. **更新 .env 文件**

```env
MAXKB_URL=http://localhost:8080
MAXKB_USERNAME=admin
MAXKB_PASSWORD=MaxKB@123456
MAXKB_KNOWLEDGE_ID=你的知识库ID
MAXKB_API_KEY=你的API密钥
```

### 5.5 导入已有数据（可选）

如果有备份数据，可以恢复：

**Windows:**
```powershell
.\maxkb-export\install.ps1
```

**Linux/Mac:**
```bash
chmod +x maxkb-export/install.sh
./maxkb-export/install.sh
```

---

## 六、启动项目

### 6.1 启动后端

```bash
# 确保在 backend 目录
cd backend

# 激活虚拟环境（如果创建了）
# Windows:
.\venv\Scripts\Activate.ps1
# Linux/Mac:
source venv/bin/activate

# 启动后端服务
python app.py
```

看到以下输出表示启动成功：

```
==================================================
  ___                   __     ___     _        
 / _ \ _ __   ___ _ __  \ \   / (_)___| |_ __ _ 
| | | | '_ \ / _ \ '_ \  \ \ / /| / __| __/ _` |
| |_| | |_) |  __/ | | |  \ V / | \__ \ || (_| |
 \___/| .__/ \___|_| |_|   \_/  |_|___/\__\__,_|
      |_|   GitHub 仓库生态画像分析平台          
==================================================

服务地址: http://0.0.0.0:5000
```

### 6.2 启动前端

打开新的终端窗口：

```bash
# 进入前端目录
cd frontend

# 启动开发服务器
npm run dev
```

看到以下输出表示启动成功：

```
  VITE v5.x.x  ready in xxx ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: http://192.168.x.x:5173/
```

### 6.3 访问系统

打开浏览器，访问 http://localhost:5173

---

## 七、常见问题 (Q&A)

### Q1: 后端启动报错 "No module named 'xxx'"

**原因**：依赖未安装完整

**解决**：
```bash
pip install flask flask-cors requests python-dotenv jieba pandas numpy
```

### Q2: GitPulse 显示 "预测服务不可用"

**原因**：PyTorch 或 Transformers 未安装

**解决**：
```bash
pip install torch transformers
```

首次运行会自动下载 DistilBERT 模型（约 250MB），请耐心等待。

### Q3: 爬取数据时报错 "API rate limit exceeded"

**原因**：GitHub Token 未配置或无效

**解决**：
1. 检查 `.env` 文件中的 GITHUB_TOKEN
2. 确保 Token 没有过期
3. 确保 Token 有 `repo` 权限

### Q4: AI 分析功能没有响应

**原因**：DeepSeek API Key 未配置

**解决**：
1. 在 `.env` 文件中添加 `DEEPSEEK_API_KEY`
2. 确保 API Key 有效且有余额

### Q5: MaxKB 访问不了 (localhost:8080)

**原因**：Docker 容器未启动

**解决**：
```bash
# 检查容器状态
docker ps -a

# 启动容器
docker start openvista-maxkb

# 如果没有容器，创建一个
docker compose -f docker-compose.maxkb.yml up -d
```

### Q6: 前端报错 "Network Error" 或 "CORS"

**原因**：后端未启动或端口被占用

**解决**：
1. 确保后端在 5000 端口运行
2. 检查是否有其他程序占用 5000 端口

### Q7: CHAOSS 评价显示 "暂无数据"

**原因**：该项目没有爬取数据

**解决**：
1. 在首页搜索框输入项目名（如 `pytorch/pytorch`）
2. 点击"爬取数据"按钮
3. 等待爬取完成（约 3-5 分钟）

### Q8: 预测结果不准确或波动大

**原因**：历史数据不足

**解决**：
- GitPulse 模型需要至少 12 个月的历史数据才能有效预测
- 数据越多，预测越准确
- 置信度低于 0.6 的预测建议谨慎参考

### Q9: Windows PowerShell 执行脚本报错

**原因**：执行策略限制

**解决**：
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Q10: 如何更新项目数据？

1. 在项目详情页，数据会自动从缓存加载
2. 如需更新，重新执行"爬取数据"
3. 后端重启会自动加载所有已爬取的项目

---

## 附录：功能配置对照表

| 功能 | 需要 GitHub Token | 需要 DeepSeek API | 需要 MaxKB | 需要 GitPulse |
|-----|------------------|------------------|-----------|--------------|
| 查看已有项目数据 | ❌ | ❌ | ❌ | ❌ |
| 爬取新项目 | ✅ | ❌ | ❌ | ❌ |
| 时序数据可视化 | ❌ | ❌ | ❌ | ❌ |
| CHAOSS 健康评价 | ❌ | ❌ | ❌ | ❌ |
| GitPulse 预测 | ❌ | ❌ | ❌ | ✅ |
| AI 智能摘要 | ❌ | ✅ | ❌ | ❌ |
| Issue 智能分析 | ❌ | ✅ | ❌ | ❌ |
| 预测归因解释 | ❌ | ✅ | ❌ | ❌ |
| 知识库问答 | ❌ | ✅ | ✅ | ❌ |

---

## 最小化启动

如果你只想快速体验，以下是最小配置：

```bash
# 1. 安装后端依赖
cd backend
pip install flask flask-cors requests python-dotenv jieba pandas numpy

# 2. 创建 .env 文件（只需 GitHub Token）
echo "GITHUB_TOKEN=你的token" > .env

# 3. 启动后端
python app.py

# 4. 新终端，安装前端依赖
cd frontend
npm install

# 5. 启动前端
npm run dev

# 6. 访问 http://localhost:5173
```

这样就可以使用基础功能：查看数据、爬取项目、CHAOSS 评价。

如需 AI 分析和预测功能，再按上述步骤配置 DeepSeek 和 GitPulse。

