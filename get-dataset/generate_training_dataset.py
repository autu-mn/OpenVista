#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Open-Digger 模型训练数据集生成脚本

功能：
1. 从 OpenDigger 和 GitHub API 爬取时序指标和文本数据
2. 每月爬取 30 个 commit + 50 个 issue（最多）
3. 保留完整文本信息，不截断
4. 按照时间窗口生成训练样本（hist_len=48, pred_len=12, stride=6）
5. 支持批量爬取 10000+ 仓库
6. 支持中断续传
7. 数据预处理和标准化

输出格式：
{
  "metrics": [...],
  "n_dims": 16,
  "hist_len": 48,
  "pred_len": 12,
  "stride": 6,
  "samples": [...]
}
"""

import os
import sys
import json
import time
import argparse
import requests
import numpy as np
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from dotenv import load_dotenv
from pathlib import Path

# 添加项目路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'backend', 'DataProcessor'))

load_dotenv()

# 导入后端模块
try:
    from github_text_crawler import OpenDiggerMetrics, GitHubTextCrawler
    from monthly_crawler import MonthlyCrawler
except ImportError:
    print("错误：无法导入后端模块，请确保在项目根目录运行")
    sys.exit(1)

# 配置常量
PROGRESS_FILE = os.path.join(SCRIPT_DIR, 'crawl_progress.json')
OUTPUT_DIR = os.path.join(SCRIPT_DIR, 'dataset_output')
TEMP_DATA_DIR = os.path.join(SCRIPT_DIR, 'temp_data')

# 16个指标（与模型训练格式一致）
METRICS_LIST = [
    "OpenRank",
    "活跃度",
    "Star数",
    "Fork数",
    "关注度",
    "参与者数",
    "新增贡献者",
    "贡献者",
    "不活跃贡献者",
    "总线因子",
    "新增Issue",
    "关闭Issue",
    "Issue评论",
    "变更请求",
    "PR接受数",
    "PR审查"
]

METRICS_MAPPING = {
    'OpenRank': 'openrank',
    '活跃度': 'activity',
    'Star数': 'stars',
    'Fork数': 'technical_fork',
    '关注度': 'attention',
    '参与者数': 'participants',
    '新增贡献者': 'new_contributors',
    '贡献者': 'contributors',
    '不活跃贡献者': 'inactive_contributors',
    '总线因子': 'bus_factor',
    '新增Issue': 'issues_new',
    '关闭Issue': 'issues_closed',
    'Issue评论': 'issue_comments',
    '变更请求': 'change_requests',
    'PR接受数': 'change_requests_accepted',
    'PR审查': 'change_requests_reviews'
}


class DatasetGenerator:
    """数据集生成器"""
    
    def __init__(self, max_commits_per_month: int = 30, max_issues_per_month: int = 50):
        """
        初始化数据集生成器
        
        Args:
            max_commits_per_month: 每月最多爬取的 commit 数量
            max_issues_per_month: 每月最多爬取的 issue 数量
        """
        self.max_commits_per_month = max_commits_per_month
        self.max_issues_per_month = max_issues_per_month
        
        # 初始化爬虫
        self.opendigger = OpenDiggerMetrics()
        self.monthly_crawler = MonthlyCrawler()
        
        # 创建输出目录
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        os.makedirs(TEMP_DATA_DIR, exist_ok=True)
    
    def crawl_repo_data(self, owner: str, repo: str) -> Optional[Dict]:
        """
        爬取单个仓库的完整数据
        
        Args:
            owner: 仓库所有者
            repo: 仓库名称
            
        Returns:
            包含指标和文本数据的字典，失败返回 None
        """
        print(f"\n{'='*80}")
        print(f"爬取仓库: {owner}/{repo}")
        print(f"{'='*80}")
        
        try:
            # 1. 获取 OpenDigger 指标数据
            print("\n[1/3] 获取 OpenDigger 指标数据...")
            opendigger_data, missing_metrics = self.opendigger.get_metrics(owner, repo)
            
            if not opendigger_data:
                print(f"  ⚠ 无法获取 OpenDigger 数据，跳过该仓库")
                return None
            
            print(f"  ✓ 获取了 {len(opendigger_data)} 个指标")
            
            # 2. 获取时间范围
            all_months = set()
            for metric_data in opendigger_data.values():
                if isinstance(metric_data, dict):
                    all_months.update(metric_data.keys())
            
            if not all_months:
                print(f"  ⚠ 没有有效的时间数据，跳过该仓库")
                return None
            
            sorted_months = sorted([m for m in all_months if len(m) >= 7])
            print(f"  ✓ 时间范围: {sorted_months[0]} 至 {sorted_months[-1]} (共 {len(sorted_months)} 个月)")
            
            # 3. 爬取时序文本数据（commit 和 issue）
            print(f"\n[2/3] 爬取时序文本数据（每月最多 {self.max_commits_per_month} 个 commit + {self.max_issues_per_month} 个 issue）...")
            monthly_text_data = {}
            
            for month in sorted_months:
                print(f"  → 处理 {month}...")
                
                # 爬取 commits（每月最多30个）
                commits = self.monthly_crawler.crawl_commits_by_month(
                    owner, repo, month, max_per_month=self.max_commits_per_month
                )
                
                # 爬取 issues（每月最多50个）
                issues = self.monthly_crawler.crawl_issues_by_month(
                    owner, repo, month, max_per_month=self.max_issues_per_month
                )
                
                # 提取完整文本（不截断）
                commit_texts = self._extract_commit_texts(commits)
                issue_texts = self._extract_issue_texts(issues)
                
                monthly_text_data[month] = {
                    'commits': commit_texts,
                    'issues': issue_texts,
                    'commits_count': len(commits),
                    'issues_count': len(issues)
                }
                
                print(f"    ✓ {month}: {len(commits)} 个 commit, {len(issues)} 个 issue")
                
                # 避免请求过快
                time.sleep(0.2)
            
            # 4. 构建完整数据
            print(f"\n[3/3] 构建数据集...")
            repo_data = {
                'owner': owner,
                'repo': repo,
                'metrics': opendigger_data,
                'text_data': monthly_text_data,
                'months': sorted_months,
                'crawl_time': datetime.now().isoformat()
            }
            
            print(f"  ✓ 数据构建完成")
            return repo_data
            
        except Exception as e:
            print(f"  ✗ 爬取失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def _extract_commit_texts(self, commits: List[Dict]) -> List[Dict]:
        """
        提取 commit 的完整文本信息（不截断）
        
        Args:
            commits: commit 列表
            
        Returns:
            包含完整文本的 commit 列表
        """
        commit_texts = []
        for commit in commits:
            commit_text = {
                'sha': commit.get('sha', ''),
                'message': commit.get('message', ''),
                'author': commit.get('author', {}).get('name', ''),
                'date': commit.get('date', ''),
                'files_changed': commit.get('files', []),
                'full_text': self._build_commit_full_text(commit)
            }
            commit_texts.append(commit_text)
        return commit_texts
    
    def _extract_issue_texts(self, issues: List[Dict]) -> List[Dict]:
        """
        提取 issue 的完整文本信息（不截断）
        
        Args:
            issues: issue 列表
            
        Returns:
            包含完整文本的 issue 列表
        """
        issue_texts = []
        for issue in issues:
            issue_text = {
                'number': issue.get('number', ''),
                'title': issue.get('title', ''),
                'body': issue.get('body', ''),
                'state': issue.get('state', ''),
                'created_at': issue.get('created_at', ''),
                'labels': issue.get('labels', []),
                'comments': issue.get('comments', []),
                'full_text': self._build_issue_full_text(issue)
            }
            issue_texts.append(issue_text)
        return issue_texts
    
    def _build_commit_full_text(self, commit: Dict) -> str:
        """构建 commit 的完整文本（不截断）"""
        texts = []
        
        # Commit message
        message = commit.get('message', '')
        if message:
            texts.append(f"Commit Message: {message}")
        
        # Author
        author = commit.get('author', {}).get('name', '')
        if author:
            texts.append(f"Author: {author}")
        
        # Files changed
        files = commit.get('files', [])
        if files:
            texts.append(f"\nChanged Files ({len(files)}):")
            for f in files:
                filename = f.get('filename', '')
                additions = f.get('additions', 0)
                deletions = f.get('deletions', 0)
                texts.append(f"  - {filename} (+{additions}/-{deletions})")
        
        return "\n".join(texts)
    
    def _build_issue_full_text(self, issue: Dict) -> str:
        """构建 issue 的完整文本（不截断）"""
        texts = []
        
        # Issue title and body
        title = issue.get('title', '')
        body = issue.get('body', '')
        if title:
            texts.append(f"Issue #{issue.get('number', '')}: {title}")
        if body:
            texts.append(f"\n{body}")
        
        # Labels
        labels = issue.get('labels', [])
        if labels:
            texts.append(f"\nLabels: {', '.join(labels)}")
        
        # Comments（完整保留所有评论）
        comments = issue.get('comments', [])
        if comments:
            texts.append(f"\nComments ({len(comments)}):")
            for comment in comments:
                user = comment.get('user', '')
                body = comment.get('body', '')
                created_at = comment.get('created_at', '')
                texts.append(f"\n--- Comment by {user} ({created_at}) ---")
                texts.append(body)
        
        return "\n".join(texts)
    
    def normalize_metrics(self, metrics_data: Dict, months: List[str], owner: str = None, repo: str = None) -> Dict[str, List[float]]:
        """
        标准化指标数据，确保所有月份都有16个指标
        
        Args:
            metrics_data: OpenDigger 指标数据
            months: 月份列表
            owner: 仓库所有者（用于保存）
            repo: 仓库名称（用于保存）
            
        Returns:
            标准化后的指标数据，格式：{metric_name: [values]}
        """
        normalized = {}
        
        for metric_name in METRICS_LIST:
            metric_key = METRICS_MAPPING.get(metric_name, metric_name.lower())
            values = []
            
            # 查找对应的指标数据
            metric_data = None
            for key, data in metrics_data.items():
                if metric_key in key.lower() or key.lower() in metric_key:
                    metric_data = data
                    break
            
            # 提取每个月的值
            for month in months:
                if metric_data and isinstance(metric_data, dict):
                    value = metric_data.get(month, 0.0)
                else:
                    value = 0.0
                values.append(float(value))
            
            normalized[metric_name] = values
        
        # 保存 owner 和 repo 信息
        if owner:
            normalized['_owner'] = owner
        if repo:
            normalized['_repo'] = repo
        
        return normalized
    
    def standardize_metrics(self, normalized_metrics: Dict[str, List[float]]) -> Dict[str, List[float]]:
        """
        对指标进行 Z-score 标准化
        
        Args:
            normalized_metrics: 标准化后的指标数据
            
        Returns:
            Z-score 标准化后的指标数据
        """
        standardized = {}
        
        for metric_name in METRICS_LIST:
            values = np.array(normalized_metrics[metric_name])
            
            # 计算均值和标准差
            mean = np.mean(values)
            std = np.std(values)
            
            # Z-score 标准化
            if std > 0:
                standardized_values = ((values - mean) / std).tolist()
            else:
                standardized_values = values.tolist()
            
            standardized[metric_name] = standardized_values
        
        # 保留元数据
        if '_owner' in normalized_metrics:
            standardized['_owner'] = normalized_metrics['_owner']
        if '_repo' in normalized_metrics:
            standardized['_repo'] = normalized_metrics['_repo']
        
        return standardized
    
    def generate_samples(
        self,
        normalized_metrics: Dict[str, List[float]],
        text_data: Dict[str, Dict],
        months: List[str],
        hist_len: int = 48,
        pred_len: int = 12,
        stride: int = 6
    ) -> List[Dict]:
        """
        生成训练样本（时间窗口采样）
        
        Args:
            normalized_metrics: 标准化后的指标数据
            text_data: 文本数据
            months: 月份列表
            hist_len: 历史长度（48个月）
            pred_len: 预测长度（12个月）
            stride: 步长（6个月）
            
        Returns:
            训练样本列表
        """
        samples = []
        total_months = len(months)
        
        if total_months < hist_len + pred_len:
            print(f"  ⚠ 数据不足（{total_months} 个月），需要至少 {hist_len + pred_len} 个月，跳过")
            return []
        
        # Z-score 标准化
        standardized_metrics = self.standardize_metrics(normalized_metrics)
        
        # 获取 owner 和 repo
        owner = standardized_metrics.get('_owner', '')
        repo = standardized_metrics.get('_repo', '')
        
        # 滑动窗口采样
        start_idx = 0
        while start_idx + hist_len + pred_len <= total_months:
            hist_start_idx = start_idx
            hist_end_idx = start_idx + hist_len
            pred_start_idx = hist_end_idx
            pred_end_idx = hist_end_idx + pred_len
            
            hist_months = months[hist_start_idx:hist_end_idx]
            pred_months = months[pred_start_idx:pred_end_idx]
            
            # 提取历史指标
            hist_metrics = []
            for metric_name in METRICS_LIST:
                values = standardized_metrics[metric_name]
                hist_values = values[hist_start_idx:hist_end_idx]
                hist_metrics.append(hist_values)
            
            # 转置：从 [16个指标, 48个月] 转为 [48个月, 16个指标]
            hist_array = np.array(hist_metrics).T.tolist()
            
            # 提取历史文本（完整保留，不截断）
            hist_texts = {}
            for month in hist_months:
                if month in text_data:
                    hist_texts[month] = text_data[month]
            
            # 构建样本
            sample = {
                "Repo": f"{owner}/{repo}" if owner and repo else "",
                "WindowStart": hist_months[0],
                "WindowEnd": pred_months[-1],
                "HistLen": hist_len,
                "PredLen": pred_len,
                "Hist": hist_array,
                "TextData": hist_texts  # 完整文本数据
            }
            
            samples.append(sample)
            start_idx += stride
        
        return samples
    
    def process_repo(self, owner: str, repo: str) -> Optional[List[Dict]]:
        """
        处理单个仓库，生成训练样本
        
        Args:
            owner: 仓库所有者
            repo: 仓库名称
            
        Returns:
            训练样本列表，失败返回 None
        """
        # 爬取数据
        repo_data = self.crawl_repo_data(owner, repo)
        if not repo_data:
            return None
        
        # 标准化指标
        normalized_metrics = self.normalize_metrics(
            repo_data['metrics'],
            repo_data['months'],
            owner=owner,
            repo=repo
        )
        
        # 生成样本
        samples = self.generate_samples(
            normalized_metrics,
            repo_data['text_data'],
            repo_data['months'],
            hist_len=48,
            pred_len=12,
            stride=6
        )
        
        if not samples:
            print(f"  ⚠ 无法生成样本，跳过")
            return None
        
        print(f"  ✓ 生成了 {len(samples)} 个训练样本")
        return samples
    
    def save_repo_data(self, owner: str, repo: str, repo_data: Dict):
        """保存单个仓库的原始数据（用于调试和续传）"""
        repo_dir = os.path.join(TEMP_DATA_DIR, f"{owner}_{repo}")
        os.makedirs(repo_dir, exist_ok=True)
        
        data_file = os.path.join(repo_dir, 'raw_data.json')
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(repo_data, f, ensure_ascii=False, indent=2)
    
    def load_repo_data(self, owner: str, repo: str) -> Optional[Dict]:
        """加载已保存的仓库数据"""
        repo_dir = os.path.join(TEMP_DATA_DIR, f"{owner}_{repo}")
        data_file = os.path.join(repo_dir, 'raw_data.json')
        
        if os.path.exists(data_file):
            with open(data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None


def load_progress() -> Dict:
    """加载爬取进度"""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    
    return {
        'completed': [],
        'failed': [],
        'samples_count': 0,
        'last_index': 0,
        'started_at': None,
        'updated_at': None
    }


def save_progress(progress: Dict):
    """保存爬取进度"""
    progress['updated_at'] = datetime.now().isoformat()
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def get_repo_list(count: int = 10000) -> List[str]:
    """
    获取仓库列表
    
    Args:
        count: 需要的仓库数量
        
    Returns:
        仓库列表（格式: owner/repo）
    """
    repos = []
    
    # 从预定义列表获取（参考 batch_crawl_opendigger.py）
    predefined_repos = [
        # 前端框架
        "facebook/react", "vuejs/vue", "angular/angular", "sveltejs/svelte",
        "vercel/next.js", "nuxt/nuxt", "remix-run/remix",
        # 后端框架
        "nodejs/node", "django/django", "spring-projects/spring-boot",
        "laravel/laravel", "rails/rails", "expressjs/express",
        "fastapi/fastapi", "pallets/flask",
        # 数据库
        "redis/redis", "mongodb/mongo", "postgres/postgres",
        "mysql/mysql-server", "elastic/elasticsearch",
        "ClickHouse/ClickHouse", "apache/spark", "apache/kafka",
        # 容器与云原生
        "kubernetes/kubernetes", "docker/docker-ce", "moby/moby",
        "containerd/containerd", "helm/helm", "prometheus/prometheus",
        "grafana/grafana", "istio/istio",
        # AI/ML
        "tensorflow/tensorflow", "pytorch/pytorch",
        "huggingface/transformers", "langchain-ai/langchain",
        "AUTOMATIC1111/stable-diffusion-webui", "openai/openai-python",
        "microsoft/DeepSpeed", "Lightning-AI/pytorch-lightning",
        # 编程语言
        "rust-lang/rust", "golang/go", "python/cpython",
        "microsoft/TypeScript", "JetBrains/kotlin", "apple/swift",
        "ziglang/zig",
        # 工具和库
        "microsoft/vscode", "atom/atom", "git/git",
        "jquery/jquery", "lodash/lodash", "moment/moment",
        "axios/axios", "facebook/jest", "mochajs/mocha",
        # 操作系统
        "torvalds/linux", "apple/darwin-xnu",
        # 其他知名项目
        "microsoft/PowerToys", "microsoft/terminal",
        "microsoft/winget-pkgs", "microsoft/fluentui",
        "google/material-design-icons", "google/fonts",
        "adobe-fonts/source-code-pro", "adobe-fonts/source-sans",
    ]
    
    repos.extend(predefined_repos)
    
    # 尝试从 CSV 文件加载（如果存在）
    csv_path = os.path.join(PROJECT_ROOT, 'repo_list.csv')
    if os.path.exists(csv_path):
        try:
            import csv
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    repo_name = row.get('repo', '')
                    if repo_name and '/' in repo_name and repo_name not in repos:
                        repos.append(repo_name)
        except Exception as e:
            print(f"  ⚠ 读取 CSV 文件失败: {str(e)}")
    
    # 如果还不够，尝试从 GitHub API 获取（需要 token）
    if len(repos) < count:
        github_token = os.getenv('GITHUB_TOKEN')
        if github_token:
            try:
                print(f"  从 GitHub API 获取更多仓库...")
                additional_repos = fetch_repos_from_github(
                    limit=count - len(repos),
                    min_stars=1000,
                    token=github_token
                )
                for repo in additional_repos:
                    if repo not in repos:
                        repos.append(repo)
            except Exception as e:
                print(f"  ⚠ 从 GitHub API 获取失败: {str(e)}")
    
    return repos[:count]


def fetch_repos_from_github(limit: int = 1000, min_stars: int = 1000, token: str = None) -> List[str]:
    """
    从 GitHub API 获取热门仓库列表
    
    Args:
        limit: 要获取的仓库数量
        min_stars: 最小 Star 数
        token: GitHub token
        
    Returns:
        仓库列表（格式: owner/repo）
    """
    repos = []
    headers = {}
    if token:
        headers['Authorization'] = f'token {token}'
    
    per_page = 100
    pages_needed = (limit + per_page - 1) // per_page
    
    for page in range(1, min(pages_needed + 1, 11)):  # GitHub API 最多返回1000个结果
        if len(repos) >= limit:
            break
        
        url = "https://api.github.com/search/repositories"
        params = {
            'q': f'stars:>={min_stars} language:*',
            'sort': 'stars',
            'order': 'desc',
            'per_page': per_page,
            'page': page
        }
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                items = data.get('items', [])
                for item in items:
                    full_name = item.get('full_name', '')
                    if full_name and full_name not in repos:
                        repos.append(full_name)
                        if len(repos) >= limit:
                            break
            elif response.status_code == 403:
                print(f"  ⚠ GitHub API 速率限制，停止获取")
                break
            time.sleep(0.5)
        except Exception as e:
            print(f"  ⚠ 获取第 {page} 页失败: {str(e)}")
            break
    
    return repos


def batch_generate_dataset(
    count: int = 10000,
    max_commits_per_month: int = 30,
    max_issues_per_month: int = 50,
    resume: bool = False,
    delay: float = 2.0
):
    """
    批量生成数据集
    
    Args:
        count: 要处理的仓库数量
        max_commits_per_month: 每月最多爬取的 commit 数量
        max_issues_per_month: 每月最多爬取的 issue 数量
        resume: 是否从上次中断处继续
        delay: 每个仓库之间的延迟（秒）
    """
    # 加载进度
    progress = load_progress()
    
    if not resume:
        progress = {
            'completed': [],
            'failed': [],
            'samples_count': 0,
            'last_index': 0,
            'started_at': datetime.now().isoformat(),
            'updated_at': None
        }
    
    # 获取仓库列表
    repos = get_repo_list(count)
    
    # 过滤已完成的仓库
    if resume:
        repos = [r for r in repos if r not in progress['completed']]
    
    if not repos:
        print("没有需要处理的仓库")
        return
    
    print(f"\n{'='*80}")
    print(f"批量生成训练数据集")
    print(f"{'='*80}")
    print(f"目标数量: {count}")
    print(f"待处理: {len(repos)}")
    print(f"已完成: {len(progress.get('completed', []))}")
    print(f"已失败: {len(progress.get('failed', []))}")
    print(f"已生成样本: {progress.get('samples_count', 0)}")
    print(f"每月最多: {max_commits_per_month} commits + {max_issues_per_month} issues")
    print(f"{'='*80}\n")
    
    # 初始化生成器
    generator = DatasetGenerator(
        max_commits_per_month=max_commits_per_month,
        max_issues_per_month=max_issues_per_month
    )
    
    # 收集所有样本
    all_samples = []
    
    # 处理每个仓库
    for idx, repo_full in enumerate(repos):
        owner, repo = repo_full.split('/', 1)
        
        print(f"\n[{idx + 1}/{len(repos)}] 处理 {repo_full}...")
        
        try:
            samples = generator.process_repo(owner, repo)
            
            if samples:
                all_samples.extend(samples)
                progress['completed'].append(repo_full)
                progress['samples_count'] += len(samples)
                print(f"  ✓ 成功，生成了 {len(samples)} 个样本")
            else:
                progress['failed'].append(repo_full)
                print(f"  ✗ 失败")
        except Exception as e:
            progress['failed'].append(repo_full)
            print(f"  ✗ 异常: {str(e)}")
        
        progress['last_index'] = idx + 1
        save_progress(progress)
        
        # 延迟
        if idx < len(repos) - 1:
            time.sleep(delay)
    
    # 保存最终数据集
    print(f"\n{'='*80}")
    print(f"数据集生成完成")
    print(f"{'='*80}")
    print(f"总样本数: {len(all_samples)}")
    print(f"成功仓库: {len(progress['completed'])}")
    print(f"失败仓库: {len(progress['failed'])}")
    
    # 构建最终数据集格式
    dataset = {
        "metrics": METRICS_LIST,
        "n_dims": len(METRICS_LIST),
        "hist_len": 48,
        "pred_len": 12,
        "stride": 6,
        "samples": all_samples
    }
    
    # 保存数据集
    output_file = os.path.join(OUTPUT_DIR, 'training_dataset.json')
    print(f"\n保存数据集到: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)
    
    print(f"✓ 数据集已保存")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='生成 Open-Digger 模型训练数据集')
    parser.add_argument(
        '--count',
        type=int,
        default=10000,
        help='要处理的仓库数量（默认: 10000）'
    )
    parser.add_argument(
        '--max-commits',
        type=int,
        default=30,
        help='每月最多爬取的 commit 数量（默认: 30）'
    )
    parser.add_argument(
        '--max-issues',
        type=int,
        default=50,
        help='每月最多爬取的 issue 数量（默认: 50）'
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help='从上次中断处继续'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=2.0,
        help='每个仓库之间的延迟秒数（默认: 2.0）'
    )
    
    args = parser.parse_args()
    
    batch_generate_dataset(
        count=args.count,
        max_commits_per_month=args.max_commits,
        max_issues_per_month=args.max_issues,
        resume=args.resume,
        delay=args.delay
    )


if __name__ == '__main__':
    main()

