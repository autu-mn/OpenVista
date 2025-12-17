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
from datetime import datetime, timedelta, timezone
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
        
        # 检查多种可能的token名称（大小写兼容，支持GITHUB_TOKEN和GITHUB_TOKEN_1到GITHUB_TOKEN_6）
        # 加载主token
        token = os.getenv('GITHUB_TOKEN') or os.getenv('github_token')
        if token:
            self.tokens.append(token)
        
        # 加载GITHUB_TOKEN_1到GITHUB_TOKEN_6
        for i in range(1, 7):
            token_key = f'GITHUB_TOKEN_{i}'
            token_value = (os.getenv(token_key) or 
                          os.getenv(token_key.replace('GITHUB_TOKEN', 'GitHub_TOKEN')) or
                          os.getenv(token_key.lower()))
            if token_value:
                self.tokens.append(token_value)
        
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
    
    def crawl_issues_by_month(self, owner: str, repo: str, month: str, max_per_month: int = 50) -> List[Dict]:
        """
        按月份爬取Issues（Top-3热度，按评论数+反应数排序）
        month格式: 'YYYY-MM'
        使用 GitHub Search API 精确获取该月份创建的 issues
        """
        year, month_num = map(int, month.split('-'))
        start_date = datetime(year, month_num, 1, tzinfo=timezone.utc)
        if month_num == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_date = datetime(year, month_num + 1, 1, tzinfo=timezone.utc)
        
        # 使用 GitHub Search API 精确搜索该月份创建的 issues
        # 格式: created:2020-08-01..2020-08-31
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = (end_date - timedelta(days=1)).strftime('%Y-%m-%d')
        
        url = f"{self.base_url}/search/issues"
        params = {
            'q': f'repo:{owner}/{repo} is:issue created:{start_str}..{end_str}',
            'sort': 'comments',  # 按评论数排序（热度）
            'order': 'desc',
            'per_page': min(max_per_month * 5, 30)  # 获取足够多再筛选
        }
        
        response = self._safe_request(url, params)
        if not response:
            return []
        
        data = response.json()
        items = data.get('items', [])
        
        if not items:
            return []
        
        month_issues = []
        for issue in items:
            comments_count = issue.get('comments', 0)
            reactions_count = issue.get('reactions', {}).get('total_count', 0)
            heat_score = comments_count + reactions_count
            
            issue_detail = {
                'number': issue['number'],
                'title': issue.get('title', ''),
                'body': issue.get('body', '') or '',
                'state': issue.get('state', ''),
                'created_at': issue['created_at'],
                'updated_at': issue['updated_at'],
                'closed_at': issue.get('closed_at'),
                'comments_count': comments_count,
                'reactions': {
                    'total_count': reactions_count,
                },
                'labels': [l['name'] for l in issue.get('labels', [])],
                'user': issue.get('user', {}).get('login', ''),
                'heat_score': heat_score
            }
            month_issues.append(issue_detail)
        
        # 按热度分数排序，取Top-N
        month_issues.sort(key=lambda x: x.get('heat_score', 0), reverse=True)
        return month_issues[:max_per_month]
    
    def _get_issue_detail(self, owner: str, repo: str, issue_number: int) -> Optional[Dict]:
        """获取Issue详细内容（包括评论）
        添加速率控制：每次请求延迟0.2秒
        """
        # 添加请求延迟，控制速率
        time.sleep(0.2)
        
        url = f"{self.base_url}/repos/{owner}/{repo}/issues/{issue_number}"
        response = self._safe_request(url)
        if not response:
            return None
        
        issue = response.json()
        
        # 获取评论（限制数量以节省API配额）
        comments = []
        comments_url = issue.get('comments_url')
        if comments_url and issue.get('comments', 0) > 0:
            # 添加延迟
            time.sleep(0.2)
            comments_response = self._safe_request(comments_url, {'per_page': 30})  # 减少到30条
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
                    for c in comments_data[:30]  # 最多30条评论
                ]
        
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
            time.sleep(0.05)
        
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
            time.sleep(0.05)
        
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
            time.sleep(0.05)
        
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
    
    def crawl_commits_by_month(self, owner: str, repo: str, month: str, max_per_month: int = 50) -> List[Dict]:
        """
        按月份爬取Commits（只保留文本信息：message和author name）
        month格式: 'YYYY-MM'
        使用 since/until 参数直接限制时间范围，避免遍历全部历史
        """
        
        year, month_num = map(int, month.split('-'))
        start_date = datetime(year, month_num, 1, tzinfo=timezone.utc)
        if month_num == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_date = datetime(year, month_num + 1, 1, tzinfo=timezone.utc)
        
        commits = []
        
        # 使用 since/until 参数直接限制时间范围（关键优化！）
        url = f"{self.base_url}/repos/{owner}/{repo}/commits"
        params = {
            'per_page': max_per_month,  # 只请求需要的数量
            'since': start_date.isoformat(),
            'until': end_date.isoformat()
        }
        
        response = self._safe_request(url, params)
        if not response:
            return commits
        
        data = response.json()
        if not data:
            return commits
        
        for commit in data[:max_per_month]:
            commit_data = commit.get('commit', {})
            commit_detail = {
                'sha': commit.get('sha', ''),
                'message': commit_data.get('message', ''),  # 提交信息文本
                'author': {
                    'name': commit_data.get('author', {}).get('name', '') if commit_data.get('author') else ''
                },
                'committed_at': commit_data.get('author', {}).get('date', '') if commit_data.get('author') else ''
            }
            commits.append(commit_detail)
        
        return commits
    
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
        限制最多爬取10页，避免卡住
        
        注意：有些仓库（如 odoo/odoo）使用 Tags 而非 Releases，
        如果 Releases 为空，则尝试从 Tags 获取版本信息
        """
        
        year, month_num = map(int, month.split('-'))
        start_date = datetime(year, month_num, 1, tzinfo=timezone.utc)
        if month_num == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_date = datetime(year, month_num + 1, 1, tzinfo=timezone.utc)
        
        releases = []
        page = 1
        max_pages = 10  # 限制最多10页
        
        while page <= max_pages:
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
                    # 尝试使用 created_at
                    published_at = release.get('created_at')
                if not published_at:
                    continue
                
                try:
                    pub_date = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                except:
                    continue
                
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
                    # 已经过了目标月份，停止
                    break
            
            page += 1
        
        # 如果没有找到 Releases，尝试获取 Tags（某些项目只使用 Tags）
        if not releases:
            releases = self._crawl_tags_by_month(owner, repo, month, start_date, end_date)
        
        return releases
    
    def _crawl_tags_by_month(self, owner: str, repo: str, month: str, 
                             start_date: datetime, end_date: datetime) -> List[Dict]:
        """
        从 Tags 获取版本信息（作为 Releases 的备选）
        """
        tags = []
        page = 1
        max_pages = 5
        
        while page <= max_pages:
            url = f"{self.base_url}/repos/{owner}/{repo}/tags"
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
            
            for tag in data:
                # Tags 没有直接的时间信息，需要通过 commit 获取
                commit_url = tag.get('commit', {}).get('url')
                if commit_url:
                    commit_response = self._safe_request(commit_url)
                    if commit_response:
                        commit_data = commit_response.json()
                        commit_date_str = commit_data.get('commit', {}).get('committer', {}).get('date')
                        if commit_date_str:
                            try:
                                commit_date = datetime.fromisoformat(commit_date_str.replace('Z', '+00:00'))
                                if start_date <= commit_date < end_date:
                                    tags.append({
                                        'tag_name': tag.get('name', ''),
                                        'name': tag.get('name', ''),
                                        'body': '',  # Tags 没有 body
                                        'created_at': commit_date_str,
                                        'published_at': commit_date_str,
                                        'author': commit_data.get('commit', {}).get('author', {}).get('name', ''),
                                        'url': f"https://github.com/{owner}/{repo}/releases/tag/{tag.get('name', '')}",
                                        'prerelease': False,
                                        'draft': False,
                                        'is_tag': True  # 标记这是从 Tag 获取的
                                    })
                                elif commit_date < start_date:
                                    # 已经过了目标月份
                                    return tags
                            except:
                                pass
            
            page += 1
        
        return tags
    
    def crawl_discussions_by_month(self, owner: str, repo: str, month: str, max_per_month: int = 3) -> List[Dict]:
        """
        爬取 GitHub Discussions（社区讨论，有价值的时序文本）
        使用 GraphQL API，因为 REST API 不支持 Discussions
        month格式: 'YYYY-MM'
        """
        from datetime import timezone
        
        year, month_num = map(int, month.split('-'))
        start_date = datetime(year, month_num, 1, tzinfo=timezone.utc)
        if month_num == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_date = datetime(year, month_num + 1, 1, tzinfo=timezone.utc)
        
        # Discussions 需要使用 GraphQL API
        graphql_url = "https://api.github.com/graphql"
        query = """
        query($owner: String!, $repo: String!, $first: Int!, $after: String) {
          repository(owner: $owner, name: $repo) {
            discussions(first: $first, after: $after, orderBy: {field: CREATED_AT, direction: DESC}) {
              pageInfo {
                hasNextPage
                endCursor
              }
              nodes {
                number
                title
                body
                createdAt
                updatedAt
                author {
                  login
                }
                category {
                  name
                }
                comments(first: 5) {
                  totalCount
                  nodes {
                    body
                    author {
                      login
                    }
                    createdAt
                  }
                }
                upvoteCount
                answerChosenAt
              }
            }
          }
        }
        """
        
        discussions = []
        cursor = None
        
        try:
            while len(discussions) < max_per_month:
                variables = {
                    "owner": owner,
                    "repo": repo,
                    "first": 20,
                    "after": cursor
                }
                
                response = requests.post(
                    graphql_url,
                    headers=self.headers,
                    json={"query": query, "variables": variables},
                    timeout=30
                )
                
                if response.status_code != 200:
                    break
                
                data = response.json()
                if 'errors' in data:
                    # 仓库可能没有启用 Discussions
                    break
                
                repo_data = data.get('data', {}).get('repository')
                if not repo_data or not repo_data.get('discussions'):
                    break
                
                disc_data = repo_data['discussions']
                nodes = disc_data.get('nodes', [])
                
                if not nodes:
                    break
                
                found_in_range = False
                for disc in nodes:
                    created_at = datetime.fromisoformat(disc['createdAt'].replace('Z', '+00:00'))
                    
                    if start_date <= created_at < end_date:
                        found_in_range = True
                        discussions.append({
                            'number': disc['number'],
                            'title': disc['title'],
                            'body': disc.get('body', '') or '',
                            'created_at': disc['createdAt'],
                            'updated_at': disc.get('updatedAt', ''),
                            'author': disc.get('author', {}).get('login', '') if disc.get('author') else '',
                            'category': disc.get('category', {}).get('name', '') if disc.get('category') else '',
                            'comments_count': disc.get('comments', {}).get('totalCount', 0),
                            'upvotes': disc.get('upvoteCount', 0),
                            'is_answered': disc.get('answerChosenAt') is not None,
                            'top_comments': [
                                {
                                    'body': c.get('body', ''),
                                    'author': c.get('author', {}).get('login', '') if c.get('author') else '',
                                    'created_at': c.get('createdAt', '')
                                }
                                for c in disc.get('comments', {}).get('nodes', [])[:3]
                            ]
                        })
                        
                        if len(discussions) >= max_per_month:
                            break
                    elif created_at < start_date:
                        # 已经过了目标月份
                        return discussions
                
                if not found_in_range or not disc_data.get('pageInfo', {}).get('hasNextPage'):
                    break
                
                cursor = disc_data['pageInfo']['endCursor']
        
        except Exception as e:
            # Discussions 可能未启用，静默失败
            pass
        
        return discussions[:max_per_month]
    
    def crawl_events_by_month(self, owner: str, repo: str, month: str, max_per_month: int = 10) -> List[Dict]:
        """
        爬取仓库事件（push、create、fork 等活动）
        这些事件反映了项目的实际活动情况
        month格式: 'YYYY-MM'
        注意：GitHub Events API 只保留最近 90 天的事件
        """
        from datetime import timezone
        
        year, month_num = map(int, month.split('-'))
        start_date = datetime(year, month_num, 1, tzinfo=timezone.utc)
        if month_num == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_date = datetime(year, month_num + 1, 1, tzinfo=timezone.utc)
        
        # 检查是否在90天内
        now = datetime.now(timezone.utc)
        if (now - start_date).days > 90:
            # 超过90天，Events API 无法获取
            return []
        
        events = []
        page = 1
        max_pages = 3
        
        while page <= max_pages and len(events) < max_per_month:
            url = f"{self.base_url}/repos/{owner}/{repo}/events"
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
            
            for event in data:
                created_at = datetime.fromisoformat(event['created_at'].replace('Z', '+00:00'))
                
                if start_date <= created_at < end_date:
                    event_type = event.get('type', '')
                    payload = event.get('payload', {})
                    
                    # 提取有意义的事件信息
                    event_detail = {
                        'type': event_type,
                        'created_at': event['created_at'],
                        'actor': event.get('actor', {}).get('login', ''),
                    }
                    
                    # 根据事件类型提取详细信息
                    if event_type == 'PushEvent':
                        commits = payload.get('commits', [])
                        event_detail['commits_count'] = len(commits)
                        event_detail['commits'] = [
                            {'message': c.get('message', ''), 'sha': c.get('sha', '')[:7]}
                            for c in commits[:3]
                        ]
                    elif event_type == 'IssuesEvent':
                        event_detail['action'] = payload.get('action', '')
                        event_detail['issue_title'] = payload.get('issue', {}).get('title', '')
                        event_detail['issue_number'] = payload.get('issue', {}).get('number', 0)
                    elif event_type == 'IssueCommentEvent':
                        event_detail['action'] = payload.get('action', '')
                        event_detail['issue_title'] = payload.get('issue', {}).get('title', '')
                        event_detail['comment_body'] = payload.get('comment', {}).get('body', '')[:200]
                    elif event_type == 'PullRequestEvent':
                        event_detail['action'] = payload.get('action', '')
                        event_detail['pr_title'] = payload.get('pull_request', {}).get('title', '')
                        event_detail['pr_number'] = payload.get('pull_request', {}).get('number', 0)
                    elif event_type == 'CreateEvent':
                        event_detail['ref_type'] = payload.get('ref_type', '')
                        event_detail['ref'] = payload.get('ref', '')
                    elif event_type == 'ReleaseEvent':
                        event_detail['action'] = payload.get('action', '')
                        event_detail['release_name'] = payload.get('release', {}).get('name', '')
                        event_detail['tag_name'] = payload.get('release', {}).get('tag_name', '')
                    elif event_type == 'ForkEvent':
                        event_detail['forkee'] = payload.get('forkee', {}).get('full_name', '')
                    elif event_type == 'WatchEvent':
                        event_detail['action'] = payload.get('action', '')
                    
                    events.append(event_detail)
                    
                    if len(events) >= max_per_month:
                        break
                elif created_at < start_date:
                    return events
            
            page += 1
        
        return events
    
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
    
    def crawl_all_months(self, owner: str, repo: str, max_per_month: int = 50, progress_callback=None, use_graphql: bool = False) -> Dict:
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
            # 使用GraphQL API批量爬取（不推荐，经常502错误）
            from .github_graphql_crawler import GitHubGraphQLCrawler
            graphql_crawler = GitHubGraphQLCrawler()
            print(f"  [INFO] 使用 GraphQL API（不推荐，可能不稳定）")
            
            # 并发爬取所有月份（分批处理，避免过多并发）
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            def crawl_single_month(month: str) -> tuple:
                """爬取单个月份的数据（只爬取 Issues 和 Commits）"""
                try:
                    result = graphql_crawler.crawl_month_batch(owner, repo, month, max_per_month)
                    return month, {
                        'month': month,
                        'issues': result.get('issues', []),
                        'commits': result.get('commits', [])
                    }
                except Exception as e:
                    error_msg = str(e)
                    # 检查是否是GraphQL错误（502、503、或GraphQL相关错误）
                    if '502' in error_msg or '503' in error_msg or 'GraphQL' in error_msg or 'query' in error_msg.lower():
                        print(f"  ⚠ GraphQL API失败 ({month}): {error_msg[:100]}")
                        print(f"  → 回退到 REST API...")
                        try:
                            # 使用REST API回退
                            issues = self.crawl_issues_by_month(owner, repo, month, max_per_month)
                            commits = self.crawl_commits_by_month(owner, repo, month, max_per_month)
                            return month, {
                                'month': month,
                                'issues': issues,
                                'commits': commits
                            }
                        except Exception as rest_error:
                            print(f"  ⚠ REST API也失败 ({month}): {str(rest_error)[:100]}")
                            return month, {
                                'month': month,
                                'issues': [],
                                'commits': []
                            }
                    else:
                        # 其他错误，直接返回空数据
                        print(f"  ⚠ 爬取 {month} 失败: {error_msg[:100]}")
                        return month, {
                            'month': month,
                            'issues': [],
                            'commits': []
                        }
            
            # 使用线程池并发爬取（降低并发数到2以减少 rate limit）
            with ThreadPoolExecutor(max_workers=2) as executor:
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
                            f'Issues:{len(month_data.get("issues", []))} Commits:{len(month_data.get("commits", []))} Discussions:{len(month_data.get("discussions", []))}',
                            progress
                        )
                    print(f"  [{completed}/{total_months}] {month}: Issues:{len(month_data.get('issues', []))} Commits:{len(month_data.get('commits', []))}")
        else:
            # 使用REST API（默认，更稳定，串行执行）
            print(f"  [INFO] 使用 REST API（稳定可靠）")
            for idx, month in enumerate(months):
                if progress_callback:
                    progress = int((idx / total_months) * 100)
                    progress_callback(idx, f'爬取 {month}', f'正在爬取 {month} 的数据...', progress)
                
                print(f"\n[{idx+1}/{total_months}] 爬取 {month}...")
                
                month_data = {
                    'month': month,
                    'issues': [],
                    'commits': []
                }
                
                # 爬取Issues（按热度排序，轮换token）
                if len(self.tokens) > 1:
                    self.switch_token()
                print(f"  - Issues (最多{max_per_month}个)...")
                issues = self.crawl_issues_by_month(owner, repo, month, max_per_month)
                month_data['issues'] = issues
                print(f"    获取 {len(issues)} 个Issues")
                
                # 爬取Commits（只保留文本信息，轮换token）
                if len(self.tokens) > 1:
                    self.switch_token()
                print(f"  - Commits (最多{max_per_month}个)...")
                commits = self.crawl_commits_by_month(owner, repo, month, max_per_month)
                month_data['commits'] = commits
                print(f"    获取 {len(commits)} 个Commits")
                
                monthly_data[month] = month_data
        
        print(f"\n{'='*60}")
        print("按月爬取完成！")
        print(f"{'='*60}\n")
        
        return {
            'repo_info': repo_info,
            'monthly_data': monthly_data
        }

