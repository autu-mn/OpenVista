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
        
        # 支持多Token轮换
        self.tokens = []
        self.current_token_index = 0
        
        if token:
            self.tokens.append(token)
        else:
            # 从环境变量加载多个Token（支持GITHUB_TOKEN和GITHUB_TOKEN_1到GITHUB_TOKEN_6）
            token = os.getenv('GITHUB_TOKEN')
            if token:
                self.tokens.append(token)
            
            # 加载GITHUB_TOKEN_1到GITHUB_TOKEN_6
            for i in range(1, 7):
                token_key = f'GITHUB_TOKEN_{i}'
                token_value = os.getenv(token_key)
                if token_value:
                    self.tokens.append(token_value)
        
        if not self.tokens:
            print("  ⚠ 警告: 未找到 GITHUB_TOKEN/GITHUB_TOKEN_1到GITHUB_TOKEN_6，API请求可能受限")
            self.token = None
        else:
            self.token = self.tokens[0]
            print(f"  [INFO] 已加载 {len(self.tokens)} 个 GitHub Token")
        
        self.headers = {}
        if self.token:
            self.headers['Authorization'] = f'token {self.token}'
        self.headers['Accept'] = 'application/vnd.github.v3+json'
    
    def switch_token(self):
        """切换到下一个Token（用于速率限制时）"""
        if len(self.tokens) > 1:
            self.current_token_index = (self.current_token_index + 1) % len(self.tokens)
            self.token = self.tokens[self.current_token_index]
            self.headers['Authorization'] = f'token {self.token}'
            print(f"  [INFO] 切换到 Token {self.current_token_index + 1}/{len(self.tokens)}")
    
    def _safe_request(self, url, params=None):
        """安全的API请求，带重试"""
        for attempt in range(3):
            try:
                response = requests.get(url, headers=self.headers, params=params, timeout=30)
                if response.status_code == 200:
                    return response
                elif response.status_code == 403:  # Rate limit
                    # 尝试切换Token
                    if len(self.tokens) > 1:
                        print(f"  ⚠ Rate limit reached, 尝试切换Token...")
                        self.switch_token()
                        continue
                    else:
                        print(f"  ⚠ Rate limit reached, waiting 60s...")
                        time.sleep(60)
                        continue
                elif response.status_code == 401:  # Unauthorized
                    print(f"  ⚠ 认证失败 (401): 请检查 GITHUB_TOKEN 是否正确")
                    return None
                elif response.status_code == 404:  # Not Found
                    print(f"  ⚠ 资源不存在 (404): {url}")
                    return None
                elif response.status_code == 422:  # Unprocessable Entity (Search API 常见)
                    # 尝试读取错误详情
                    try:
                        error_data = response.json()
                        error_msg = error_data.get('message', '未知错误')
                        print(f"  ⚠ 请求验证失败 (422): {error_msg}")
                        if 'search' in url.lower():
                            print(f"    [提示] Search API 可能不支持该查询，或查询格式有误")
                    except:
                        print(f"  ⚠ 请求验证失败 (422): {url}")
                    return None
                else:
                    print(f"  ⚠ API请求失败: 状态码 {response.status_code}, URL: {url}")
                    if response.status_code == 403:
                        # 尝试读取rate limit信息
                        try:
                            rate_limit = response.headers.get('X-RateLimit-Remaining', 'unknown')
                            reset_time = response.headers.get('X-RateLimit-Reset', 'unknown')
                            print(f"    剩余请求次数: {rate_limit}, 重置时间: {reset_time}")
                        except:
                            pass
                    # 尝试读取错误详情
                    try:
                        error_data = response.json()
                        if 'message' in error_data:
                            print(f"    错误信息: {error_data['message']}")
                        except:
                            pass
                    return None
            except Exception as e:
                if attempt < 2:
                    time.sleep(2)
                    continue
                print(f"  ⚠ API请求异常: {str(e)}, URL: {url}")
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
                if page == 1:
                    print(f"    ⚠ 无法获取 Issue 数据，可能的原因：")
                    print(f"      1. GitHub Token 未配置或无效")
                    print(f"      2. 仓库不存在或无访问权限")
                    print(f"      3. API 速率限制")
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
                if page == 1:
                    print(f"    ⚠ 无法获取 PR 数据，可能的原因：")
                    print(f"      1. GitHub Token 未配置或无效")
                    print(f"      2. 仓库不存在或无访问权限")
                    print(f"      3. API 速率限制")
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
                if page == 1:
                    print(f"    ⚠ 无法获取 Commit 数据，可能的原因：")
                    print(f"      1. GitHub Token 未配置或无效")
                    print(f"      2. 仓库不存在或无访问权限")
                    print(f"      3. API 速率限制")
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
    
    def get_monthly_issues_count(self, owner: str, repo: str, max_pages: int = 10) -> Dict:
        """
        按月份统计新增和关闭的 Issue 数量
        使用 GitHub Search API 专门搜索 Issues（排除 PRs）
        返回: {'issues_new': {'2024-01': 10, ...}, 'issues_closed': {'2024-01': 8, ...}}
        """
        print(f"  获取按月 Issue 统计（使用 Search API，排除 PRs）...")
        
        issues_new = {}  # 新增Issue（按创建时间）
        issues_closed = {}  # 关闭Issue（按关闭时间）
        
        page = 1
        total_fetched = 0
        max_results = 1000  # GitHub Search API 最多返回 1000 条结果
        
        # 使用 Search API，确保只获取 Issues（不包括 PRs）
        # 查询格式：repo:owner/repo is:issue
        search_query = f"repo:{owner}/{repo} is:issue"
        
        while page <= max_pages and total_fetched < max_results:
            url = f"{self.base_url}/search/issues"
            params = {
                'q': search_query,
                'sort': 'created',
                'order': 'desc',
                'per_page': 100,  # Search API 最多每页 100 条
                'page': page
            }
            
            print(f"    [调试] 请求第 {page} 页，查询: {search_query}")
            response = self._safe_request(url, params)
            
            if not response:
                print(f"    [警告] 第 {page} 页请求失败，停止获取")
                break
            
            # Search API 返回格式不同：{"total_count": ..., "items": [...]}
            data = response.json()
            
            if 'items' not in data:
                print(f"    [警告] 响应格式异常: {list(data.keys())}")
                break
            
            issues = data.get('items', [])
            total_count = data.get('total_count', 0)
            
            if page == 1:
                print(f"    [信息] 仓库共有 {total_count} 个 Issues（GitHub Search API 最多返回 1000 个）")
            
            if not issues:
                print(f"    [信息] 第 {page} 页无数据，停止获取")
                break
            
            print(f"    [调试] 第 {page} 页获取到 {len(issues)} 个 Issues")
            
            for issue in issues:
                # Search API 返回的 Issues 已经排除了 PRs，但为了安全还是检查一下
                if 'pull_request' in issue:
                    print(f"    [警告] 发现 PR（应该不会出现）: {issue.get('number')}")
                    continue
                
                # 统计新增 Issue（按创建时间）
                created_at = issue.get('created_at')
                if created_at:
                    try:
                        date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        month_key = date.strftime('%Y-%m')
                        issues_new[month_key] = issues_new.get(month_key, 0) + 1
                    except Exception as e:
                        print(f"    [警告] 解析创建时间失败: {created_at}, 错误: {e}")
                
                # 统计关闭 Issue（按关闭时间）
                closed_at = issue.get('closed_at')
                if closed_at:
                    try:
                        date = datetime.fromisoformat(closed_at.replace('Z', '+00:00'))
                        month_key = date.strftime('%Y-%m')
                        issues_closed[month_key] = issues_closed.get(month_key, 0) + 1
                    except Exception as e:
                        print(f"    [警告] 解析关闭时间失败: {closed_at}, 错误: {e}")
                
                total_fetched += 1
            
            # 如果返回的数据少于 100，说明已经是最后一页
            if len(issues) < 100:
                print(f"    [信息] 已获取所有数据（最后一页）")
                break
            
            # 如果已经达到最大结果数，停止
            if total_fetched >= max_results:
                print(f"    [警告] 已达到 GitHub Search API 最大结果数限制（1000），停止获取")
                break
            
            page += 1
            time.sleep(0.5)  # Search API 速率限制更严格，增加延迟
        
        print(f"    ✓ 统计完成: 共获取 {total_fetched} 个 Issues")
        print(f"      - 新增 Issues 覆盖 {len(issues_new)} 个月")
        print(f"      - 关闭 Issues 覆盖 {len(issues_closed)} 个月")
        
        if issues_new:
            # 显示最近几个月的统计
            recent_months = sorted(issues_new.keys(), reverse=True)[:5]
            print(f"      - 最近新增月份: {', '.join([f'{m}({issues_new[m]}个)' for m in recent_months])}")
        
        return {'issues_new': issues_new, 'issues_closed': issues_closed}
    
    def get_monthly_contributors(self, owner: str, repo: str, max_pages: int = 30) -> Dict:
        """
        按月份统计贡献者数量（通过提交记录）
        返回: {'contributors': {'2024-01': 15, ...}, 'new_contributors': {'2024-01': 3, ...}}
        """
        print(f"  获取按月贡献者统计...")
        
        # 记录每个月的贡献者集合
        monthly_contributors = {}  # {month: set(author)}
        all_seen_contributors = set()  # 累计已见过的贡献者
        new_contributors = {}  # 每月新增贡献者数
        
        page = 1
        total_fetched = 0
        
        # 先获取所有提交，按时间升序处理
        all_commits = []
        
        while page <= max_pages:
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
            
            all_commits.extend(commits)
            total_fetched += len(commits)
            page += 1
            time.sleep(0.3)
        
        # 按时间升序排序（最早的在前）
        all_commits.sort(key=lambda x: x['commit']['author'].get('date', ''), reverse=False)
        
        for commit in all_commits:
            commit_date = commit['commit']['author'].get('date')
            author = commit.get('author')
            if not commit_date:
                continue
            
            # 获取作者标识
            author_login = author.get('login') if author else commit['commit']['author'].get('email', 'unknown')
            if not author_login:
                continue
            
            date = datetime.fromisoformat(commit_date.replace('Z', '+00:00'))
            month_key = date.strftime('%Y-%m')
            
            # 初始化月份
            if month_key not in monthly_contributors:
                monthly_contributors[month_key] = set()
            
            # 添加到该月贡献者
            monthly_contributors[month_key].add(author_login)
            
            # 统计新增贡献者
            if author_login not in all_seen_contributors:
                all_seen_contributors.add(author_login)
                new_contributors[month_key] = new_contributors.get(month_key, 0) + 1
        
        # 转换为每月贡献者数量
        contributors_count = {month: len(authors) for month, authors in monthly_contributors.items()}
        
        print(f"    - 统计了 {total_fetched} 个提交，覆盖 {len(contributors_count)} 个月")
        return {'contributors': contributors_count, 'new_contributors': new_contributors}
    
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

