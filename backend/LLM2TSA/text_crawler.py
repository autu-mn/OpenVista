"""
文本时序数据爬虫
按月爬取最热门的Issue/PR/Commit，与时序数据对齐
"""

import os
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict
from dotenv import load_dotenv

# 加载.env文件（从项目根目录）
# 找到项目根目录（DataPulse）
current_dir = os.path.dirname(os.path.abspath(__file__))
# 向上查找，直到找到包含.env的目录
root_dir = current_dir
while root_dir != os.path.dirname(root_dir):  # 避免无限循环
    env_path = os.path.join(root_dir, '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        break
    root_dir = os.path.dirname(root_dir)
else:
    # 如果没找到，尝试从当前目录向上查找
    load_dotenv()  # 默认行为


class TextTimeSeriesCrawler:
    """文本时序数据爬虫：按月爬取最热门的Issue/PR/Commit"""
    
    def __init__(self, token: str = None):
        self.base_url = "https://api.github.com"
        
        # 支持多Token轮换
        self.tokens = []
        self.current_token_index = 0
        
        if token:
            self.tokens.append(token)
        else:
            # 从环境变量加载多个Token（支持多种命名方式）
            token = os.getenv('GITHUB_TOKEN')
            token_1 = os.getenv('GITHUB_TOKEN_1')
            token_2 = os.getenv('GITHUB_TOKEN_2')
            
            # 按顺序添加Token（GITHUB_TOKEN优先，然后是GITHUB_TOKEN_1和GITHUB_TOKEN_2）
            if token:
                self.tokens.append(token)
            if token_1:
                self.tokens.append(token_1)
            if token_2:
                self.tokens.append(token_2)
        
        if not self.tokens:
            raise ValueError("未找到 GITHUB_TOKEN 或 GITHUB_TOKEN_1/GITHUB_TOKEN_2，请在 .env 文件中配置")
        
        self.token = self.tokens[0]
        self.headers = {
            'Accept': 'application/vnd.github.v3+json'
        }
        if self.token:
            self.headers['Authorization'] = f'token {self.token}'
        
        self.rate_limit_remaining = 5000
    
    def switch_token(self):
        """切换到下一个Token"""
        if len(self.tokens) > 1:
            self.current_token_index = (self.current_token_index + 1) % len(self.tokens)
            self.token = self.tokens[self.current_token_index]
            self.headers['Authorization'] = f'token {self.token}'
            print(f"  [INFO] 切换到Token {self.current_token_index + 1}/{len(self.tokens)}")
    
    def check_rate_limit(self):
        """检查API限流状态"""
        url = f"{self.base_url}/rate_limit"
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                remaining = data['resources']['core']['remaining']
                reset_time = data['resources']['core']['reset']
                self.rate_limit_remaining = remaining
                
                if remaining < 100:
                    print(f"  [WARN] Token {self.current_token_index + 1} 剩余请求数: {remaining}")
                    if len(self.tokens) > 1:
                        self.switch_token()
                return remaining
        except:
            pass
        return self.rate_limit_remaining
    
    def _safe_request(self, url: str, params: dict = None) -> Optional[requests.Response]:
        """安全请求，带重试和Token轮换"""
        for attempt in range(3):
            try:
                # 检查限流状态
                remaining = self.check_rate_limit()
                if remaining < 10 and len(self.tokens) > 1:
                    self.switch_token()
                    remaining = self.check_rate_limit()
                
                response = requests.get(url, headers=self.headers, params=params, timeout=30)
                
                if response.status_code == 200:
                    # 更新限流状态
                    if 'X-RateLimit-Remaining' in response.headers:
                        self.rate_limit_remaining = int(response.headers['X-RateLimit-Remaining'])
                    return response
                elif response.status_code == 403:
                    # API限流
                    if len(self.tokens) > 1:
                        print(f"  [WARN] Token {self.current_token_index + 1} 被限流，切换到下一个Token...")
                        self.switch_token()
                        continue
                    else:
                        print(f"  [WARN] API限流，等待60秒...")
                        time.sleep(60)
                        continue
                else:
                    return None
            except Exception as e:
                if attempt < 2:
                    time.sleep(2)
                    continue
                print(f"  [WARN] 请求失败: {str(e)}")
                return None
        return None
    
    def _get_next_month(self, month: str) -> str:
        """获取下一个月份"""
        date = datetime.strptime(month, "%Y-%m")
        next_date = date + timedelta(days=32)
        return next_date.strftime("%Y-%m")
    
    def _calculate_hot_score(self, item: dict, item_type: str = 'issue') -> float:
        """计算热度分数"""
        comments = item.get('comments', 0)
        reactions = item.get('reactions', {})
        if isinstance(reactions, dict):
            reactions_count = reactions.get('total_count', 0)
        else:
            reactions_count = 0
        
        if item_type in ['issue', 'pr']:
            # Issue/PR: 评论数*0.4 + 点赞数*0.3 + 参与人数*0.3
            assignees = len(item.get('assignees', []))
            return comments * 0.4 + reactions_count * 0.3 + assignees * 0.3
        else:
            # Commit: 评论数 + 点赞数
            return comments + reactions_count
    
    def get_hottest_issue_in_month(self, owner: str, repo: str, month: str) -> Optional[Dict]:
        """获取指定月份最热门的1个Issue"""
        start_date = f"{month}-01T00:00:00Z"
        next_month = self._get_next_month(month)
        
        url = f"{self.base_url}/repos/{owner}/{repo}/issues"
        params = {
            'state': 'all',
            'since': start_date,
            'per_page': 100,
            'sort': 'comments',
            'direction': 'desc'
        }
        
        response = self._safe_request(url, params)
        if not response:
            return None
        
        issues = response.json()
        if not issues:
            return None
        
        # 过滤出该月的Issue（排除PR）
        month_issues = []
        for issue in issues:
            if 'pull_request' in issue:
                continue
            created_at = issue.get('created_at', '')[:7]
            if created_at == month:
                issue['hot_score'] = self._calculate_hot_score(issue, 'issue')
                month_issues.append(issue)
        
        if not month_issues:
            return None
        
        # 选最热门的
        hottest = max(month_issues, key=lambda x: x['hot_score'])
        
        return {
            'title': hottest.get('title', ''),
            'body': (hottest.get('body') or '')[:500],
            'comments': hottest.get('comments', 0),
            'reactions': hottest.get('reactions', {}).get('total_count', 0),
            'hot_score': round(hottest['hot_score'], 2),
            'created_at': hottest.get('created_at', ''),
            'url': hottest.get('html_url', ''),
            'state': hottest.get('state', '')
        }
    
    def get_hottest_pr_in_month(self, owner: str, repo: str, month: str) -> Optional[Dict]:
        """获取指定月份最热门的1个PR"""
        start_date = f"{month}-01T00:00:00Z"
        
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls"
        params = {
            'state': 'all',
            'per_page': 100,
            'sort': 'updated',
            'direction': 'desc'
        }
        
        response = self._safe_request(url, params)
        if not response:
            return None
        
        prs = response.json()
        if not prs:
            return None
        
        # 过滤出该月的PR
        month_prs = []
        for pr in prs:
            created_at = pr.get('created_at', '')[:7]
            if created_at == month:
                pr['hot_score'] = self._calculate_hot_score(pr, 'pr')
                month_prs.append(pr)
        
        if not month_prs:
            return None
        
        hottest = max(month_prs, key=lambda x: x['hot_score'])
        
        return {
            'title': hottest.get('title', ''),
            'body': (hottest.get('body') or '')[:500],
            'comments': hottest.get('comments', 0),
            'hot_score': round(hottest['hot_score'], 2),
            'created_at': hottest.get('created_at', ''),
            'merged_at': hottest.get('merged_at', ''),
            'url': hottest.get('html_url', ''),
            'state': hottest.get('state', '')
        }
    
    def get_hottest_commit_in_month(self, owner: str, repo: str, month: str) -> Optional[Dict]:
        """获取指定月份最热门的1个Commit"""
        start_date = f"{month}-01T00:00:00Z"
        next_month = self._get_next_month(month)
        end_date = f"{next_month}-01T00:00:00Z"
        
        url = f"{self.base_url}/repos/{owner}/{repo}/commits"
        params = {
            'since': start_date,
            'until': end_date,
            'per_page': 100
        }
        
        response = self._safe_request(url, params)
        if not response:
            return None
        
        commits = response.json()
        if not commits:
            return None
        
        # Commit没有直接的热度指标，取第一个（最新的）
        # 或者可以根据message长度、是否是merge commit等判断重要性
        hottest = commits[0]
        commit_info = hottest.get('commit', {})
        
        return {
            'message': commit_info.get('message', '')[:500],
            'author': commit_info.get('author', {}).get('name', ''),
            'committed_at': commit_info.get('author', {}).get('date', ''),
            'url': hottest.get('html_url', ''),
            'sha': hottest.get('sha', '')[:7]
        }
    
    def crawl_text_timeseries(self, owner: str, repo: str, time_axis: List[str], 
                              progress_callback=None) -> Dict[str, Dict]:
        """
        爬取文本时序数据，与时间轴对齐
        
        参数:
            owner: 仓库所有者
            repo: 仓库名
            time_axis: 月份时间轴列表 ["2020-08", "2020-09", ...]
            progress_callback: 进度回调函数
        
        返回:
            {
                "2020-08": {
                    "hottest_issue": {...},
                    "hottest_pr": {...},
                    "hottest_commit": {...}
                },
                ...
            }
        """
        print(f"\n开始爬取文本时序数据: {owner}/{repo}")
        print(f"时间轴: {time_axis[0]} 至 {time_axis[-1]} (共{len(time_axis)}个月)")
        
        text_timeseries = {}
        total_months = len(time_axis)
        
        for i, month in enumerate(time_axis):
            if progress_callback:
                progress = int((i + 1) / total_months * 100)
                progress_callback(i, total_months, f"正在处理 {month}...", progress)
            
            print(f"  [{i+1}/{total_months}] 处理 {month}...")
            
            # 获取该月最热门的Issue/PR/Commit
            hottest_issue = self.get_hottest_issue_in_month(owner, repo, month)
            hottest_pr = self.get_hottest_pr_in_month(owner, repo, month)
            hottest_commit = self.get_hottest_commit_in_month(owner, repo, month)
            
            text_timeseries[month] = {
                'hottest_issue': hottest_issue,
                'hottest_pr': hottest_pr,
                'hottest_commit': hottest_commit
            }
            
            # 打印获取情况
            issue_status = "[OK]" if hottest_issue else "[NO]"
            pr_status = "[OK]" if hottest_pr else "[NO]"
            commit_status = "[OK]" if hottest_commit else "[NO]"
            print(f"      Issue:{issue_status} PR:{pr_status} Commit:{commit_status}")
            
            # 避免触发API限流
            time.sleep(0.3)
        
        # 统计
        issue_count = sum(1 for m in text_timeseries.values() if m.get('hottest_issue'))
        pr_count = sum(1 for m in text_timeseries.values() if m.get('hottest_pr'))
        commit_count = sum(1 for m in text_timeseries.values() if m.get('hottest_commit'))
        
        print(f"\n爬取完成:")
        print(f"  Issue: {issue_count}/{total_months} 个月")
        print(f"  PR: {pr_count}/{total_months} 个月")
        print(f"  Commit: {commit_count}/{total_months} 个月")
        
        return text_timeseries

