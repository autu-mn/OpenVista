"""
使用GitHub API补充OpenDigger缺失的指标
优先级：OpenDigger > GitHub API > 0填充
"""

import os
import requests
from datetime import datetime, timezone
from typing import Dict, List, Optional
from dotenv import load_dotenv
import time

load_dotenv()


class GitHubMetricsSupplement:
    """使用GitHub API补充缺失的指标"""
    
    def __init__(self):
        self.base_url = "https://api.github.com"
        
        # 支持多Token轮换
        self.tokens = []
        self.current_token_index = 0
        
        token = os.getenv('GITHUB_TOKEN') or os.getenv('github_token')
        token_1 = os.getenv('GITHUB_TOKEN_1') or os.getenv('GitHub_TOKEN_1') or os.getenv('github_token_1')
        token_2 = os.getenv('GITHUB_TOKEN_2') or os.getenv('GitHub_TOKEN_2') or os.getenv('github_token_2')
        
        if token:
            self.tokens.append(token)
        if token_1:
            self.tokens.append(token_1)
        if token_2:
            self.tokens.append(token_2)
        
        if not self.tokens:
            raise ValueError("未找到 GITHUB_TOKEN，请在 .env 文件中配置")
        
        self.token = self.tokens[0]
        self.headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json'
        }
    
    def switch_token(self):
        """切换到下一个Token"""
        if len(self.tokens) > 1:
            self.current_token_index = (self.current_token_index + 1) % len(self.tokens)
            self.token = self.tokens[self.current_token_index]
            self.headers['Authorization'] = f'token {self.token}'
    
    def _safe_request(self, url, params=None, max_retries=3):
        """安全的API请求"""
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=self.headers, params=params, timeout=30)
                if response.status_code == 200:
                    return response
                elif response.status_code == 403:
                    if len(self.tokens) > 1:
                        self.switch_token()
                        continue
                    else:
                        time.sleep(60)
                        continue
                elif response.status_code == 404:
                    return None
                else:
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    return None
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return None
        return None
    
    def get_commits_count_by_month(self, owner: str, repo: str, month: str) -> int:
        """
        获取指定月份的提交数
        month格式: 'YYYY-MM'
        """
        year, month_num = map(int, month.split('-'))
        start_date = datetime(year, month_num, 1, tzinfo=timezone.utc)
        if month_num == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_date = datetime(year, month_num + 1, 1, tzinfo=timezone.utc)
        
        url = f"{self.base_url}/repos/{owner}/{repo}/commits"
        params = {
            'since': start_date.isoformat(),
            'until': end_date.isoformat(),
            'per_page': 1  # 只需要总数，不需要详细数据
        }
        
        response = self._safe_request(url, params)
        if not response:
            return 0
        
        # 从Link头获取总数（如果支持）
        link_header = response.headers.get('Link', '')
        if 'rel="last"' in link_header:
            # 提取最后一页的页码
            import re
            match = re.search(r'page=(\d+)>; rel="last"', link_header)
            if match:
                last_page = int(match.group(1))
                # 获取最后一页的数据来计算总数
                params['per_page'] = 100
                params['page'] = last_page
                last_response = self._safe_request(url, params)
                if last_response:
                    last_data = last_response.json()
                    return (last_page - 1) * 100 + len(last_data)
        
        # 如果没有Link头，遍历所有页面（但限制最大页数）
        count = 0
        page = 1
        max_pages = 10  # 限制最多10页，避免太慢
        
        while page <= max_pages:
            params['page'] = page
            params['per_page'] = 100
            response = self._safe_request(url, params)
            if not response:
                break
            
            data = response.json()
            if not data:
                break
            
            count += len(data)
            if len(data) < 100:
                break
            
            page += 1
        
        return count
    
    def get_pr_declined_count_by_month(self, owner: str, repo: str, month: str) -> int:
        """
        获取指定月份被拒绝的PR数（closed但未merged）
        month格式: 'YYYY-MM'
        """
        year, month_num = map(int, month.split('-'))
        start_date = datetime(year, month_num, 1, tzinfo=timezone.utc)
        if month_num == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_date = datetime(year, month_num + 1, 1, tzinfo=timezone.utc)
        
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls"
        params = {
            'state': 'closed',
            'per_page': 100,
            'sort': 'updated',
            'direction': 'desc'
        }
        
        count = 0
        page = 1
        max_pages = 5  # 限制最多5页
        
        while page <= max_pages:
            params['page'] = page
            response = self._safe_request(url, params)
            if not response:
                break
            
            prs = response.json()
            if not prs:
                break
            
            for pr in prs:
                updated_at = datetime.fromisoformat(pr['updated_at'].replace('Z', '+00:00'))
                
                if updated_at < start_date:
                    return count  # 已经过了这个月份
                
                if start_date <= updated_at < end_date:
                    # 检查是否被拒绝（closed但未merged）
                    if pr.get('merged_at') is None:
                        count += 1
            
            if len(prs) < 100:
                break
            
            page += 1
        
        return count
    
    def get_issue_response_time_by_month(self, owner: str, repo: str, month: str) -> Optional[float]:
        """
        计算指定月份的平均Issue响应时间（小时）
        响应时间 = 第一个评论时间 - Issue创建时间
        month格式: 'YYYY-MM'
        """
        year, month_num = map(int, month.split('-'))
        start_date = datetime(year, month_num, 1, tzinfo=timezone.utc)
        if month_num == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_date = datetime(year, month_num + 1, 1, tzinfo=timezone.utc)
        
        url = f"{self.base_url}/repos/{owner}/{repo}/issues"
        params = {
            'state': 'all',
            'per_page': 100,
            'sort': 'created',
            'direction': 'desc'
        }
        
        response_times = []
        page = 1
        max_pages = 3  # 限制最多3页，避免太慢
        
        while page <= max_pages:
            params['page'] = page
            response = self._safe_request(url, params)
            if not response:
                break
            
            issues = response.json()
            if not issues:
                break
            
            for issue in issues:
                # 跳过PR
                if 'pull_request' in issue:
                    continue
                
                created_at = datetime.fromisoformat(issue['created_at'].replace('Z', '+00:00'))
                
                if created_at < start_date:
                    break  # 已经过了这个月份
                
                if start_date <= created_at < end_date:
                    # 获取第一个评论时间
                    comments_url = issue.get('comments_url')
                    if comments_url and issue.get('comments', 0) > 0:
                        comments_response = self._safe_request(comments_url, {'per_page': 1, 'sort': 'created', 'direction': 'asc'})
                        if comments_response:
                            comments = comments_response.json()
                            if comments:
                                first_comment_time = datetime.fromisoformat(comments[0]['created_at'].replace('Z', '+00:00'))
                                response_time = (first_comment_time - created_at).total_seconds() / 3600  # 转换为小时
                                response_times.append(response_time)
            
            page += 1
        
        if response_times:
            return sum(response_times) / len(response_times)
        return None
    
    def supplement_missing_metrics(self, owner: str, repo: str, opendigger_metrics: Dict, months: List[str]) -> Dict:
        """
        补充缺失的指标
        优先级：OpenDigger > GitHub API补充 > 0填充
        
        返回格式：{metric_name: {month: value, ...}, ...}
        """
        supplemented = {}
        
        # 定义需要补充的指标及其对应的补充函数
        supplement_functions = {
            'Issue响应时间': self.get_issue_response_time_by_month,
            # 注意：OpenDigger没有"代码提交数"和"PR拒绝数"，这些指标不在25个标准指标中
            # 如果需要，可以添加，但需要确保指标名称与all_metrics_list一致
        }
        
        # 检查每个指标是否缺失（完全缺失或部分月份缺失）
        for metric_name, supplement_func in supplement_functions.items():
            if metric_name not in opendigger_metrics:
                # 完全缺失，需要补充
                print(f"    - 补充 {metric_name}（完全缺失）...")
                metric_data = {}
                
                for month in months:
                    try:
                        value = supplement_func(owner, repo, month)
                        if value is not None:
                            metric_data[month] = value
                        else:
                            # GitHub API无法获取，用0填充
                            metric_data[month] = 0.0
                    except Exception as e:
                        print(f"      ⚠ {month} 补充失败: {str(e)}")
                        # 补充失败，该月份用0填充
                        metric_data[month] = 0.0
                
                if metric_data:
                    supplemented[metric_name] = metric_data
                    print(f"      ✓ 已补充 {len(metric_data)} 个月的数据")
            else:
                # 部分缺失，补充缺失的月份
                existing_data = opendigger_metrics[metric_name]
                if isinstance(existing_data, dict):
                    # 找出缺失或为0的月份
                    missing_months = [
                        m for m in months 
                        if m not in existing_data or existing_data.get(m) == 0 or existing_data.get(m) is None
                    ]
                    if missing_months:
                        print(f"    - 补充 {metric_name}（{len(missing_months)} 个月缺失）...")
                        metric_data = existing_data.copy()
                        
                        for month in missing_months:
                            try:
                                value = supplement_func(owner, repo, month)
                                if value is not None and value != 0:
                                    metric_data[month] = value
                                else:
                                    # GitHub API无法获取，保持原值（可能是0）
                                    pass
                            except Exception as e:
                                print(f"      ⚠ {month} 补充失败: {str(e)}")
                                # 补充失败，保持原值（可能是0）
                        
                        supplemented[metric_name] = metric_data
                        print(f"      ✓ 已补充 {len(missing_months)} 个月的数据")
        
        return supplemented

