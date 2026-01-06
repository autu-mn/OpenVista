# OpenVista Docker 部署指南

本文档介绍如何使用 Docker 部署 OpenVista 平台，包括从 Hugging Face 加载 GitPulse 预测模型。

## 前置要求

- Docker 20.10+
- Docker Compose 2.0+
- 至少 4GB 可用内存
- 至少 10GB 可用磁盘空间（用于模型缓存）

## 快速开始

### 1. 克隆项目

```bash
git clone <repository-url>
cd OpenVista
```

### 2. 准备 GitPulse 代码

GitPulse 预测代码需要从项目根目录挂载。如果项目根目录没有 `GitPulse` 目录：

**选项 A：克隆 GitPulse 仓库（推荐）**
```bash
# 在项目根目录执行
git clone <gitpulse-repo-url> GitPulse
```

**选项 B：如果 GitPulse 代码在其他位置**
修改 `docker-compose.yml` 中的 volume 挂载路径：
```yaml
volumes:
  - /path/to/GitPulse:/app/GitPulse:ro
```

**选项 C：如果没有 GitPulse 代码**
注释掉 `docker-compose.yml` 中的 GitPulse volume 挂载，但注意：
- 模型权重可以从 Hugging Face 下载
- 但 `predict/predict_single_repo.py` 代码仍然需要，否则预测功能无法使用

### 3. 配置环境变量

创建 `.env` 文件（如果不存在）：

```bash
# Windows
copy .env.example .env

# Linux/Mac
cp .env.example .env
```

编辑 `.env` 文件，填入必要的配置：

```env
# GitHub API Token（必需）
GITHUB_TOKEN=your_github_token_here

# MaxKB AI API（可选）
MAXKB_AI_API=http://localhost:8080/api/application/{app_id}/chat/completions
MAXKB_API_KEY=your_maxkb_api_key

# Hugging Face 模型配置
USE_HUGGINGFACE=true
HUGGINGFACE_MODEL_ID=Osacato/Gitpulse

# Hugging Face Token（如果需要访问私有模型）
# HUGGINGFACE_TOKEN=your_huggingface_token
```

### 4. 启动服务

```bash
docker-compose up -d
```

这将启动三个服务：
- **backend**: Flask 后端服务（端口 5000）
- **frontend**: React 前端服务（端口 3000）
- **maxkb**: MaxKB 知识库服务（端口 8080）

### 5. 查看日志

```bash
# 查看所有服务日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f maxkb
```

### 6. 访问应用

- 前端：http://localhost:3000
- 后端 API：http://localhost:5000
- MaxKB：http://localhost:8080

## GitPulse 模型配置

### GitPulse 代码结构要求

GitPulse 预测功能需要以下代码结构：

```
GitPulse/
├── predict/
│   ├── predict_single_repo.py  # 必需：预测代码类 RepoPredictor
│   └── models/                  # 可选：本地模型文件目录
│       └── best_model.pt       # 模型权重文件（可从 Hugging Face 下载）
└── model/                       # 可选：模型定义代码
    └── multimodal_ts_v4_1.py   # CondGRU+Text 模型定义
```

**重要**：
- `predict/predict_single_repo.py` 是必需的，包含 `RepoPredictor` 类
- 模型权重文件（`.pt`）可以从 Hugging Face 下载，也可以使用本地文件
- 如果项目根目录没有 `GitPulse` 目录，需要：
  1. 克隆 GitPulse 仓库到项目根目录，或
  2. 修改 `docker-compose.yml` 中的 volume 挂载路径指向 GitPulse 代码位置

### 从 Hugging Face 加载模型

默认配置会从 Hugging Face 自动下载模型权重。首次启动时，后端会：

1. 检查 `USE_HUGGINGFACE` 环境变量
2. 如果为 `true`，从 Hugging Face 下载模型权重到缓存目录
3. 模型缓存位置：`~/.cache/huggingface/hub/`（在容器中为 `/root/.cache/huggingface`）
4. 使用挂载的 GitPulse 代码中的 `RepoPredictor` 类加载模型

### 模型下载

模型权重会在首次使用时自动下载。如果下载失败，检查：

1. 网络连接是否正常
2. Hugging Face 服务是否可访问：https://huggingface.co/Osacato/Gitpulse
3. 模型 ID 是否正确（默认：`Osacato/Gitpulse`）
4. 查看后端日志：`docker-compose logs backend`

### 使用本地模型权重

如果不想从 Hugging Face 下载模型权重，可以：

1. 设置 `USE_HUGGINGFACE=false`
2. 将模型文件放在 `GitPulse/predict/models/best_model.pt`
3. 通过 volume 挂载到容器中（已在 `docker-compose.yml` 中配置）

## 服务说明

### Backend 服务

- **端口**: 5000
- **数据目录**: `./backend/DataProcessor/data`（挂载到容器）
- **日志目录**: `./backend/logs`（挂载到容器）
- **模型缓存**: Docker volume `model_cache`

### Frontend 服务

- **端口**: 3000（映射到容器内的 80）
- **构建**: 使用多阶段构建，先构建 React 应用，再使用 Nginx 提供服务

### MaxKB 服务

- **端口**: 8080
- **数据**: 存储在 Docker volume 中
- **数据库**: PostgreSQL（内置）

## 环境变量说明

| 变量名 | 说明 | 必需 | 默认值 |
|--------|------|------|--------|
| `GITHUB_TOKEN` | GitHub API Token | 是 | - |
| `USE_HUGGINGFACE` | 是否从 Hugging Face 加载模型 | 否 | `true` |
| `HUGGINGFACE_MODEL_ID` | Hugging Face 模型 ID | 否 | `Osacato/Gitpulse` |
| `HUGGINGFACE_TOKEN` | Hugging Face Token（私有模型需要） | 否 | - |
| `MAXKB_AI_API` | MaxKB API 地址 | 否 | - |
| `MAXKB_API_KEY` | MaxKB API Key | 否 | - |
| `DEEPSEEK_API_KEY` | DeepSeek API Key（备用） | 否 | - |

## 数据持久化

以下数据会持久化存储：

1. **项目数据**: `./backend/DataProcessor/data`（挂载到主机）
2. **日志文件**: `./backend/logs`（挂载到主机）
3. **模型缓存**: Docker volume `model_cache`
4. **MaxKB 数据**: Docker volumes `maxkb_data` 和 `maxkb_postgres`

## 常见问题

### 1. 模型下载失败

**问题**: 首次启动时模型下载失败

**解决方案**:
- 检查网络连接
- 确认 Hugging Face 可访问
- 尝试手动下载：`docker-compose exec backend python -c "from huggingface_hub import snapshot_download; snapshot_download('Osacato/Gitpulse')"`

### 2. 内存不足

**问题**: 容器启动失败或运行缓慢

**解决方案**:
- 增加 Docker 内存限制
- 使用 CPU 版本的 PyTorch（已默认配置）
- 如果使用 GPU，修改 Dockerfile 使用 GPU 版本的 PyTorch

### 3. 端口冲突

**问题**: 端口已被占用

**解决方案**:
- 修改 `docker-compose.yml` 中的端口映射
- 例如：`"5001:5000"` 将后端映射到 5001 端口

### 4. 前端无法连接后端

**问题**: 前端显示连接错误

**解决方案**:
- 检查后端服务是否正常运行：`docker-compose ps`
- 检查后端日志：`docker-compose logs backend`
- 确认前端配置中的 API 地址正确

## 更新服务

```bash
# 停止服务
docker-compose down

# 重新构建并启动
docker-compose up -d --build

# 只更新特定服务
docker-compose up -d --build backend
```

## 清理

```bash
# 停止并删除容器
docker-compose down

# 删除所有数据（包括 volumes）
docker-compose down -v

# 删除镜像
docker-compose down --rmi all
```

## 生产环境建议

1. **使用反向代理**: 使用 Nginx 或 Traefik 作为反向代理
2. **HTTPS**: 配置 SSL 证书
3. **监控**: 添加 Prometheus 和 Grafana 监控
4. **备份**: 定期备份数据目录和 volumes
5. **资源限制**: 在 `docker-compose.yml` 中设置资源限制

## 参考链接

- [GitPulse 模型](https://huggingface.co/Osacato/Gitpulse)
- [Docker 文档](https://docs.docker.com/)
- [Docker Compose 文档](https://docs.docker.com/compose/)

