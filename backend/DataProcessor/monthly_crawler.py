"""
按月爬取GitHub仓库数据
- Issue/PR：按更新时间
- Commit：按提交时间
- Release：按发布时间
每月最多30个
"""

import os
import requests
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()


class MonthlyCrawler:
    """按月爬取GitHub仓库数据"""
    
    def __init__(self):
        self.base_url = "https://api.github.com"
        
        # 支持多Token轮换（支持不同大小写）
        self.tokens = []
        self.current_token_index = 0
        
        # 检查多种可能的token名称（大小写兼容）
        token = os.getenv('GITHUB_TOKEN') or os.getenv('github_token')
        token_1 = os.getenv('GITHUB_TOKEN_1') or os.getenv('GitHub_TOKEN_1') or os.getenv('github_token_1')
        token_2 = os.getenv('GITHUB_TOKEN_2') or os.getenv('GitHub_TOKEN_2') or os.getenv('github_token_2')
        
        if token:
            self.tokens.append(token)
        if token_1:
            self.tokens.append(token_1)
        if token_2:
            self.tokens.append(token_2)
        
        # 轮换使用token
        if len(self.tokens) > 1:
            print(f"  [INFO] 已加载 {len(self.tokens)} 个 GitHub Token，将轮换使用")
        
        if not self.tokens:
            raise ValueError("未找到 GITHUB_TOKEN，请在 .env 文件中配置")
        
        self.token = self.tokens[0]
        self.headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json'
        }
    
    def switch_token(self):
        """切换到下一个Token（静默切换，避免过多输出）"""
        if len(self.tokens) > 1:
            self.current_token_index = (self.current_token_index + 1) % len(self.tokens)
            self.token = self.tokens[self.current_token_index]
            self.headers['Authorization'] = f'token {self.token}'
            # 只在切换时输出一次，避免过多日志
            # print(f"  [INFO] 使用 Token {self.current_token_index + 1}/{len(self.tokens)}")
    
    def _safe_request(self, url, params=None, max_retries=3):
        """安全的API请求（支持token轮换）"""
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=self.headers, params=params, timeout=30)
                if response.status_code == 200:
                    return response
                elif response.status_code == 403:
                    if len(self.tokens) > 1:
                        print(f"  ⚠ Rate limit reached, 切换Token...")
                        self.switch_token()
                        continue
                    else:
                        print(f"  ⚠ Rate limit reached, waiting 60s...")
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
                print(f"  ⚠ 请求失败: {str(e)}")
                return None
        return None
    
    def get_repo_created_at(self, owner: str, repo: str) -> Optional[str]:
        """获取仓库创建时间（返回YYYY-MM格式）"""
        url = f"{self.base_url}/repos/{owner}/{repo}"
        response = self._safe_request(url)
        if response:
            data = response.json()
            created_at = data.get('created_at', '')
            if created_at:
                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                return dt.strftime('%Y-%m')
        return None
    
    def crawl_issues_by_month(self, owner: str, repo: str, month: str, max_per_month: int = 30) -> List[Dict]:
        """
        按月份爬取Issues（按更新时间）
        month格式: 'YYYY-MM'
        """
        from datetime import timezone
        
        year, month_num = map(int, month.split('-'))
        start_date = datetime(year, month_num, 1, tzinfo=timezone.utc)
        if month_num == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_date = datetime(year, month_num + 1, 1, tzinfo=timezone.utc)
        
        issues = []
        page = 1
        
        while len(issues) < max_per_month:
            url = f"{self.base_url}/repos/{owner}/{repo}/issues"
            params = {
                'state': 'all',
                'per_page': 100,
                'page': page,
                'sort': 'updated',
                'direction': 'desc'
            }
            
            response = self._safe_request(url, params)
            if not response:
                break
            
            data = response.json()
            if not data:
                break
            
            for issue in data:
                # 跳过PR
                if 'pull_request' in issue:
                    continue
                
                updated_at = datetime.fromisoformat(issue['updated_at'].replace('Z', '+00:00'))
                
                # 判断是否在该月份
                if start_date <= updated_at < end_date:
                    # 获取详细内容
                    issue_detail = self._get_issue_detail(owner, repo, issue['number'])
                    if issue_detail:
                        issues.append(issue_detail)
                    
                    if len(issues) >= max_per_month:
                        break
                elif updated_at < start_date:
                    # 已经过了这个月份，停止
                    return issues
            
            page += 1
            time.sleep(0.5)
        
        return issues[:max_per_month]
    
    def _get_issue_detail(self, owner: str, repo: str, issue_number: int) -> Optional[Dict]:
        """获取Issue详细内容（包括评论）"""
        url = f"{self.base_url}/repos/{owner}/{repo}/issues/{issue_number}"
        response = self._safe_request(url)
        if not response:
            return None
        
        issue = response.json()
        
        # 获取评论
        comments = []
        comments_url = issue.get('comments_url')
        if comments_url and issue.get('comments', 0) > 0:
            comments_response = self._safe_request(comments_url, {'per_page': 100})
            if comments_response:
                comments_data = comments_response.json()
                comments = [
                    {
                        'body': c.get('body', ''),
                        'user': c.get('user', {}).get('login', ''),
                        'created_at': c.get('created_at', ''),
                        'reactions': {
                            'total_count': c.get('reactions', {}).get('total_count', 0),
                            'thumbs_up': c.get('reactions', {}).get('+1', 0),
                        }
                    }
                    for c in comments_data[:50]  # 最多50条评论
                ]
            time.sleep(0.3)
        
        return {
            'number': issue['number'],
            'title': issue.get('title', ''),
            'body': issue.get('body', ''),
            'state': issue.get('state', ''),
            'created_at': issue['created_at'],
            'updated_at': issue['updated_at'],
            'closed_at': issue.get('closed_at'),
            'comments_count': issue.get('comments', 0),
            'reactions': {
                'total_count': issue.get('reactions', {}).get('total_count', 0),
                'thumbs_up': issue.get('reactions', {}).get('+1', 0),
                'thumbs_down': issue.get('reactions', {}).get('-1', 0),
                'laugh': issue.get('reactions', {}).get('laugh', 0),
                'hooray': issue.get('reactions', {}).get('hooray', 0),
                'confused': issue.get('reactions', {}).get('confused', 0),
                'heart': issue.get('reactions', {}).get('heart', 0),
                'rocket': issue.get('reactions', {}).get('rocket', 0),
                'eyes': issue.get('reactions', {}).get('eyes', 0),
            },
            'labels': [label['name'] for label in issue.get('labels', [])],
            'user': issue.get('user', {}).get('login', ''),
            'assignees': [assignee['login'] for assignee in issue.get('assignees', [])],
            'comments': comments
        }
    
    def crawl_prs_by_month(self, owner: str, repo: str, month: str, max_per_month: int = 30) -> List[Dict]:
        """
        按月份爬取PRs（按更新时间）
        month格式: 'YYYY-MM'
        """
        from datetime import timezone
        
        year, month_num = map(int, month.split('-'))
        start_date = datetime(year, month_num, 1, tzinfo=timezone.utc)
        if month_num == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_date = datetime(year, month_num + 1, 1, tzinfo=timezone.utc)
        
        prs = []
        page = 1
        
        while len(prs) < max_per_month:
            url = f"{self.base_url}/repos/{owner}/{repo}/pulls"
            params = {
                'state': 'all',
                'per_page': 100,
                'page': page,
                'sort': 'updated',
                'direction': 'desc'
            }
            
            response = self._safe_request(url, params)
            if not response:
                break
            
            data = response.json()
            if not data:
                break
            
            for pr in data:
                updated_at = datetime.fromisoformat(pr['updated_at'].replace('Z', '+00:00'))
                
                if start_date <= updated_at < end_date:
                    pr_detail = self._get_pr_detail(owner, repo, pr['number'])
                    if pr_detail:
                        prs.append(pr_detail)
                    
                    if len(prs) >= max_per_month:
                        break
                elif updated_at < start_date:
                    return prs
            
            page += 1
            time.sleep(0.5)
        
        return prs[:max_per_month]
    
    def _get_pr_detail(self, owner: str, repo: str, pr_number: int) -> Optional[Dict]:
        """获取PR详细内容（包括评论和review comments）"""
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}"
        response = self._safe_request(url)
        if not response:
            return None
        
        pr = response.json()
        
        # 获取评论
        comments = []
        comments_url = pr.get('comments_url')
        if comments_url and pr.get('comments', 0) > 0:
            comments_response = self._safe_request(comments_url, {'per_page': 100})
            if comments_response:
                comments_data = comments_response.json()
                comments = [
                    {
                        'body': c.get('body', ''),
                        'user': c.get('user', {}).get('login', ''),
                        'created_at': c.get('created_at', ''),
                        'reactions': {
                            'total_count': c.get('reactions', {}).get('total_count', 0),
                        }
                    }
                    for c in comments_data[:50]
                ]
            time.sleep(0.3)
        
        # 获取review comments
        review_comments = []
        review_comments_url = pr.get('review_comments_url')
        if review_comments_url and pr.get('review_comments', 0) > 0:
            review_response = self._safe_request(review_comments_url, {'per_page': 100})
            if review_response:
                review_data = review_response.json()
                review_comments = [
                    {
                        'body': c.get('body', ''),
                        'user': c.get('user', {}).get('login', ''),
                        'created_at': c.get('created_at', ''),
                        'path': c.get('path', ''),
                        'line': c.get('line', None),
                    }
                    for c in review_data[:50]
                ]
            time.sleep(0.3)
        
        return {
            'number': pr['number'],
            'title': pr.get('title', ''),
            'body': pr.get('body', ''),
            'state': pr.get('state', ''),
            'merged': pr.get('merged', False),
            'created_at': pr['created_at'],
            'updated_at': pr['updated_at'],
            'closed_at': pr.get('closed_at'),
            'merged_at': pr.get('merged_at'),
            'comments_count': pr.get('comments', 0),
            'review_comments_count': pr.get('review_comments', 0),
            'commits_count': pr.get('commits', 0),
            'additions': pr.get('additions', 0),
            'deletions': pr.get('deletions', 0),
            'changed_files': pr.get('changed_files', 0),
            'reactions': {
                'total_count': pr.get('reactions', {}).get('total_count', 0),
                'thumbs_up': pr.get('reactions', {}).get('+1', 0),
                'thumbs_down': pr.get('reactions', {}).get('-1', 0),
                'laugh': pr.get('reactions', {}).get('laugh', 0),
                'hooray': pr.get('reactions', {}).get('hooray', 0),
                'confused': pr.get('reactions', {}).get('confused', 0),
                'heart': pr.get('reactions', {}).get('heart', 0),
                'rocket': pr.get('reactions', {}).get('rocket', 0),
                'eyes': pr.get('reactions', {}).get('eyes', 0),
            },
            'labels': [label['name'] for label in pr.get('labels', [])],
            'user': pr.get('user', {}).get('login', ''),
            'assignees': [assignee['login'] for assignee in pr.get('assignees', [])],
            'requested_reviewers': [reviewer['login'] for reviewer in pr.get('requested_reviewers', [])],
            'comments': comments,
            'review_comments': review_comments
        }
    
    def crawl_commits_by_month(self, owner: str, repo: str, month: str, max_per_month: int = 30) -> List[Dict]:
        """
        按月份爬取Commits（按提交时间）
        month格式: 'YYYY-MM'
        """
        from datetime import timezone
        
        year, month_num = map(int, month.split('-'))
        start_date = datetime(year, month_num, 1, tzinfo=timezone.utc)
        if month_num == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_date = datetime(year, month_num + 1, 1, tzinfo=timezone.utc)
        
        commits = []
        page = 1
        
        while len(commits) < max_per_month:
            url = f"{self.base_url}/repos/{owner}/{repo}/commits"
            params = {
                'per_page': 100,
                'page': page
            }
            
            response = self._safe_request(url, params)
            if not response:
                break
            
            data = response.json()
            if not data:
                break
            
            for commit in data:
                commit_date_str = commit['commit']['author']['date']
                commit_date = datetime.fromisoformat(commit_date_str.replace('Z', '+00:00'))
                
                if start_date <= commit_date < end_date:
                    commit_detail = self._get_commit_detail(owner, repo, commit['sha'])
                    if commit_detail:
                        commits.append(commit_detail)
                    
                    if len(commits) >= max_per_month:
                        break
                elif commit_date < start_date:
                    return commits
            
            page += 1
            time.sleep(0.5)
        
        return commits[:max_per_month]
    
    def _get_commit_detail(self, owner: str, repo: str, sha: str) -> Optional[Dict]:
        """获取Commit详细内容（包括代码变更）"""
        url = f"{self.base_url}/repos/{owner}/{repo}/commits/{sha}"
        response = self._safe_request(url)
        if not response:
            return None
        
        commit = response.json()
        commit_data = commit['commit']
        
        return {
            'sha': commit['sha'],
            'message': commit_data.get('message', ''),
            'author': {
                'name': commit_data['author'].get('name', ''),
                'email': commit_data['author'].get('email', ''),
                'date': commit_data['author'].get('date', '')
            },
            'committer': {
                'name': commit_data['committer'].get('name', ''),
                'email': commit_data['committer'].get('email', ''),
                'date': commit_data['committer'].get('date', '')
            },
            'url': commit.get('html_url', ''),
            'stats': {
                'additions': commit.get('stats', {}).get('additions', 0),
                'deletions': commit.get('stats', {}).get('deletions', 0),
                'total': commit.get('stats', {}).get('total', 0)
            },
            'files': [
                {
                    'filename': f.get('filename', ''),
                    'additions': f.get('additions', 0),
                    'deletions': f.get('deletions', 0),
                    'changes': f.get('changes', 0),
                    'status': f.get('status', ''),
                    'patch': f.get('patch', '')[:500] if f.get('patch') else ''  # 限制大小
                }
                for f in commit.get('files', [])[:20]  # 最多20个文件
            ]
        }
    
    def crawl_releases_by_month(self, owner: str, repo: str, month: str) -> List[Dict]:
        """
        按月份爬取Releases（按发布时间）
        month格式: 'YYYY-MM'
        """
        from datetime import timezone
        
        year, month_num = map(int, month.split('-'))
        start_date = datetime(year, month_num, 1, tzinfo=timezone.utc)
        if month_num == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_date = datetime(year, month_num + 1, 1, tzinfo=timezone.utc)
        
        releases = []
        page = 1
        
        while True:
            url = f"{self.base_url}/repos/{owner}/{repo}/releases"
            params = {
                'per_page': 100,
                'page': page
            }
            
            response = self._safe_request(url, params)
            if not response:
                break
            
            data = response.json()
            if not data:
                break
            
            for release in data:
                published_at = release.get('published_at')
                if not published_at:
                    continue
                
                pub_date = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                
                if start_date <= pub_date < end_date:
                    releases.append({
                        'tag_name': release.get('tag_name', ''),
                        'name': release.get('name', ''),
                        'body': release.get('body', ''),
                        'created_at': release.get('created_at', ''),
                        'published_at': published_at,
                        'author': release.get('author', {}).get('login', ''),
                        'url': release.get('html_url', ''),
                        'prerelease': release.get('prerelease', False),
                        'draft': release.get('draft', False)
                    })
                elif pub_date < start_date:
                    return releases
            
            page += 1
            time.sleep(0.5)
        
        return releases
    
    def generate_month_list(self, owner: str, repo: str) -> List[str]:
        """生成从仓库创建到当前的所有月份列表"""
        created_month = self.get_repo_created_at(owner, repo)
        if not created_month:
            created_month = datetime.now().strftime('%Y-%m')
        
        months = []
        current = datetime.strptime(created_month, '%Y-%m')
        end = datetime.now()
        
        while current <= end:
            months.append(current.strftime('%Y-%m'))
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
        
        return months
    
    def crawl_all_months(self, owner: str, repo: str, max_per_month: int = 3, progress_callback=None, use_graphql: bool = True) -> Dict:
        """
        爬取所有月份的数据（使用GraphQL API和并发请求优化）
        返回格式：
        {
          'monthly_data': {
            '2024-01': {...},
            '2024-02': {...},
            ...
          },
          'repo_info': {...}
        }
        """
        print(f"\n{'='*60}")
        print(f"开始按月爬取仓库: {owner}/{repo}")
        if use_graphql:
            print(f"使用 GraphQL API + 并发请求（优化模式）")
        print(f"{'='*60}\n")
        
        # 获取仓库信息
        repo_info_url = f"{self.base_url}/repos/{owner}/{repo}"
        repo_response = self._safe_request(repo_info_url)
        repo_info = repo_response.json() if repo_response else {}
        
        # 生成月份列表
        months = self.generate_month_list(owner, repo)
        print(f"  需要爬取的月份数: {len(months)}")
        
        monthly_data = {}
        total_months = len(months)
        
        if use_graphql:
            # 使用GraphQL API批量爬取（并发）
            from .github_graphql_crawler import GitHubGraphQLCrawler
            graphql_crawler = GitHubGraphQLCrawler()
            
            # 并发爬取所有月份（分批处理，避免过多并发）
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            def crawl_single_month(month: str) -> tuple:
                """爬取单个月份的数据"""
                try:
                    result = graphql_crawler.crawl_month_batch(owner, repo, month, max_per_month)
                    return month, {
                        'month': month,
                        'issues': result.get('issues', []),
                        'prs': result.get('prs', []),
                        'commits': result.get('commits', []),
                        'releases': result.get('releases', [])
                    }
                except Exception as e:
                    print(f"  ⚠ 爬取 {month} 失败: {str(e)}")
                    return month, {
                        'month': month,
                        'issues': [],
                        'prs': [],
                        'commits': [],
                        'releases': []
                    }
            
            # 使用线程池并发爬取（最多5个并发）
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(crawl_single_month, month): month for month in months}
                
                completed = 0
                for future in as_completed(futures):
                    completed += 1
                    month, month_data = future.result()
                    monthly_data[month] = month_data
                    
                    if progress_callback:
                        progress = int((completed / total_months) * 100)
                        progress_callback(
                            completed - 1,
                            f'爬取 {month}',
                            f'已获取 {len(month_data["issues"])} Issues, {len(month_data["prs"])} PRs, {len(month_data["commits"])} Commits, {len(month_data["releases"])} Releases',
                            progress
                        )
                    print(f"  [{completed}/{total_months}] {month}: {len(month_data['issues'])} Issues, {len(month_data['prs'])} PRs, {len(month_data['commits'])} Commits, {len(month_data['releases'])} Releases")
        else:
            # 使用REST API（原始方法，串行）
            for idx, month in enumerate(months):
                if progress_callback:
                    progress = int((idx / total_months) * 100)
                    progress_callback(idx, f'爬取 {month}', f'正在爬取 {month} 的数据...', progress)
                
                print(f"\n[{idx+1}/{total_months}] 爬取 {month}...")
                
                month_data = {
                    'month': month,
                    'issues': [],
                    'prs': [],
                    'commits': [],
                    'releases': []
                }
                
                # 爬取Issues（轮换token）
                if len(self.tokens) > 1:
                    self.switch_token()
                print(f"  - Issues...")
                issues = self.crawl_issues_by_month(owner, repo, month, max_per_month)
                month_data['issues'] = issues
                print(f"    获取 {len(issues)} 个Issues")
                
                # 爬取PRs（轮换token）
                if len(self.tokens) > 1:
                    self.switch_token()
                print(f"  - PRs...")
                prs = self.crawl_prs_by_month(owner, repo, month, max_per_month)
                month_data['prs'] = prs
                print(f"    获取 {len(prs)} 个PRs")
                
                # 爬取Commits（轮换token）
                if len(self.tokens) > 1:
                    self.switch_token()
                print(f"  - Commits...")
                commits = self.crawl_commits_by_month(owner, repo, month, max_per_month)
                month_data['commits'] = commits
                print(f"    获取 {len(commits)} 个Commits")
                
                # 爬取Releases（轮换token）
                if len(self.tokens) > 1:
                    self.switch_token()
                print(f"  - Releases...")
                releases = self.crawl_releases_by_month(owner, repo, month)
                month_data['releases'] = releases
                print(f"    获取 {len(releases)} 个Releases")
                
                monthly_data[month] = month_data
                
                # 避免rate limit
                time.sleep(1)
        
        print(f"\n{'='*60}")
        print("按月爬取完成！")
        print(f"{'='*60}\n")
        
        return {
            'repo_info': repo_info,
            'monthly_data': monthly_data
        }

