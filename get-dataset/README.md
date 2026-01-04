# Open-Digger 模型训练数据集生成工具

本工具用于生成 Open-Digger 模型训练所需的数据集，包含时序指标和文本数据。

## 功能特性

- ✅ 从 OpenDigger 和 GitHub API 爬取时序指标数据（16个指标）
- ✅ 每月爬取 30 个 commit + 50 个 issue（最多）
- ✅ **完整保留文本信息，不截断**（解决当前版本的截断问题）
- ✅ 按照时间窗口生成训练样本（hist_len=48, pred_len=12, stride=6）
- ✅ 支持批量爬取 10000+ 仓库
- ✅ 支持中断续传
- ✅ 数据预处理和 Z-score 标准化
- ✅ 输出符合模型训练要求的 JSON 格式

## 数据格式

输出数据集格式：

```json
{
  "metrics": [
    "OpenRank", "活跃度", "Star数", "Fork数", "关注度",
    "参与者数", "新增贡献者", "贡献者", "不活跃贡献者",
    "总线因子", "新增Issue", "关闭Issue", "Issue评论",
    "变更请求", "PR接受数", "PR审查"
  ],
  "n_dims": 16,
  "hist_len": 48,
  "pred_len": 12,
  "stride": 6,
  "samples": [
    {
      "Repo": "owner/repo",
      "WindowStart": "2018-03",
      "WindowEnd": "2023-02",
      "HistLen": 48,
      "PredLen": 12,
      "Hist": [
        [-2.748, -2.471, ...],  // 48个月 × 16个指标
        ...
      ],
      "TextData": {
        "2018-03": {
          "commits": [...],
          "issues": [...]
        },
        ...
      }
    }
  ]
}
```

## 环境配置

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

在项目根目录创建 `.env` 文件：

```env
# GitHub API Token（必需，用于爬取 commit 和 issue）
GITHUB_TOKEN=your_github_token_here

# 可选：多个 Token 轮换使用（提高速率限制）
GITHUB_TOKEN_1=token1
GITHUB_TOKEN_2=token2
# ... 最多支持 GITHUB_TOKEN_6
```

### 3. 获取 GitHub Token

1. 访问 https://github.com/settings/tokens
2. 点击 "Generate new token (classic)"
3. 选择权限：`public_repo`（至少）
4. 复制生成的 token 到 `.env` 文件

## 使用方法

### 基本用法

```bash
# 生成数据集（默认10000个仓库）
python generate_training_dataset.py

# 指定仓库数量
python generate_training_dataset.py --count 5000

# 指定每月爬取数量
python generate_training_dataset.py --max-commits 30 --max-issues 50

# 从上次中断处继续
python generate_training_dataset.py --resume

# 自定义延迟（避免速率限制）
python generate_training_dataset.py --delay 3.0
```

### 参数说明

- `--count`: 要处理的仓库数量（默认: 10000）
- `--max-commits`: 每月最多爬取的 commit 数量（默认: 30）
- `--max-issues`: 每月最多爬取的 issue 数量（默认: 50）
- `--resume`: 从上次中断处继续（默认: False）
- `--delay`: 每个仓库之间的延迟秒数（默认: 2.0）

### 仓库列表

脚本会按以下优先级获取仓库列表：

1. **预定义列表**：包含知名开源项目（React、Vue、Kubernetes 等）
2. **CSV 文件**：如果项目根目录存在 `repo_list.csv`，会从中加载
3. **GitHub API**：如果预定义列表和 CSV 不够，会从 GitHub API 获取热门仓库

### CSV 文件格式

如果使用 CSV 文件，格式应为：

```csv
repo,platform
facebook/react,github
vuejs/vue,github
...
```

## 输出文件

### 数据集文件

- `dataset_output/training_dataset.json`: 最终生成的数据集文件

### 临时文件

- `temp_data/{owner}_{repo}/raw_data.json`: 每个仓库的原始数据（用于调试和续传）
- `crawl_progress.json`: 爬取进度文件（用于续传）

## 数据预处理

### 1. 指标标准化

- 确保所有月份都有 16 个指标（缺失的用 0 填充）
- 使用 Z-score 标准化（均值为 0，标准差为 1）

### 2. 文本处理

- **完整保留** commit 和 issue 的文本信息，不截断
- Commit 包含：message、author、changed files
- Issue 包含：title、body、labels、所有评论（完整）

### 3. 时间窗口采样

- 历史长度（hist_len）: 48 个月
- 预测长度（pred_len）: 12 个月
- 步长（stride）: 6 个月
- 滑动窗口生成多个训练样本

## 中断续传

如果爬取过程中断，可以使用 `--resume` 参数继续：

```bash
python generate_training_dataset.py --resume
```

脚本会：
1. 读取 `crawl_progress.json` 获取已完成和失败的仓库
2. 跳过已完成的仓库
3. 从上次中断的位置继续

## 注意事项

### 速率限制

GitHub API 有速率限制：
- 未认证：60 请求/小时
- 认证：5000 请求/小时

建议：
- 使用多个 Token 轮换（配置 `GITHUB_TOKEN_1` 到 `GITHUB_TOKEN_6`）
- 增加延迟时间（`--delay` 参数）
- 分批处理（先处理少量仓库测试）

### 数据量

- 每个仓库平均需要 5-10 分钟（取决于数据量）
- 10000 个仓库预计需要 800-1600 小时（单线程）
- 建议使用多进程或分布式处理

### 存储空间

- 每个仓库原始数据约 1-5 MB
- 10000 个仓库约需要 10-50 GB 存储空间
- 最终数据集文件约 1-10 GB（取决于样本数量）

## 故障排查

### 1. 导入错误

```
错误：无法导入后端模块
```

**解决**：确保在项目根目录运行脚本，或检查 Python 路径配置。

### 2. GitHub API 速率限制

```
403 Rate limit reached
```

**解决**：
- 配置多个 Token
- 增加延迟时间
- 等待速率限制重置

### 3. 数据不足

```
⚠ 数据不足（X 个月），需要至少 60 个月，跳过
```

**解决**：该仓库历史数据不足，会自动跳过。

### 4. 网络错误

```
连接错误 / 超时
```

**解决**：
- 检查网络连接
- 增加重试次数
- 使用代理（如果需要）

## 示例输出

```
================================================================================
批量生成训练数据集
================================================================================
目标数量: 10000
待处理: 10000
已完成: 0
已失败: 0
已生成样本: 0
每月最多: 30 commits + 50 issues
================================================================================

[1/10000] 处理 facebook/react...
================================================================================
爬取仓库: facebook/react
================================================================================

[1/3] 获取 OpenDigger 指标数据...
  ✓ 获取了 16 个指标
  ✓ 时间范围: 2013-05 至 2024-12 (共 140 个月)

[2/3] 爬取时序文本数据（每月最多 30 个 commit + 50 个 issue）...
  → 处理 2013-05...
    ✓ 2013-05: 25 个 commit, 12 个 issue
  ...

[3/3] 构建数据集...
  ✓ 数据构建完成
  ✓ 生成了 15 个训练样本
  ✓ 成功，生成了 15 个样本
```

## 许可证

与主项目保持一致。

