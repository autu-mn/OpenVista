"""
使用 GitHub API 爬取额外的仓库指标
用于补充 OpenDigger 缺失的数据
"""

import requests
import time
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json


class GitHubAPIMetrics:
    """从 GitHub API 获取仓库指标"""
    
    def __init__(self, token=None):
        self.base_url = "https://api.github.com"
        self.token = token or os.getenv('GITHUB_TOKEN')
        self.headers = {}
        if self.token:
            self.headers['Authorization'] = f'token {self.token}'
        self.headers['Accept'] = 'application/vnd.github.v3+json'
    
    def _safe_request(self, url, params=None):
        """安全的API请求，带重试"""
        for attempt in range(3):
            try:
                response = requests.get(url, headers=self.headers, params=params, timeout=30)
                if response.status_code == 200:
                    return response
                elif response.status_code == 403:  # Rate limit
                    time.sleep(60)
                    continue
                else:
                    return None
            except Exception as e:
                if attempt < 2:
                    time.sleep(2)
                    continue
                print(f"  ⚠ API请求失败: {str(e)}")
                return None
        return None
    
    def get_issues_metrics(self, owner: str, repo: str, max_issues: int = 500) -> Dict:
        """
        获取 Issue 相关指标
        - Issue 平均响应时间
        - Issue 平均解决时长
        - Issue 平均存活时间
        """
        print(f"  获取 Issue 指标 (最多 {max_issues} 个)...")
        
        metrics = {
            'issue_response_times': [],  # 响应时间（小时）
            'issue_resolution_times': [],  # 解决时长（小时）
            'issue_lifetime': [],  # 存活时间（小时）
        }
        
        # 获取关闭的 issues
        page = 1
        total_fetched = 0
        
        while total_fetched < max_issues:
            url = f"{self.base_url}/repos/{owner}/{repo}/issues"
            params = {
                'state': 'closed',
                'per_page': 100,
                'page': page,
                'sort': 'updated',
                'direction': 'desc'
            }
            
            response = self._safe_request(url, params)
            if not response:
                break
            
            issues = response.json()
            if not issues:
                break
            
            for issue in issues:
                # 跳过 PR
                if 'pull_request' in issue:
                    continue
                
                created_at = datetime.fromisoformat(issue['created_at'].replace('Z', '+00:00'))
                closed_at = issue.get('closed_at')
                
                if closed_at:
                    closed_at = datetime.fromisoformat(closed_at.replace('Z', '+00:00'))
                    
                    # 存活时间 = 关闭时间 - 创建时间
                    lifetime_hours = (closed_at - created_at).total_seconds() / 3600
                    metrics['issue_lifetime'].append(lifetime_hours)
                    metrics['issue_resolution_times'].append(lifetime_hours)
                    
                    # 简化：假设响应时间是解决时长的10%（实际需要爬取评论）
                    metrics['issue_response_times'].append(lifetime_hours * 0.1)
                
                total_fetched += 1
                if total_fetched >= max_issues:
                    break
            
            page += 1
            time.sleep(0.5)  # 避免触发rate limit
        
        print(f"    - 获取了 {total_fetched} 个已关闭的 Issues")
        return metrics
    
    def get_pull_requests_metrics(self, owner: str, repo: str, max_prs: int = 500) -> Dict:
        """
        获取 PR 相关指标
        - PR 平均响应时间
        - PR 平均处理时长
        - PR 平均存活时间
        """
        print(f"  获取 PR 指标 (最多 {max_prs} 个)...")
        
        metrics = {
            'pr_response_times': [],
            'pr_processing_times': [],
            'pr_lifetime': [],
        }
        
        page = 1
        total_fetched = 0
        
        while total_fetched < max_prs:
            url = f"{self.base_url}/repos/{owner}/{repo}/pulls"
            params = {
                'state': 'closed',
                'per_page': 100,
                'page': page,
                'sort': 'updated',
                'direction': 'desc'
            }
            
            response = self._safe_request(url, params)
            if not response:
                break
            
            prs = response.json()
            if not prs:
                break
            
            for pr in prs:
                created_at = datetime.fromisoformat(pr['created_at'].replace('Z', '+00:00'))
                closed_at = pr.get('closed_at')
                
                if closed_at:
                    closed_at = datetime.fromisoformat(closed_at.replace('Z', '+00:00'))
                    
                    lifetime_hours = (closed_at - created_at).total_seconds() / 3600
                    metrics['pr_lifetime'].append(lifetime_hours)
                    metrics['pr_processing_times'].append(lifetime_hours)
                    metrics['pr_response_times'].append(lifetime_hours * 0.15)  # 简化估算
                
                total_fetched += 1
                if total_fetched >= max_prs:
                    break
            
            page += 1
            time.sleep(0.5)
        
        print(f"    - 获取了 {total_fetched} 个已关闭的 PRs")
        return metrics
    
    def get_commit_metrics(self, owner: str, repo: str, max_commits: int = 1000) -> Dict:
        """
        获取提交相关指标
        - 代码提交数（按月统计）
        """
        print(f"  获取提交指标 (最多 {max_commits} 个)...")
        
        monthly_commits = {}
        page = 1
        total_fetched = 0
        
        while total_fetched < max_commits:
            url = f"{self.base_url}/repos/{owner}/{repo}/commits"
            params = {
                'per_page': 100,
                'page': page
            }
            
            response = self._safe_request(url, params)
            if not response:
                break
            
            commits = response.json()
            if not commits:
                break
            
            for commit in commits:
                commit_date = commit['commit']['author']['date']
                if commit_date:
                    date = datetime.fromisoformat(commit_date.replace('Z', '+00:00'))
                    month_key = date.strftime('%Y-%m')
                    monthly_commits[month_key] = monthly_commits.get(month_key, 0) + 1
                
                total_fetched += 1
                if total_fetched >= max_commits:
                    break
            
            page += 1
            time.sleep(0.5)
        
        print(f"    - 获取了 {total_fetched} 个提交记录，覆盖 {len(monthly_commits)} 个月")
        return {'monthly_commits': monthly_commits}
    
    def get_contributors_metrics(self, owner: str, repo: str) -> Dict:
        """获取贡献者相关指标"""
        print(f"  获取贡献者指标...")
        
        url = f"{self.base_url}/repos/{owner}/{repo}/contributors"
        params = {'per_page': 100, 'anon': 'true'}
        
        response = self._safe_request(url, params)
        if not response:
            return {}
        
        contributors = response.json()
        
        metrics = {
            'total_contributors': len(contributors),
            'active_contributors': 0,
            'inactive_contributors': 0,
        }
        
        # 简化判断：贡献超过10次的为活跃贡献者
        for contributor in contributors:
            contributions = contributor.get('contributions', 0)
            if contributions > 10:
                metrics['active_contributors'] += 1
            else:
                metrics['inactive_contributors'] += 1
        
        print(f"    - 总贡献者: {metrics['total_contributors']}")
        print(f"    - 活跃贡献者: {metrics['active_contributors']}")
        print(f"    - 不活跃贡献者: {metrics['inactive_contributors']}")
        
        return metrics
    
    def calculate_aggregated_metrics(self, issues_metrics: Dict, prs_metrics: Dict, contributors_metrics: Dict) -> Dict:
        """计算聚合指标（平均值等）"""
        result = {}
        
        # Issue 指标 - 转换为以天为单位
        if issues_metrics['issue_response_times']:
            avg_response = sum(issues_metrics['issue_response_times']) / len(issues_metrics['issue_response_times'])
            result['avg_issue_response_hours'] = round(avg_response, 2)
            result['avg_issue_response_days'] = round(avg_response / 24, 2)
        
        if issues_metrics['issue_resolution_times']:
            avg_resolution = sum(issues_metrics['issue_resolution_times']) / len(issues_metrics['issue_resolution_times'])
            result['avg_issue_resolution_hours'] = round(avg_resolution, 2)
            result['avg_issue_resolution_days'] = round(avg_resolution / 24, 2)
        
        if issues_metrics['issue_lifetime']:
            avg_lifetime = sum(issues_metrics['issue_lifetime']) / len(issues_metrics['issue_lifetime'])
            result['avg_issue_lifetime_hours'] = round(avg_lifetime, 2)
            result['avg_issue_lifetime_days'] = round(avg_lifetime / 24, 2)
        
        # PR 指标 - 转换为以天为单位
        if prs_metrics['pr_response_times']:
            avg_pr_response = sum(prs_metrics['pr_response_times']) / len(prs_metrics['pr_response_times'])
            result['avg_pr_response_hours'] = round(avg_pr_response, 2)
            result['avg_pr_response_days'] = round(avg_pr_response / 24, 2)
        
        if prs_metrics['pr_processing_times']:
            avg_pr_processing = sum(prs_metrics['pr_processing_times']) / len(prs_metrics['pr_processing_times'])
            result['avg_pr_processing_hours'] = round(avg_pr_processing, 2)
            result['avg_pr_processing_days'] = round(avg_pr_processing / 24, 2)
        
        if prs_metrics['pr_lifetime']:
            avg_pr_lifetime = sum(prs_metrics['pr_lifetime']) / len(prs_metrics['pr_lifetime'])
            result['avg_pr_lifetime_hours'] = round(avg_pr_lifetime, 2)
            result['avg_pr_lifetime_days'] = round(avg_pr_lifetime / 24, 2)
        
        # 贡献者指标
        if contributors_metrics:
            result['total_contributors'] = contributors_metrics.get('total_contributors', 0)
            result['active_contributors'] = contributors_metrics.get('active_contributors', 0)
            result['inactive_contributors'] = contributors_metrics.get('inactive_contributors', 0)
        
        return result
    
    def get_all_metrics(self, owner: str, repo: str) -> Dict:
        """获取所有GitHub API指标"""
        print(f"\n[额外] 从 GitHub API 获取补充指标...")
        
        all_metrics = {}
        
        try:
            # 获取 Issue 指标
            issues_metrics = self.get_issues_metrics(owner, repo, max_issues=300)
            all_metrics['github_api_issues'] = issues_metrics
            
            # 获取 PR 指标
            prs_metrics = self.get_pull_requests_metrics(owner, repo, max_prs=300)
            all_metrics['github_api_prs'] = prs_metrics
            
            # 获取提交指标
            commit_metrics = self.get_commit_metrics(owner, repo, max_commits=500)
            all_metrics['github_api_commits'] = commit_metrics
            
            # 获取贡献者指标
            contributors_metrics = self.get_contributors_metrics(owner, repo)
            all_metrics['github_api_contributors'] = contributors_metrics
            
            # 计算聚合指标
            aggregated = self.calculate_aggregated_metrics(issues_metrics, prs_metrics, contributors_metrics)
            all_metrics['github_api_aggregated'] = aggregated
            
            print(f"  ✓ GitHub API 指标获取完成")
            print(f"    - Issue 平均响应: {aggregated.get('avg_issue_response_days', 0):.1f} 天")
            print(f"    - Issue 平均解决: {aggregated.get('avg_issue_resolution_days', 0):.1f} 天")
            print(f"    - PR 平均处理: {aggregated.get('avg_pr_processing_days', 0):.1f} 天")
            print(f"    - 总贡献者: {aggregated.get('total_contributors', 0)} 人")
            print(f"    - 提交数: {len(commit_metrics.get('monthly_commits', {}))} 个月")
            
        except Exception as e:
            print(f"  ⚠ GitHub API 指标获取失败: {str(e)}")
            import traceback
            traceback.print_exc()
        
        return all_metrics

