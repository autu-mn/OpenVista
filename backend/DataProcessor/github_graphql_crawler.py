"""
使用GitHub GraphQL API批量爬取文本数据
支持并发请求，大幅提升速度
"""

import os
import requests
import json
import asyncio
import aiohttp
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

load_dotenv()


class GitHubGraphQLCrawler:
    """使用GraphQL API批量爬取GitHub数据"""
    
    def __init__(self):
        self.graphql_url = "https://api.github.com/graphql"
        
        # 支持多Token轮换（支持GITHUB_TOKEN和GITHUB_TOKEN_1到GITHUB_TOKEN_6）
        self.tokens = []
        self.current_token_index = 0
        self.rate_limit_retry_count = {}  # 记录每个token的rate limit重试次数
        
        # 加载主token
        token = os.getenv('GITHUB_TOKEN') or os.getenv('github_token')
        if token:
            self.tokens.append(token)
            self.rate_limit_retry_count[token] = 0
        
        # 加载GITHUB_TOKEN_1到GITHUB_TOKEN_6
        for i in range(1, 7):
            token_key = f'GITHUB_TOKEN_{i}'
            token_value = (os.getenv(token_key) or 
                          os.getenv(token_key.replace('GITHUB_TOKEN', 'GitHub_TOKEN')) or
                          os.getenv(token_key.lower()))
            if token_value:
                self.tokens.append(token_value)
                self.rate_limit_retry_count[token_value] = 0
        
        if not self.tokens:
            raise ValueError("未找到 GITHUB_TOKEN，请在 .env 文件中配置")
        
        self.token = self.tokens[0]
        self.headers = {
            'Authorization': f'bearer {self.token}',
            'Content-Type': 'application/json'
        }
    
    def switch_token(self):
        """切换到下一个Token"""
        if len(self.tokens) > 1:
            self.current_token_index = (self.current_token_index + 1) % len(self.tokens)
            self.token = self.tokens[self.current_token_index]
            self.headers['Authorization'] = f'bearer {self.token}'
    
    def _execute_query(self, query: str, variables: Dict = None) -> Optional[Dict]:
        """执行GraphQL查询"""
        payload = {'query': query}
        if variables:
            payload['variables'] = variables
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.graphql_url,
                    headers=self.headers,
                    json=payload,
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if 'errors' in data:
                        error_msgs = [err.get('message', str(err)) for err in data['errors']]
                        error_str = ', '.join(error_msgs)
                        print(f"  ⚠ GraphQL错误: {error_str}")
                        
                        # 检查是否是rate limit错误
                        if any('rate limit' in msg.lower() for msg in error_msgs):
                            # 记录当前token的rate limit次数
                            self.rate_limit_retry_count[self.token] = self.rate_limit_retry_count.get(self.token, 0) + 1
                            
                            # 检查是否所有token都超过了rate limit
                            all_tokens_exceeded = all(
                                self.rate_limit_retry_count.get(token, 0) > 0 
                                for token in self.tokens
                            )
                            
                            if all_tokens_exceeded and len(self.tokens) > 1:
                                # 所有token都超过limit，检查响应头中的重置时间
                                reset_time = None
                                if 'X-RateLimit-Reset' in response.headers:
                                    reset_time = int(response.headers['X-RateLimit-Reset'])
                                    current_time = int(time.time())
                                    wait_seconds = max(reset_time - current_time + 5, 60)  # 至少等待60秒，或等到重置时间+5秒缓冲
                                else:
                                    # 如果没有重置时间信息，等待1小时
                                    wait_seconds = 3600
                                
                                wait_minutes = wait_seconds // 60
                                print(f"  ⚠ 所有Token都超过Rate Limit，等待 {wait_minutes} 分钟（{wait_seconds}秒）后重试...")
                                # 每30秒输出一次进度
                                for remaining in range(wait_seconds, 0, -30):
                                    if remaining % 300 == 0 or remaining <= 60:  # 每5分钟或最后1分钟输出
                                        print(f"    剩余等待时间: {remaining // 60} 分钟")
                                    time.sleep(min(30, remaining))
                                
                                # 重置所有token的计数
                                for token in self.tokens:
                                    self.rate_limit_retry_count[token] = 0
                                # 切换到第一个token
                                self.current_token_index = 0
                                self.token = self.tokens[0]
                                self.headers['Authorization'] = f'bearer {self.token}'
                                print(f"  ✓ 等待完成，重置所有Token状态，继续重试...")
                                continue
                            elif len(self.tokens) > 1:
                                # 还有token可用，切换token
                                print(f"  → Token {self.current_token_index + 1} Rate Limit，切换Token...")
                                self.switch_token()
                                continue
                            else:
                                # 只有一个token，检查响应头中的重置时间
                                reset_time = None
                                try:
                                    if 'X-RateLimit-Reset' in response.headers:
                                        reset_time = int(response.headers['X-RateLimit-Reset'])
                                        current_time = int(time.time())
                                        wait_seconds = max(reset_time - current_time + 5, 60)  # 至少等待60秒
                                    else:
                                        wait_seconds = 3600  # 默认等待1小时
                                except:
                                    wait_seconds = 3600
                                
                                wait_minutes = wait_seconds // 60
                                print(f"  → Rate limit reached, waiting {wait_minutes} 分钟（{wait_seconds}秒）...")
                                # 每30秒输出一次进度
                                for remaining in range(wait_seconds, 0, -30):
                                    if remaining % 300 == 0 or remaining <= 60:
                                        print(f"    剩余等待时间: {remaining // 60} 分钟")
                                    time.sleep(min(30, remaining))
                                self.rate_limit_retry_count[self.token] = 0
                                print(f"  ✓ 等待完成，继续重试...")
                                continue
                        return None
                    return data.get('data')
                elif response.status_code == 403:
                    # 检查响应中的错误信息
                    try:
                        error_data = response.json()
                        if 'errors' in error_data:
                            error_msgs = [err.get('message', '') for err in error_data['errors']]
                            if any('rate limit' in msg.lower() for msg in error_msgs):
                                # 记录当前token的rate limit次数
                                self.rate_limit_retry_count[self.token] = self.rate_limit_retry_count.get(self.token, 0) + 1
                                
                                # 检查是否所有token都超过了rate limit
                                all_tokens_exceeded = all(
                                    self.rate_limit_retry_count.get(token, 0) > 0 
                                    for token in self.tokens
                                )
                                
                                if all_tokens_exceeded and len(self.tokens) > 1:
                                    # 所有token都超过limit，检查响应头中的重置时间
                                    reset_time = None
                                    try:
                                        if hasattr(response, 'headers') and 'X-RateLimit-Reset' in response.headers:
                                            reset_time = int(response.headers['X-RateLimit-Reset'])
                                            import time
                                            current_time = int(time.time())
                                            wait_seconds = max(reset_time - current_time + 5, 60)  # 至少等待60秒
                                        else:
                                            # 如果没有重置时间信息，等待1小时
                                            wait_seconds = 3600
                                    except:
                                        wait_seconds = 3600
                                    
                                    wait_minutes = wait_seconds // 60
                                    print(f"  ⚠ 所有Token都超过Rate Limit，等待 {wait_minutes} 分钟（{wait_seconds}秒）后重试...")
                                    import time
                                    # 每30秒输出一次进度
                                    for remaining in range(wait_seconds, 0, -30):
                                        if remaining % 300 == 0 or remaining <= 60:  # 每5分钟或最后1分钟输出
                                            print(f"    剩余等待时间: {remaining // 60} 分钟")
                                        time.sleep(min(30, remaining))
                                    
                                    # 重置所有token的计数
                                    for token in self.tokens:
                                        self.rate_limit_retry_count[token] = 0
                                    # 切换到第一个token
                                    self.current_token_index = 0
                                    self.token = self.tokens[0]
                                    self.headers['Authorization'] = f'bearer {self.token}'
                                    print(f"  ✓ 等待完成，重置所有Token状态，继续重试...")
                                    continue
                                elif len(self.tokens) > 1:
                                    # 还有token可用，切换token
                                    print(f"  ⚠ Token {self.current_token_index + 1} Rate Limit，切换Token...")
                                    self.switch_token()
                                    continue
                                else:
                                    # 只有一个token，等待60秒
                                    print(f"  ⚠ Rate limit reached, waiting 60s...")
                                    import time
                                    time.sleep(60)
                                    self.rate_limit_retry_count[self.token] = 0
                                    continue
                    except:
                        pass
                    # 其他403错误，尝试切换token
                    if len(self.tokens) > 1:
                        self.switch_token()
                        continue
                    return None
                else:
                    print(f"  ⚠ 请求失败: {response.status_code}")
                    return None
            except Exception as e:
                if attempt < max_retries - 1:
                    import time
                    time.sleep(2)
                    continue
                print(f"  ⚠ 请求异常: {str(e)}")
                return None
        
        return None
    
    def batch_fetch_issues(self, owner: str, repo: str, month: str, max_count: int = 3) -> List[Dict]:
        """
        批量获取指定月份的Issues（Top-3 热度，按评论数+反应数排序）
        month格式: 'YYYY-MM'
        """
        year, month_num = map(int, month.split('-'))
        start_date = datetime(year, month_num, 1, tzinfo=timezone.utc).isoformat()
        if month_num == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc).isoformat()
        else:
            end_date = datetime(year, month_num + 1, 1, tzinfo=timezone.utc).isoformat()
        
        # 添加请求延迟，控制速率
        time.sleep(0.2)
        
        query = """
        query($owner: String!, $repo: String!, $after: String) {
          repository(owner: $owner, name: $repo) {
            issues(
              first: 50
              after: $after
              orderBy: {field: COMMENTS, direction: DESC}
              states: [OPEN, CLOSED]
            ) {
              pageInfo {
                hasNextPage
                endCursor
              }
              nodes {
                number
                title
                body
                state
                createdAt
                updatedAt
                closedAt
                comments(first: 50) {
                  nodes {
                    body
                    author {
                      login
                    }
                    createdAt
                    reactions {
                      totalCount
                    }
                  }
                }
                reactions {
                  totalCount
                }
                __typename
                labels(first: 20) {
                  nodes {
                    name
                  }
                }
                author {
                  login
                }
                assignees(first: 10) {
                  nodes {
                    login
                  }
                }
              }
            }
          }
        }
        """
        
        all_issues = []
        cursor = None
        
        while len(all_issues) < max_count:
            variables = {
                'owner': owner,
                'repo': repo,
                'after': cursor
            }
            
            data = self._execute_query(query, variables)
            if not data:
                print(f"  ⚠ 获取issues失败: GraphQL查询返回空数据")
                break
            
            if not data.get('repository'):
                print(f"  ⚠ 获取issues失败: 仓库不存在或无权限")
                break
            
            repository_data = data.get('repository')
            if not repository_data or 'issues' not in repository_data:
                print(f"  ⚠ 获取issues失败: 响应格式错误")
                break
            
            issues = repository_data['issues']['nodes']
            page_info = repository_data['issues']['pageInfo']
            
            # 收集该月份的所有issues，计算热度分数
            month_issues = []
            for issue in issues:
                # 跳过PR（PR在GitHub中也是issue类型）
                if issue.get('__typename') == 'PullRequest':
                    continue
                
                updated_at = datetime.fromisoformat(issue['updatedAt'].replace('Z', '+00:00'))
                issue_start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                issue_end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                
                if issue_start <= updated_at < issue_end:
                    # 计算热度分数：评论数 + 反应数
                    comments_count = len(issue['comments']['nodes'])
                    reactions_count = issue['reactions']['totalCount']
                    heat_score = comments_count + reactions_count
                    
                    # 格式化数据
                    formatted_issue = {
                        'number': issue['number'],
                        'title': issue['title'],
                        'body': issue['body'] or '',
                        'state': issue['state'],
                        'created_at': issue['createdAt'],
                        'updated_at': issue['updatedAt'],
                        'closed_at': issue.get('closedAt'),
                        'comments_count': comments_count,
                        'reactions': {
                            'total_count': reactions_count,
                        },
                        'heat_score': heat_score,  # 热度分数
                        'labels': [label['name'] for label in issue['labels']['nodes']],
                        'user': issue['author']['login'] if issue['author'] else '',
                        'assignees': [assignee['login'] for assignee in issue['assignees']['nodes']],
                        'comments': [
                            {
                                'body': comment['body'],
                                'user': comment['author']['login'] if comment['author'] else '',
                                'created_at': comment['createdAt'],
                                'reactions': {
                                    'total_count': comment['reactions']['totalCount']
                                }
                            }
                            for comment in issue['comments']['nodes']
                        ]
                    }
                    month_issues.append(formatted_issue)
                elif updated_at < issue_start:
                    # 已经过了这个月份，停止收集
                    break
            
            # 按热度分数排序，取Top-N
            month_issues.sort(key=lambda x: x['heat_score'], reverse=True)
            all_issues.extend(month_issues[:max_count])
            
            if len(all_issues) >= max_count or not page_info['hasNextPage']:
                break
            
            cursor = page_info['endCursor']
        
        # 返回Top-3（按热度排序）
        return all_issues[:max_count]
    
    def batch_fetch_prs(self, owner: str, repo: str, month: str, max_count: int = 3) -> List[Dict]:
        """
        批量获取指定月份的PRs（包括评论和review comments）
        """
        year, month_num = map(int, month.split('-'))
        start_date = datetime(year, month_num, 1, tzinfo=timezone.utc).isoformat()
        if month_num == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc).isoformat()
        else:
            end_date = datetime(year, month_num + 1, 1, tzinfo=timezone.utc).isoformat()
        
        query = """
        query($owner: String!, $repo: String!, $after: String) {
          repository(owner: $owner, name: $repo) {
            pullRequests(
              first: 20
              after: $after
              orderBy: {field: UPDATED_AT, direction: DESC}
              states: [OPEN, CLOSED, MERGED]
            ) {
              pageInfo {
                hasNextPage
                endCursor
              }
              nodes {
                number
                title
                body
                state
                createdAt
                updatedAt
                closedAt
                mergedAt
                merged
                comments(first: 50) {
                  nodes {
                    body
                    author {
                      login
                    }
                    createdAt
                  }
                }
                reviewThreads(first: 20) {
                  nodes {
                    comments(first: 10) {
                      nodes {
                        body
                        author {
                          login
                        }
                        createdAt
                      }
                    }
                  }
                }
                reactions {
                  totalCount
                }
                labels(first: 20) {
                  nodes {
                    name
                  }
                }
                author {
                  login
                }
                assignees(first: 10) {
                  nodes {
                    login
                  }
                }
              }
            }
          }
        }
        """
        
        all_prs = []
        cursor = None
        
        while len(all_prs) < max_count:
            variables = {
                'owner': owner,
                'repo': repo,
                'after': cursor
            }
            
            data = self._execute_query(query, variables)
            if not data or not data.get('repository'):
                break
            
            prs = data['repository']['pullRequests']['nodes']
            page_info = data['repository']['pullRequests']['pageInfo']
            
            for pr in prs:
                updated_at = datetime.fromisoformat(pr['updatedAt'].replace('Z', '+00:00'))
                pr_start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                pr_end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                
                if pr_start <= updated_at < pr_end:
                    # 合并所有评论
                    all_comments = []
                    for comment in pr['comments']['nodes']:
                        all_comments.append({
                            'body': comment['body'],
                            'user': comment['author']['login'] if comment['author'] else '',
                            'created_at': comment['createdAt'],
                            'type': 'comment'
                        })
                    
                    for thread in pr['reviewThreads']['nodes']:
                        for review_comment in thread['comments']['nodes']:
                            all_comments.append({
                                'body': review_comment['body'],
                                'user': review_comment['author']['login'] if review_comment['author'] else '',
                                'created_at': review_comment['createdAt'],
                                'type': 'review_comment'
                            })
                    
                    formatted_pr = {
                        'number': pr['number'],
                        'title': pr['title'],
                        'body': pr['body'] or '',
                        'state': pr['state'],
                        'merged': pr['merged'],
                        'created_at': pr['createdAt'],
                        'updated_at': pr['updatedAt'],
                        'closed_at': pr.get('closedAt'),
                        'merged_at': pr.get('mergedAt'),
                        'comments_count': len(all_comments),
                        'reactions': {
                            'total_count': pr['reactions']['totalCount']
                        },
                        'labels': [label['name'] for label in pr['labels']['nodes']],
                        'user': pr['author']['login'] if pr['author'] else '',
                        'assignees': [assignee['login'] for assignee in pr['assignees']['nodes']],
                        'comments': all_comments
                    }
                    all_prs.append(formatted_pr)
                    
                    if len(all_prs) >= max_count:
                        break
                elif updated_at < pr_start:
                    return all_prs
            
            if not page_info['hasNextPage'] or len(all_prs) >= max_count:
                break
            
            cursor = page_info['endCursor']
        
        return all_prs[:max_count]
    
    def batch_fetch_commits(self, owner: str, repo: str, month: str, max_count: int = 3) -> List[Dict]:
        """
        批量获取指定月份的Commits（只保留文本信息，减少字段）
        """
        year, month_num = map(int, month.split('-'))
        start_date = datetime(year, month_num, 1, tzinfo=timezone.utc).isoformat()
        if month_num == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc).isoformat()
        else:
            end_date = datetime(year, month_num + 1, 1, tzinfo=timezone.utc).isoformat()
        
        # 添加请求延迟，控制速率
        time.sleep(0.2)
        
        query = """
        query($owner: String!, $repo: String!, $after: String) {
          repository(owner: $owner, name: $repo) {
            defaultBranchRef {
              target {
                ... on Commit {
                  history(first: 20, after: $after) {
                    pageInfo {
                      hasNextPage
                      endCursor
                    }
                    nodes {
                      oid
                      message
                      author {
                        name
                        date
                      }
                      committedDate
                    }
                  }
                }
              }
            }
          }
        }
        """
        
        all_commits = []
        cursor = None
        
        while len(all_commits) < max_count:
            variables = {
                'owner': owner,
                'repo': repo,
                'after': cursor
            }
            
            data = self._execute_query(query, variables)
            if not data or not data.get('repository') or not data['repository'].get('defaultBranchRef'):
                break
            
            history = data['repository']['defaultBranchRef']['target']['history']
            commits = history['nodes']
            page_info = history['pageInfo']
            
            for commit in commits:
                committed_date = datetime.fromisoformat(commit['committedDate'].replace('Z', '+00:00'))
                commit_start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                commit_end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                
                if commit_start <= committed_date < commit_end:
                    # 只保留文本信息，减少字段
                    formatted_commit = {
                        'sha': commit['oid'],
                        'message': commit['message'],  # 提交信息文本
                        'author': {
                            'name': commit['author']['name'] if commit['author'] else '',  # 作者名字文本
                        },
                        'committed_at': commit['committedDate']
                    }
                    all_commits.append(formatted_commit)
                    
                    if len(all_commits) >= max_count:
                        break
                elif committed_date < commit_start:
                    return all_commits
            
            if not page_info['hasNextPage'] or len(all_commits) >= max_count:
                break
            
            cursor = page_info['endCursor']
        
        return all_commits[:max_count]
    
    def batch_fetch_releases(self, owner: str, repo: str, month: str, max_count: int = 3) -> List[Dict]:
        """
        批量获取指定月份的Releases
        添加速率控制：每次请求延迟0.2秒
        """
        year, month_num = map(int, month.split('-'))
        start_date = datetime(year, month_num, 1, tzinfo=timezone.utc).isoformat()
        if month_num == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc).isoformat()
        else:
            end_date = datetime(year, month_num + 1, 1, tzinfo=timezone.utc).isoformat()
        
        # 添加请求延迟，控制速率
        time.sleep(0.2)
        
        query = """
        query($owner: String!, $repo: String!, $after: String) {
          repository(owner: $owner, name: $repo) {
            releases(first: 20, after: $after, orderBy: {field: CREATED_AT, direction: DESC}) {
              pageInfo {
                hasNextPage
                endCursor
              }
              nodes {
                tagName
                name
                description
                descriptionHTML
                createdAt
                publishedAt
                author {
                  login
                }
                url
              }
            }
          }
        }
        """
        
        all_releases = []
        cursor = None
        
        while len(all_releases) < max_count:
            variables = {
                'owner': owner,
                'repo': repo,
                'after': cursor
            }
            
            data = self._execute_query(query, variables)
            if not data or not data.get('repository'):
                break
            
            releases = data['repository']['releases']['nodes']
            page_info = data['repository']['releases']['pageInfo']
            
            for release in releases:
                published_at = datetime.fromisoformat(release['publishedAt'].replace('Z', '+00:00'))
                release_start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                release_end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                
                if release_start <= published_at < release_end:
                    # Release类型使用description而不是body
                    release_body = release.get('description') or release.get('descriptionHTML') or ''
                    formatted_release = {
                        'tag_name': release['tagName'],
                        'name': release['name'],
                        'body': release_body,
                        'created_at': release['createdAt'],
                        'published_at': release['publishedAt'],
                        'author': release['author']['login'] if release['author'] else '',
                        'url': release['url']
                    }
                    all_releases.append(formatted_release)
                    
                    if len(all_releases) >= max_count:
                        break
                elif published_at < release_start:
                    return all_releases
            
            if not page_info['hasNextPage'] or len(all_releases) >= max_count:
                break
            
            cursor = page_info['endCursor']
        
        return all_releases[:max_count]
    
    def crawl_month_batch(self, owner: str, repo: str, month: str, max_per_month: int = 3) -> Dict:
        """
        批量爬取指定月份的数据（Issues Top-3热度、Commits文本、Releases）
        已移除 PR 爬取以节省 API 配额
        添加速率控制：每次请求延迟0.2秒
        """
        # 串行执行，每次请求后延迟0.2秒
        results = {
            'issues': [],
            'prs': [],  # 不再爬取，返回空列表
            'commits': [],
            'releases': []
        }
        
        # 爬取 Issues（Top-3 热度）
        try:
            results['issues'] = self.batch_fetch_issues(owner, repo, month, max_per_month)
        except Exception as e:
            print(f"  ⚠ 爬取 {month} Issues 失败: {str(e)}")
            results['issues'] = []
        
        # 爬取 Commits（只保留文本信息）
        try:
            results['commits'] = self.batch_fetch_commits(owner, repo, month, max_per_month)
        except Exception as e:
            print(f"  ⚠ 爬取 {month} Commits 失败: {str(e)}")
            results['commits'] = []
        
        # 爬取 Releases
        try:
            results['releases'] = self.batch_fetch_releases(owner, repo, month, max_per_month)
        except Exception as e:
            print(f"  ⚠ 爬取 {month} Releases 失败: {str(e)}")
            results['releases'] = []
        
        return results

