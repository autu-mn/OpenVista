# OpenVista 后端 Dockerfile
# 支持从 Hugging Face 加载 GitPulse 模型

FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

# 先复制 requirements 文件（利用 Docker 缓存）
COPY backend/requirements.txt ./

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 安装 Hugging Face Hub（用于从 Hugging Face 下载模型）
RUN pip install --no-cache-dir huggingface_hub transformers

# 安装 PyTorch（CPU 版本，如果需要 GPU 请使用 pytorch/pytorch 基础镜像）
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# 复制后端代码
COPY backend/ .

# 创建必要的目录
RUN mkdir -p logs data DataProcessor/data

# 注意：GitPulse 核心代码（predict/ 目录）需要通过 volume 挂载
# 在 docker-compose.yml 中配置：- ./GitPulse:/app/GitPulse:ro
# 如果 GitPulse 目录不存在，predictor.py 会尝试从 Hugging Face 下载模型
# 但 RepoPredictor 类仍然需要 GitPulse 的预测代码（predict/predict_single_repo.py）

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# 暴露端口
EXPOSE 5000

# 启动命令
CMD ["python", "app.py"]

