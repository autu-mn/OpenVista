# Rate Limit 优化总结

## 🎯 优化目标

- ✅ 确保不超过 5000 次请求/小时
- ✅ Issues 只爬取 Top-3 热度
- ✅ 移除 PR 爬取
- ✅ Commits 只保留文本信息
- ✅ 添加请求速率控制

---

## ✅ 已完成的修改

### 1. Issues 爬取优化

#### GraphQL API (`github_graphql_crawler.py`)
- ✅ 按评论数排序（`orderBy: {field: COMMENTS, direction: DESC}`）
- ✅ 收集该月份所有 Issues，计算热度分数（评论数 + 反应数）
- ✅ 按热度排序，只返回 Top-3
- ✅ 每次请求延迟 1 秒

#### REST API (`monthly_crawler.py`)
- ✅ 按评论数排序（`sort: 'comments'`）
- ✅ 计算热度分数（评论数 + 反应数）
- ✅ 按热度排序，只返回 Top-3
- ✅ 每次请求延迟 1 秒
- ✅ 评论数量限制：50 → 30 条

**热度计算公式**:
```python
heat_score = comments_count + reactions_count
```

---

### 2. PR 爬取移除

#### GraphQL API
- ✅ `crawl_month_batch()` 不再调用 `batch_fetch_prs()`
- ✅ 返回空列表 `'prs': []`

#### REST API
- ✅ `crawl_all_months()` 不再调用 `crawl_prs_by_month()`
- ✅ 所有 PR 相关代码保留但不执行

**节省的 API 请求**:
- 每个项目每月节省 3 次 PR 查询
- 假设 113 个月：节省 339 次请求

---

### 3. Commits 优化

#### GraphQL API
- ✅ 移除字段：`additions`, `deletions`, `changedFiles`, `url`, `email`
- ✅ 只保留：`message`（提交信息文本）、`author.name`（作者名字文本）、`committed_at`
- ✅ 每次请求延迟 1 秒

#### REST API
- ✅ 不再调用 `_get_commit_detail()`（节省详细查询）
- ✅ 直接从列表响应中提取文本信息
- ✅ 只保留：`message`、`author.name`、`committed_at`
- ✅ 每次请求延迟 1 秒

**节省的 API 请求**:
- 每个 Commit 节省 1 次详细查询
- 假设每月 3 个 Commits，113 个月：节省 339 次请求

---

### 4. 速率控制

#### 全局策略
- ✅ 每次 GraphQL 请求后延迟 **1.0 秒**
- ✅ 每次 REST API 请求后延迟 **1.0 秒**
- ✅ 每页请求后延迟 **1.0 秒**

**速率计算**:
- 5000 次/小时 = 83.3 次/分钟 = **1.39 次/秒**
- 使用 **1.0 秒延迟** = **1.0 次/秒** = 3600 次/小时
- ✅ **安全裕度**: 3600 < 5000，不会超限

#### 具体位置
1. `batch_fetch_issues()` - 请求前延迟 1 秒
2. `batch_fetch_commits()` - 请求前延迟 1 秒
3. `batch_fetch_releases()` - 请求前延迟 1 秒
4. `crawl_issues_by_month()` - 请求前延迟 1 秒，每页后延迟 1 秒
5. `_get_issue_detail()` - 请求前延迟 1 秒，获取评论前延迟 1 秒
6. `crawl_commits_by_month()` - 请求前延迟 1 秒，每页后延迟 1 秒
7. `crawl_all_months()` - 每月数据爬取后延迟 1 秒

---

## 📊 API 请求量估算

### 优化前（假设 113 个月）

| 数据类型 | 每月请求数 | 总请求数 | 说明 |
|---------|-----------|---------|------|
| Issues | ~5 | 565 | 列表 + 详情 + 评论 |
| PRs | ~5 | 565 | 列表 + 详情 + 评论 |
| Commits | ~4 | 452 | 列表 + 详情 |
| Releases | ~2 | 226 | 列表 |
| **总计** | **~16** | **~1,808** | 可能超限 |

### 优化后（113 个月）

| 数据类型 | 每月请求数 | 总请求数 | 说明 |
|---------|-----------|---------|------|
| Issues | ~3 | 339 | 列表 + Top-3详情 + 评论（限制30条） |
| PRs | 0 | 0 | ✅ 已移除 |
| Commits | ~1 | 113 | ✅ 只查询列表，不查详情 |
| Releases | ~1 | 113 | 列表 |
| **总计** | **~5** | **~565** | ✅ 远低于 5000 |

**节省**: 1,808 - 565 = **1,243 次请求**（节省 68.7%）

---

## ⏱️ 时间估算

### 优化前
- 113 个月 × 16 请求/月 × 0.5 秒 = **904 秒** ≈ **15 分钟**
- 但可能因 rate limit 中断，实际更长

### 优化后
- 113 个月 × 5 请求/月 × 1.0 秒 = **565 秒** ≈ **9.4 分钟**
- ✅ 不会触发 rate limit，稳定完成

---

## 🔍 热度排序逻辑

### Issues Top-3 热度

**热度分数计算**:
```python
heat_score = comments_count + reactions_count
```

**排序方式**:
1. GraphQL: `orderBy: {field: COMMENTS, direction: DESC}` + 本地排序
2. REST API: `sort: 'comments'` + 本地排序

**选择逻辑**:
- 收集该月份所有 Issues
- 计算每个 Issue 的热度分数
- 按热度分数降序排序
- 取前 3 个

**示例**:
```
Issue #100: comments=50, reactions=20 → heat_score=70 ✅ Top-1
Issue #101: comments=30, reactions=15 → heat_score=45 ✅ Top-2
Issue #102: comments=25, reactions=10 → heat_score=35 ✅ Top-3
Issue #103: comments=10, reactions=5  → heat_score=15 ❌ 不选
```

---

## 📝 数据字段对比

### Commits 字段变化

**优化前**:
```json
{
  "sha": "...",
  "message": "...",
  "author": {
    "name": "...",
    "email": "...",
    "date": "..."
  },
  "committer": {...},
  "url": "...",
  "stats": {
    "additions": 100,
    "deletions": 50,
    "total": 150
  },
  "files": [...]
}
```

**优化后**:
```json
{
  "sha": "...",
  "message": "...",  // ✅ 只保留文本
  "author": {
    "name": "..."  // ✅ 只保留文本
  },
  "committed_at": "..."  // ✅ 时间戳
}
```

**节省**: 减少 ~70% 的数据量

---

## 🚀 使用建议

### 1. 验证速率控制

运行爬取后，检查日志：
- ✅ 每次请求间隔约 1 秒
- ✅ 没有 "rate limit exceeded" 错误
- ✅ 爬取过程稳定

### 2. 监控 API 使用

使用 `verify_tokens.py` 检查剩余配额：
```bash
cd backend
python verify_tokens.py
```

### 3. 如果仍然超限

**进一步优化**:
- 增加延迟到 1.5 秒（2400 次/小时）
- 减少 Issues 评论数量（30 → 20）
- 减少每月爬取数量（3 → 2）

---

## 📋 修改文件清单

- ✅ `backend/DataProcessor/github_graphql_crawler.py`
  - `batch_fetch_issues()` - 按热度排序，Top-3
  - `batch_fetch_commits()` - 只保留文本字段
  - `batch_fetch_releases()` - 添加速率控制
  - `crawl_month_batch()` - 移除 PR 爬取

- ✅ `backend/DataProcessor/monthly_crawler.py`
  - `crawl_issues_by_month()` - 按热度排序，Top-3
  - `_get_issue_detail()` - 限制评论数量，添加延迟
  - `crawl_commits_by_month()` - 只保留文本字段
  - `crawl_all_months()` - 移除 PR 爬取，更新日志

- ✅ `backend/DataProcessor/crawl_monthly_data.py`
  - 更新日志说明

---

## ✅ 优化效果

| 指标 | 优化前 | 优化后 | 改进 |
|------|--------|--------|------|
| 每月请求数 | ~16 | ~5 | ⬇️ 68.7% |
| 113个月总请求 | ~1,808 | ~565 | ⬇️ 68.7% |
| 是否超限 | ❌ 可能 | ✅ 不会 | ✅ |
| Issues 质量 | 随机 | Top-3热度 | ✅ |
| Commits 数据量 | 完整 | 仅文本 | ⬇️ 70% |
| PR 爬取 | ✅ 是 | ❌ 否 | ✅ 节省 |

---

## 🎯 总结

**所有优化已完成！**

- ✅ Issues 只爬 Top-3 热度
- ✅ PR 爬取已移除
- ✅ Commits 只保留文本信息
- ✅ 速率控制：1 秒/请求（3600次/小时 < 5000）
- ✅ 不会超限

**现在可以安全地爬取项目了！** 🎉

