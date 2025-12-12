"""
使用GitHub GraphQL API批量爬取文本数据
支持并发请求，大幅提升速度
"""

import os
import requests
import json
import asyncio
import aiohttp
from datetime import datetime, timezone
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

load_dotenv()


class GitHubGraphQLCrawler:
    """使用GraphQL API批量爬取GitHub数据"""
    
    def __init__(self):
        self.graphql_url = "https://api.github.com/graphql"
        
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
                        print(f"  ⚠ GraphQL错误: {data['errors']}")
                        return None
                    return data.get('data')
                elif response.status_code == 403:
                    if len(self.tokens) > 1:
                        self.switch_token()
                        continue
                    else:
                        print(f"  ⚠ Rate limit reached, waiting 60s...")
                        import time
                        time.sleep(60)
                        continue
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
        批量获取指定月份的Issues（包括评论）
        month格式: 'YYYY-MM'
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
            issues(
              first: 100
              after: $after
              orderBy: {field: UPDATED_AT, direction: DESC}
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
            if not data or not data.get('repository'):
                break
            
            issues = data['repository']['issues']['nodes']
            page_info = data['repository']['issues']['pageInfo']
            
            for issue in issues:
                # 跳过PR（PR在GitHub中也是issue类型）
                # 使用__typename判断，或者检查是否有pull_request相关的字段
                if issue.get('__typename') == 'PullRequest':
                    continue
                
                updated_at = datetime.fromisoformat(issue['updatedAt'].replace('Z', '+00:00'))
                issue_start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                issue_end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                
                if issue_start <= updated_at < issue_end:
                    # 格式化数据
                    formatted_issue = {
                        'number': issue['number'],
                        'title': issue['title'],
                        'body': issue['body'] or '',
                        'state': issue['state'],
                        'created_at': issue['createdAt'],
                        'updated_at': issue['updatedAt'],
                        'closed_at': issue.get('closedAt'),
                        'comments_count': len(issue['comments']['nodes']),
                        'reactions': {
                            'total_count': issue['reactions']['totalCount'],
                            'thumbs_up': 0,  # GraphQL API不直接提供thumbs_up计数
                        },
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
                    all_issues.append(formatted_issue)
                    
                    if len(all_issues) >= max_count:
                        break
                elif updated_at < issue_start:
                    # 已经过了这个月份，停止
                    return all_issues
            
            if not page_info['hasNextPage'] or len(all_issues) >= max_count:
                break
            
            cursor = page_info['endCursor']
        
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
              first: 100
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
        批量获取指定月份的Commits
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
            defaultBranchRef {
              target {
                ... on Commit {
                  history(first: 100, after: $after) {
                    pageInfo {
                      hasNextPage
                      endCursor
                    }
                    nodes {
                      oid
                      message
                      author {
                        name
                        email
                        date
                      }
                      committedDate
                      additions
                      deletions
                      changedFiles
                      url
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
                    formatted_commit = {
                        'sha': commit['oid'],
                        'message': commit['message'],
                        'author': {
                            'name': commit['author']['name'] if commit['author'] else '',
                            'email': commit['author']['email'] if commit['author'] else '',
                            'date': commit['author']['date'] if commit['author'] else commit['committedDate']
                        },
                        'committed_at': commit['committedDate'],
                        'additions': commit.get('additions', 0),
                        'deletions': commit.get('deletions', 0),
                        'changed_files': commit.get('changedFiles', 0),
                        'url': commit['url']
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
            releases(first: 100, after: $after, orderBy: {field: CREATED_AT, direction: DESC}) {
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
        批量爬取指定月份的所有数据（Issues、PRs、Commits、Releases）
        使用并发请求提升速度
        """
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                'issues': executor.submit(self.batch_fetch_issues, owner, repo, month, max_per_month),
                'prs': executor.submit(self.batch_fetch_prs, owner, repo, month, max_per_month),
                'commits': executor.submit(self.batch_fetch_commits, owner, repo, month, max_per_month),
                'releases': executor.submit(self.batch_fetch_releases, owner, repo, month, max_per_month)
            }
            
            results = {}
            for key, future in futures.items():
                try:
                    results[key] = future.result(timeout=60)
                except Exception as e:
                    print(f"  ⚠ 获取{key}失败: {str(e)}")
                    results[key] = []
        
        return results

