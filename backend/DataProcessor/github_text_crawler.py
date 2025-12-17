import os
import requests
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import time
import json
import re
import base64
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed

load_dotenv()


class OpenDiggerMetrics:
    def __init__(self):
        self.base_url = "https://oss.open-digger.cn/github/"
        self.max_retries = 3
        self.timeout = 20
    
    def _fetch_single_metric(self, owner, repo, metric_key, metric_name):
        """获取单个指标（带重试机制）"""
        url = f"{self.base_url}{owner}/{repo}/{metric_key}.json"
        
        for attempt in range(self.max_retries):
            try:
                response = requests.get(url, timeout=self.timeout)
                if response.status_code == 200:
                    data = response.json()
                    if data:
                        # 只保留月度数据（YYYY-MM 格式）
                        monthly_data = {k: v for k, v in data.items() if '-' in k and len(k) == 7}
                        if monthly_data:
                            return {'success': True, 'name': metric_name, 'data': monthly_data}
                    return {'success': False, 'name': metric_name, 'error': '数据为空'}
                elif response.status_code == 404:
                    return {'success': False, 'name': metric_name, 'error': '404 仓库无此指标'}
                else:
                    if attempt < self.max_retries - 1:
                        time.sleep(0.2)  # 重试前等待
                        continue
                    return {'success': False, 'name': metric_name, 'error': f'HTTP {response.status_code}'}
            except requests.exceptions.Timeout:
                if attempt < self.max_retries - 1:
                    time.sleep(0.2)
                    continue
                return {'success': False, 'name': metric_name, 'error': '超时'}
            except requests.exceptions.ConnectionError:
                if attempt < self.max_retries - 1:
                    time.sleep(2)  # 连接错误等待更长
                    continue
                return {'success': False, 'name': metric_name, 'error': '连接错误'}
            except Exception as e:
                return {'success': False, 'name': metric_name, 'error': str(e)[:50]}
        
        return {'success': False, 'name': metric_name, 'error': '重试次数耗尽'}
    
    def get_metrics(self, owner, repo):
        """获取 OpenDigger 指标数据（使用并发请求和重试机制）"""
        metrics_config = {
            # OpenRank
            'openrank': 'OpenRank',
            
            # 统计指标
            'activity': '活跃度',
            'stars': 'Star数',
            'technical_fork': 'Fork数',
            'attention': '关注度',
            'participants': '参与者数',
            
            # 开发者相关
            'new_contributors': '新增贡献者',
            'contributors': '贡献者',
            'inactive_contributors': '不活跃贡献者',
            'bus_factor': '总线因子',
            
            # Issue 相关
            'issues_new': '新增Issue',
            'issues_closed': '关闭Issue',
            'issue_comments': 'Issue评论',
            
            # PR (变更请求) 相关
            'change_requests': '变更请求',
            'change_requests_accepted': 'PR接受数',
            'change_requests_reviews': 'PR审查',
            
            # 代码更改相关
            'code_change_lines_add': '代码新增行数',
            'code_change_lines_remove': '代码删除行数',
            'code_change_lines_sum': '代码变更总行数',
        }
        
        result = {}
        missing_metrics = []
        error_details = []
        
        print(f"    正在获取 {len(metrics_config)} 个 OpenDigger 指标...")
        
        # 使用并发请求提高速度
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(self._fetch_single_metric, owner, repo, key, name): name
                for key, name in metrics_config.items()
            }
            
            completed = 0
            for future in as_completed(futures):
                completed += 1
                res = future.result()
                if res['success']:
                    result[res['name']] = res['data']
                else:
                    missing_metrics.append(res['name'])
                    if res['error'] not in ['404 仓库无此指标', '数据为空']:
                        error_details.append(f"{res['name']}: {res['error']}")
        
        # 打印进度信息
        success_count = len(result)
        if success_count > 0:
            print(f"    ✓ 成功获取 {success_count}/{len(metrics_config)} 个指标")
            # 显示数据范围
            sample_metric = next(iter(result.values())) if result else {}
            if sample_metric:
                months = sorted(sample_metric.keys())
                if months:
                    print(f"    ✓ 数据范围: {months[0]} ~ {months[-1]} ({len(months)} 个月)")
        else:
            print(f"    ⚠ 未能获取任何 OpenDigger 指标!")
        
        if error_details:
            print(f"    ⚠ 错误详情: {', '.join(error_details[:3])}{'...' if len(error_details) > 3 else ''}")
        
        return result, missing_metrics


class GitHubTextCrawler:
    def __init__(self):
        self.tokens = []
        self.current_token_index = 0
        
        # 支持不同大小写的token名称（支持GITHUB_TOKEN和GITHUB_TOKEN_1到GITHUB_TOKEN_6）
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
        self.base_url = 'https://api.github.com'
        self.rate_limit_remaining = 5000
    
    def switch_token(self):
        if len(self.tokens) > 1:
            self.current_token_index = (self.current_token_index + 1) % len(self.tokens)
            self.token = self.tokens[self.current_token_index]
            self.headers['Authorization'] = f'token {self.token}'
    
    def check_rate_limit(self):
        url = f"{self.base_url}/rate_limit"
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                data = response.json()
                remaining = data['resources']['core']['remaining']
                self.rate_limit_remaining = remaining
                if remaining < 100:
                    print(f"警告: GitHub API 剩余请求数: {remaining}")
        except:
            pass
    
    def safe_request(self, url, params=None, max_retries=3):
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=self.headers, params=params, timeout=15)
                if response.status_code == 200:
                    return response
                elif response.status_code == 403:
                    if attempt < max_retries - 1:
                        self.switch_token()
                        time.sleep(2)
                        continue
                return response
            except requests.exceptions.SSLError as e:
                if attempt < max_retries - 1:
                    print(f"SSL错误，重试中 ({attempt + 1}/{max_retries})...")
                    time.sleep(2)
                    continue
                print(f"SSL错误，跳过: {str(e)}")
                return None
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(0.2)
                    continue
                print(f"请求失败: {str(e)}")
                return None
        return None
    
    def safe_get_content(self, url, max_retries=3):
        for attempt in range(max_retries):
            try:
                response = requests.get(url, timeout=15, verify=True)
                if response.status_code == 200:
                    return response.text
            except requests.exceptions.SSLError as e:
                if attempt < max_retries - 1:
                    print(f"SSL错误，重试中 ({attempt + 1}/{max_retries})...")
                    time.sleep(2)
                    continue
                print(f"SSL错误，跳过: {str(e)}")
                return None
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(0.2)
                    continue
                print(f"获取内容失败: {str(e)}")
                return None
        return None
    
    def get_repo_info(self, owner, repo):
        url = f"{self.base_url}/repos/{owner}/{repo}"
        response = self.safe_request(url)
        if not response:
            return None
        
        if response.status_code == 200:
            data = response.json()
            return {
                'name': data['name'],
                'full_name': data['full_name'],
                'description': data.get('description', ''),
                'homepage': data.get('homepage', ''),
                'language': data.get('language', ''),
                'stars': data['stargazers_count'],
                'forks': data['forks_count'],
                'watchers': data['watchers_count'],
                'open_issues': data['open_issues_count'],
                'created_at': data['created_at'],
                'updated_at': data['updated_at'],
                'license': data.get('license', {}).get('name', '') if data.get('license') else '',
                'topics': data.get('topics', [])
            }
            return None
    
    def get_readme(self, owner, repo):
        """获取 README 文件（包括英文版和中文版，尽可能获取所有语言版本）"""
        readmes = []
        found_names = set()  # 避免重复
        
        # 尝试获取默认 README（通常是英文）
        url = f"{self.base_url}/repos/{owner}/{repo}/readme"
        try:
            response = self.safe_request(url)
            if response and response.status_code == 200:
                data = response.json()
                content_url = data.get('download_url')
                if content_url:
                    content = self.safe_get_content(content_url)
                    if content:
                        readmes.append({
                            'name': data['name'],
                            'path': data['path'],
                            'size': data['size'],
                            'content': content,
                            'language': 'english'
                        })
                        found_names.add(data['name'].lower())
                        print(f"    - {data['name']} (英文/默认)")
                    else:
                        print(f"    ⚠ README下载失败: {content_url}")
                else:
                    print(f"    ⚠ README没有download_url")
            elif response:
                print(f"    ⚠ README请求失败: HTTP {response.status_code}")
            else:
                print(f"    ⚠ README请求失败: 无响应")
        except Exception as e:
            print(f"    ⚠ 获取README异常: {str(e)}")
        
        # 尝试获取所有语言版本的 README（不只是中文）
        multilang_readme_names = [
            # 中文版（根目录）
            'README-cn.md', 'README-CN.md', 'README_CN.md', 'README_cn.md',
            'README-zh.md', 'README-ZH.md', 'README_ZH.md', 'README_zh.md',
            'README-zh-CN.md', 'README_zh_CN.md', 'README-zh-Hans.md',
            'README.zh.md', 'README.zh-CN.md', 'README.zh-Hans.md',
            'README中文.md', 'README.Chinese.md', 'README_Chinese.md',
            # 中文版（docs 目录）
            'docs/README-cn.md', 'docs/README-CN.md', 'docs/README_CN.md',
            'docs/README-zh.md', 'docs/README-ZH.md', 'docs/README_zh.md',
            'docs/README.zh.md', 'docs/README.zh-CN.md',
            # 日文版
            'README-ja.md', 'README_ja.md', 'README.ja.md',
            # 韩文版
            'README-ko.md', 'README_ko.md', 'README.ko.md',
            # 其他语言
            'README-es.md', 'README-fr.md', 'README-de.md', 'README-pt.md',
            # i18n 目录
            'i18n/README-zh.md', 'i18n/README-cn.md', 'i18n/README.zh-CN.md',
            # 中文版（可能在根目录用不同名字）
            'README_zh-CN.md', 'README-Hans.md', 'README_Hans.md',
        ]
        
        # 并发获取所有语言版本的 README
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {
                executor.submit(self.get_file_content, owner, repo, readme_name): readme_name 
                for readme_name in multilang_readme_names
            }
            
            for future in as_completed(futures):
                readme_name = futures[future]
                try:
                    file_data = future.result(timeout=5)
                    if file_data and file_data.get('name', '').lower() not in found_names:
                        # 判断语言
                        name_lower = readme_name.lower()
                        if 'zh' in name_lower or 'cn' in name_lower or 'chinese' in name_lower or 'hans' in name_lower or '中文' in name_lower:
                            file_data['language'] = 'chinese'
                            lang_label = '中文'
                        elif 'ja' in name_lower:
                            file_data['language'] = 'japanese'
                            lang_label = '日文'
                        elif 'ko' in name_lower:
                            file_data['language'] = 'korean'
                            lang_label = '韩文'
                        else:
                            file_data['language'] = 'other'
                            lang_label = '其他'
                        
                        readmes.append(file_data)
                        found_names.add(file_data.get('name', '').lower())
                        print(f"    - {readme_name} ({lang_label})")
                except Exception:
                    pass
        
        # 返回所有找到的 README
        if len(readmes) == 0:
            return None
        elif len(readmes) == 1:
            return readmes[0]
        else:
            # 返回列表，包含多个 README
            print(f"    ✓ 共找到 {len(readmes)} 个 README 文件")
            return readmes
    
    def get_file_content(self, owner, repo, file_path):
        url = f"{self.base_url}/repos/{owner}/{repo}/contents/{quote(file_path)}"
        response = self.safe_request(url)
        if not response or response.status_code != 200:
            return None
        
        data = response.json()
        if data.get('encoding') == 'base64':
            try:
                content = base64.b64decode(data['content']).decode('utf-8')
                return {
                    'path': data['path'],
                    'name': data['name'],
                    'size': data['size'],
                    'content': content
                }
            except:
                return None
        return None
    
    def get_config_files(self, owner, repo):
        """获取配置文件（并发优化）"""
        config_patterns = [
            'package.json', 'package-lock.json',
            'requirements.txt', 'Pipfile', 'pyproject.toml', 'setup.py',
            'pom.xml', 'build.gradle', 'build.gradle.kts',
            'Cargo.toml', 'Cargo.lock',
            'composer.json', 'composer.lock',
            'go.mod', 'go.sum',
            'Gemfile', 'Gemfile.lock',
            'tsconfig.json', 'tsconfig.base.json',
            'webpack.config.js', 'vite.config.js',
            'docker-compose.yml', 'Dockerfile',
            '.gitignore', '.editorconfig',
            'Makefile', 'CMakeLists.txt'
        ]
        
        config_files = []
        
        # 使用线程池并发获取配置文件
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {
                executor.submit(self.get_file_content, owner, repo, pattern): pattern 
                for pattern in config_patterns
            }
            
            for future in as_completed(futures):
                pattern = futures[future]
                try:
                    file_data = future.result(timeout=5)
                    if file_data:
                        config_files.append(file_data)
                except Exception as e:
                    # 文件不存在或获取失败，静默跳过
                    pass
        
        return config_files
    
    def _collect_doc_file_paths(self, owner, repo, path='docs', max_files=35, depth=0, max_depth=3, collected_paths=None):
        """收集文档文件路径（不实际获取内容）"""
        if collected_paths is None:
            collected_paths = []
        
        if depth >= max_depth or len(collected_paths) >= max_files:
            return collected_paths
        
        url = f"{self.base_url}/repos/{owner}/{repo}/contents/{path}"
        response = self.safe_request(url)
        
        if not response or response.status_code != 200:
            return collected_paths
        
        try:
            items = response.json()
            if not isinstance(items, list):
                return collected_paths
        except:
            return collected_paths
        
        # 只处理前 50 个项目（文件+目录），增加数量以收集更多文档
        items = items[:50]
        
        for item in items:
            if len(collected_paths) >= max_files:
                break
            
            if item['type'] == 'file':
                file_ext = os.path.splitext(item['name'])[1].lower()
                if file_ext in ['.md', '.txt', '.rst', '.adoc']:
                    collected_paths.append(item['path'])
            elif item['type'] == 'dir' and depth < max_depth - 1:
                # 跳过一些常见的非重要目录
                skip_dirs = ['__pycache__', 'node_modules', '.git', 'build', 'dist', 
                           '_build', '_static', '_templates', 'test', 'tests', 'examples']
                if item['name'] not in skip_dirs:
                    self._collect_doc_file_paths(owner, repo, item['path'], 
                                                 max_files=max_files, 
                                                 depth=depth + 1, 
                                                 max_depth=max_depth,
                                                 collected_paths=collected_paths)
        
        return collected_paths
    
    def get_docs_files(self, owner, repo, path='docs', max_files=35, depth=0, max_depth=3):
        """获取文档文件（并发优化，搜索多个目录避免早停）"""
        if depth == 0:
            print(f"  获取文档文件（最多 {max_files} 个文件，最大深度 {max_depth}，并发）...")
        
        all_file_paths = []
        
        # 需要过滤的无用文档模式（法律文件、CLA协议等）
        skip_patterns = [
            'cla/', 'cla-', '-cla.', '/cla/', 
            'legal/', 'copyright', 'patent',
            'contributor-license', 'individual-',
            'corporate-', 'icla', 'ccla'
        ]
        
        def should_skip(file_path):
            """判断是否应该跳过此文件"""
            lower_path = file_path.lower()
            # 跳过 CLA 和法律文件
            for pattern in skip_patterns:
                if pattern in lower_path:
                    return True
            return False
        
        # 优先搜索核心文档目录
        priority_dirs = ['docs', 'documentation', 'doc', '.github']
        for doc_dir in priority_dirs:
            if len(all_file_paths) >= max_files:
                break
            paths = self._collect_doc_file_paths(owner, repo, doc_dir, max_files - len(all_file_paths), 0, max_depth)
            # 过滤无用文档
            paths = [p for p in paths if not should_skip(p)]
            all_file_paths.extend(paths)
            if paths:
                print(f"    在 {doc_dir}/ 目录找到 {len(paths)} 个文档")
        
        # 递归搜索所有子目录中的 README.md 文件
        if len(all_file_paths) < max_files:
            print(f"    递归搜索所有 README.md 文件...")
            readme_paths = self._collect_all_readmes(owner, repo, max_files - len(all_file_paths))
            all_file_paths.extend(readme_paths)
            if readme_paths:
                print(f"    找到 {len(readme_paths)} 个 README.md 文件")
        
        # 搜索根目录下的 Markdown 文件
        if len(all_file_paths) < max_files:
            print(f"    搜索根目录下的 Markdown 文件...")
            root_paths = self._collect_root_md_files(owner, repo, max_files - len(all_file_paths))
            root_paths = [p for p in root_paths if not should_skip(p)]
            all_file_paths.extend(root_paths)
            if root_paths:
                print(f"    在根目录找到 {len(root_paths)} 个 Markdown 文件")
        
        # 如果还不够，搜索更多子目录
        if len(all_file_paths) < max_files:
            extra_dirs = ['src', 'lib', 'packages', 'extensions', 'plugins', 'modules', 'wiki', 'guides']
            for extra_dir in extra_dirs:
                if len(all_file_paths) >= max_files:
                    break
                paths = self._collect_doc_file_paths(owner, repo, extra_dir, max_files - len(all_file_paths), 0, 2)
                # 只添加 .md 文件，并过滤无用文档
                md_paths = [p for p in paths if p.lower().endswith('.md') and not should_skip(p)]
                all_file_paths.extend(md_paths)
                if md_paths:
                    print(f"    在 {extra_dir}/ 目录找到 {len(md_paths)} 个 Markdown 文件")
        
        if not all_file_paths:
            print(f"  ⚠ 未找到文档文件")
            return []
        
        # 去重并限制文件数量
        all_file_paths = list(dict.fromkeys(all_file_paths))[:max_files]
        
        # 并发获取文件内容
        docs_files = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {
                executor.submit(self.get_file_content, owner, repo, file_path): file_path 
                for file_path in all_file_paths
            }
            
            for future in as_completed(futures):
                file_path = futures[future]
                try:
                    file_data = future.result(timeout=5)
                    if file_data:
                        print(f"    - {file_path}")
                        docs_files.append(file_data)
                except Exception as e:
                    # 文件获取失败，静默跳过
                    pass
        
        print(f"  获取到 {len(docs_files)} 个文档文件")
        return docs_files
    
    def _collect_root_md_files(self, owner, repo, max_files=30):
        """收集根目录下的 Markdown 文件（扩展搜索）"""
        url = f"{self.base_url}/repos/{owner}/{repo}/contents/"
        response = self.safe_request(url)
        
        if not response or response.status_code != 200:
            return []
        
        try:
            items = response.json()
            if not isinstance(items, list):
                return []
        except:
            return []
        
        md_files = []
        # 已经在重要文件列表中获取过的文件
        skip_files = ['README.md', 'LICENSE.md', 'SECURITY.md', 'CONTRIBUTING.md', 
                      'CHANGELOG.md', 'HISTORY.md', 'CODE_OF_CONDUCT.md', 'readme.md',
                      'license.md', 'security.md', 'contributing.md']
        
        for item in items:
            if len(md_files) >= max_files:
                break
            if item['type'] == 'file':
                file_ext = os.path.splitext(item['name'])[1].lower()
                if file_ext in ['.md', '.markdown', '.rst', '.txt']:
                    # 跳过已经获取的重要文件
                    if item['name'] not in skip_files and item['name'].lower() not in skip_files:
                        md_files.append(item['path'])
        
        return md_files
    
    def _collect_all_readmes(self, owner, repo, max_files=20, depth=0, max_depth=4, path=''):
        """递归搜索所有子目录中的 README.md 文件"""
        if depth > max_depth:
            return []
        
        url = f"{self.base_url}/repos/{owner}/{repo}/contents/{path}"
        response = self.safe_request(url)
        
        if not response or response.status_code != 200:
            return []
        
        try:
            items = response.json()
            if not isinstance(items, list):
                return []
        except:
            return []
        
        readme_paths = []
        subdirs = []
        
        for item in items:
            if len(readme_paths) >= max_files:
                break
            
            name_lower = item['name'].lower()
            
            # 找到 README 文件
            if item['type'] == 'file' and name_lower in ['readme.md', 'readme.markdown', 'readme.rst', 'readme.txt', 'readme']:
                # 跳过根目录的 README（已经单独获取）
                if path != '':
                    readme_paths.append(item['path'])
            
            # 收集子目录（排除无用目录）
            elif item['type'] == 'dir':
                dir_name = item['name'].lower()
                # 跳过不需要搜索的目录
                skip_dirs = ['node_modules', 'vendor', 'dist', 'build', '.git', '__pycache__', 
                             'venv', 'env', '.venv', 'cla', 'legal', 'test', 'tests', 
                             'benchmark', 'benchmarks', '.idea', '.vscode']
                if dir_name not in skip_dirs and not dir_name.startswith('.'):
                    subdirs.append(item['path'])
        
        # 递归搜索子目录
        if depth < max_depth and len(readme_paths) < max_files:
            for subdir in subdirs[:10]:  # 限制子目录搜索数量
                if len(readme_paths) >= max_files:
                    break
                sub_readmes = self._collect_all_readmes(
                    owner, repo, max_files - len(readme_paths), 
                    depth + 1, max_depth, subdir
                )
                readme_paths.extend(sub_readmes)
        
        return readme_paths
    
    def get_license_file(self, owner, repo):
        """获取LICENSE文件（支持多种格式，并发优化）"""
        license_patterns = [
            'LICENSE', 'LICENSE.txt', 'LICENSE.md',
            'LICENCE', 'LICENCE.txt', 'LICENCE.md',
            'COPYING', 'COPYING.txt',
            'AUTHORS', 'AUTHORS.txt', 'AUTHORS.md'
        ]
        
        # 并发获取，找到第一个就返回
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(self.get_file_content, owner, repo, pattern): pattern 
                for pattern in license_patterns
            }
            
            for future in as_completed(futures):
                pattern = futures[future]
                try:
                    file_data = future.result(timeout=3)
                    if file_data:
                        print(f"    - 找到 LICENSE: {pattern}")
                        # 取消其他未完成的任务
                        for f in futures:
                            if f != future and not f.done():
                                f.cancel()
                        return file_data
                except Exception:
                    pass
        
        return None
    
    def get_all_markdown_files(self, owner, repo, max_files=50, max_depth=3):
        """递归获取所有Markdown文件（包括doc/docx/pdf）"""
        print(f"  获取所有文档文件（Markdown/DOC/DOCX/PDF，最多 {max_files} 个）...")
        
        all_files = []
        visited_paths = set()
        
        def search_directory(path='', depth=0):
            if depth >= max_depth or len(all_files) >= max_files:
                return
            
            if path in visited_paths:
                return
            visited_paths.add(path)
            
            url = f"{self.base_url}/repos/{owner}/{repo}/contents/{path}" if path else f"{self.base_url}/repos/{owner}/{repo}/contents"
            response = self.safe_request(url)
            
            if not response or response.status_code != 200:
                return
            
            try:
                items = response.json()
                if not isinstance(items, list):
                    return
            except:
                return
            
            # 跳过常见的不需要爬取的目录
            skip_dirs = ['__pycache__', 'node_modules', '.git', 'build', 'dist', 
                        '_build', '_static', '_templates', 'test', 'tests', 'examples',
                        'vendor', 'target', 'bin', 'obj', '.idea', '.vscode']
            
            for item in items:
                if len(all_files) >= max_files:
                    break
                
                if item['type'] == 'file':
                    file_name = item['name'].lower()
                    file_ext = os.path.splitext(file_name)[1].lower()
                    
                    # 支持的文件类型（优先文本文件）
                    if file_ext in ['.md', '.markdown', '.txt', '.rst', '.adoc'] or 'license' in file_name or 'readme' in file_name:
                        file_data = self.get_file_content(owner, repo, item['path'])
                        if file_data:
                            all_files.append(file_data)
                            print(f"    - {item['path']}")
                            time.sleep(0.2)
                    # 对于二进制文件（doc/docx/pdf），尝试获取但可能无法读取内容
                    elif file_ext in ['.doc', '.docx', '.pdf']:
                        # 尝试获取文件信息（GitHub API可能不返回大文件的内容）
                        file_data = self.get_file_content(owner, repo, item['path'])
                        if file_data:
                            all_files.append(file_data)
                            print(f"    - {item['path']} (二进制文件)")
                            time.sleep(0.2)
                        else:
                            # 如果无法获取内容，至少记录文件信息
                            all_files.append({
                                'name': item['name'],
                                'path': item['path'],
                                'content': f"[二进制文件，无法读取内容] {item.get('size', 0)} bytes",
                                'size': item.get('size', 0)
                            })
                            print(f"    - {item['path']} (二进制文件，仅记录信息)")
                            time.sleep(0.1)
                
                elif item['type'] == 'dir' and depth < max_depth - 1:
                    if item['name'] not in skip_dirs:
                        search_directory(item['path'], depth + 1)
            
            time.sleep(0.3)
        
        search_directory()
        print(f"  获取到 {len(all_files)} 个文档文件")
        return all_files
    
    def get_important_md_files(self, owner, repo, max_files=20):
        """获取仓库根目录下的重要 Markdown 文件（并发优化，避免早停）"""
        print(f"  获取根目录重要文档文件（最多 {max_files} 个，并发）...")
        important_names = [
            # 核心文档
            'CONTRIBUTING.md', 'CHANGELOG.md', 'HISTORY.md',
            'LICENSE', 'LICENSE.md', 'LICENSE.txt',
            'SECURITY.md', 'CODE_OF_CONDUCT.md',
            'ROADMAP.md', 'ARCHITECTURE.md', 'DESIGN.md',
            # 引用信息
            'CITATION.cff', 'CITATION.md', 'CITATION',
            # 使用指南
            'FAQ.md', 'INSTALL.md', 'USAGE.md',
            'TUTORIAL.md', 'GUIDE.md', 'QUICKSTART.md',
            'GETTING_STARTED.md', 'DEVELOPMENT.md', 'MAINTAINERS.md',
            'CONTRIBUTORS.md', 'AUTHORS.md', 'CREDITS.md',
            'DEPLOYMENT.md', 'CONFIGURATION.md', 'TROUBLESHOOTING.md',
            'MIGRATION.md', 'UPGRADE.md', 'RELEASE_NOTES.md',
            'API.md', 'DOCUMENTATION.md', 'SPEC.md'
        ]
        
        # 限制并发数量，避免过多请求
        important_names = important_names[:max_files]
        important_files = []
        
        # 使用线程池并发获取文件
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(self.get_file_content, owner, repo, filename): filename 
                for filename in important_names
            }
            
            for future in as_completed(futures):
                filename = futures[future]
                try:
                    file_data = future.result(timeout=5)
                    if file_data:
                        print(f"    - {filename}")
                        important_files.append(file_data)
                except Exception as e:
                    # 文件不存在或获取失败，静默跳过
                    pass
        
        print(f"  获取到 {len(important_files)} 个重要 Markdown 文件")
        return important_files
    
    def get_labels(self, owner, repo):
        url = f"{self.base_url}/repos/{owner}/{repo}/labels"
        response = self.safe_request(url)
        if not response:
            return []
        
        if response.status_code == 200:
            labels = response.json()
            return [{
                'name': label['name'],
                'description': label.get('description', ''),
                'color': label['color']
            } for label in labels]
        return []
    
    def get_contributors(self, owner, repo):
        url = f"{self.base_url}/repos/{owner}/{repo}/contributors"
        response = self.safe_request(url)
        if not response:
            return []
        
        if response.status_code == 200:
            contributors = response.json()
            return [{
                'login': contributor.get('login', ''),
                'contributions': contributor.get('contributions', 0),
                'url': contributor.get('html_url', '')
            } for contributor in contributors[:50]]
        return []
    
    def get_releases(self, owner, repo):
        url = f"{self.base_url}/repos/{owner}/{repo}/releases"
        response = self.safe_request(url)
        if not response:
            return []
        
        if response.status_code == 200:
            releases = response.json()
            return [{
                'tag_name': release.get('tag_name', ''),
                'name': release.get('name', ''),
                'body': release.get('body', ''),
                'created_at': release.get('created_at', ''),
                'published_at': release.get('published_at', ''),
                'author': release.get('author', {}).get('login', ''),
                'url': release.get('html_url', '')
            } for release in releases[:20]]
        return []
    
    def calculate_fallback_metrics(self, owner, repo, repo_info):
        """禁止生成估算数据，只使用真实数据"""
        print(f"  ⚠ 不生成估算数据，只使用真实数据源")
        return {}
    
    def clean_text_for_segmentation(self, text):
        if not text:
            return ""
        
        text = str(text)
        
        text = re.sub(r'\r\n', '\n', text)
        text = re.sub(r'\r', '\n', text)
        
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        text = re.sub(r'[^\S\n]+', ' ', text)
        
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if line and len(line) > 1:
                cleaned_lines.append(line)
        
        text = '\n'.join(cleaned_lines)
        
        text = re.sub(r'[^\w\s\u4e00-\u9fff\n\r\t.,;:!?()[\]{}"\'-]', '', text)
        
        return text.strip()
    
    def crawl_all(self, owner, repo, include_opendigger=True, progress_callback=None):
        print(f"\n{'='*60}")
        print(f"开始爬取仓库: {owner}/{repo}")
        print(f"{'='*60}")
        
        self.check_rate_limit()
        all_data = {}
        missing_metrics = []
        
        if include_opendigger:
            if progress_callback:
                progress_callback(0, '获取 OpenDigger 基础指标', '正在获取基础指标...', 5)
            print("\n[0/6] 获取 OpenDigger 基础指标...")
            opendigger = OpenDiggerMetrics()
            opendigger_data, missing_metrics = opendigger.get_metrics(owner, repo)
            all_data['opendigger_metrics'] = opendigger_data
        
        if progress_callback:
            progress_callback(1, '获取仓库核心信息', '正在获取仓库信息...', 15)
        print("\n[1/6] 获取仓库核心信息...")
        all_data['repo_info'] = self.get_repo_info(owner, repo)
        
        if progress_callback:
            progress_callback(2, '获取 README', '正在获取 README...', 25)
        print("\n[2/6] 获取 README...")
        all_data['readme'] = self.get_readme(owner, repo)
        
        if progress_callback:
            progress_callback(3, '获取配置文件', '正在获取配置文件...', 40)
        print("\n[3/6] 获取配置文件...")
        all_data['config_files'] = self.get_config_files(owner, repo)
        print(f"  已获取 {len(all_data['config_files'])} 个配置文件")
        
        if progress_callback:
            progress_callback(4, '获取文档文件', '正在获取文档文件...', 60)
        print("\n[4/5] 获取文档文件...")
        all_data['docs_files'] = self.get_docs_files(owner, repo, max_files=20, max_depth=2)
        all_data['important_md_files'] = self.get_important_md_files(owner, repo, max_files=8)
        
        if progress_callback:
            progress_callback(4, '获取标签和贡献者', '正在获取标签和贡献者...', 75)
        print("\n[5/5] 获取标签和贡献者...")
        all_data['labels'] = self.get_labels(owner, repo)
        all_data['contributors'] = self.get_contributors(owner, repo)
        print(f"  标签数: {len(all_data['labels'])}")
        print(f"  贡献者数: {len(all_data['contributors'])}")
        
        # 获取 GitHub API 补充指标
        if progress_callback:
            progress_callback(5, '获取GitHub API指标', '正在获取Issue/PR/Commit指标...', 80)
        print("\n[5/6] 获取 GitHub API 指标...")
        try:
            from .github_api_metrics import GitHubAPIMetrics
            github_api = GitHubAPIMetrics()
            github_metrics = github_api.get_all_metrics(owner, repo)
            all_data['github_api_metrics'] = github_metrics
            print(f"  ✓ GitHub API 指标获取成功")
        except Exception as e:
            print(f"  ⚠ GitHub API 指标获取失败: {str(e)}")
            import traceback
            traceback.print_exc()
            all_data['github_api_metrics'] = {}
        
        # 不再生成估算数据
        if missing_metrics:
            print(f"\n  ⚠ 以下指标在 OpenDigger 中缺失: {', '.join(missing_metrics)}")
            print(f"  ℹ 系统将仅使用 GitHub API 获取的真实数据，不生成估算数据")
        
        print(f"\n{'='*60}")
        print("爬取完成！")
        print(f"{'='*60}")
        
        return all_data
    
    def _clean_excel_string(self, value):
        if not isinstance(value, str):
            return value
        cleaned = ''
        for char in value:
            code = ord(char)
            if code == 9 or code == 10 or code == 13 or (code >= 32 and code <= 126):
                cleaned += char
            elif code >= 128:
                cleaned += char
        return cleaned
    
    def _clean_dataframe_for_excel(self, df):
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].apply(self._clean_excel_string)
            return df
    
    def save_to_excel(self, data, owner, repo):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        data_dir = os.path.join(os.path.dirname(__file__), 'data', f"{owner}_{repo}")
        os.makedirs(data_dir, exist_ok=True)
        
        filename = os.path.join(data_dir, f"{owner}_{repo}_text_data_{timestamp}.xlsx")
        
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            if data.get('repo_info'):
                df = pd.DataFrame([data['repo_info']])
                df = self._clean_dataframe_for_excel(df)
                df.to_excel(writer, sheet_name='仓库信息', index=False)
            
            if data.get('readme'):
                df = pd.DataFrame([data['readme']])
                df = self._clean_dataframe_for_excel(df)
                df.to_excel(writer, sheet_name='README', index=False)
            
            if data.get('config_files'):
                df = pd.DataFrame(data['config_files'])
                df = self._clean_dataframe_for_excel(df)
                df.to_excel(writer, sheet_name='配置文件', index=False)
            
            if data.get('docs_files'):
                df = pd.DataFrame(data['docs_files'])
                df = self._clean_dataframe_for_excel(df)
                df.to_excel(writer, sheet_name='文档文件', index=False)
            
            if data.get('labels'):
                df = pd.DataFrame(data['labels'])
                df = self._clean_dataframe_for_excel(df)
                df.to_excel(writer, sheet_name='标签', index=False)
            
            if data.get('contributors'):
                df = pd.DataFrame(data['contributors'])
                df = self._clean_dataframe_for_excel(df)
                df.to_excel(writer, sheet_name='贡献者', index=False)
        
        print(f"已保存: {filename}")
        return filename
    
    def save_to_json(self, data, owner, repo):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        data_dir = os.path.join(os.path.dirname(__file__), 'data', f"{owner}_{repo}")
        os.makedirs(data_dir, exist_ok=True)
        
        filename = os.path.join(data_dir, f"{owner}_{repo}_text_data_{timestamp}.json")
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"已保存 JSON: {filename}")
        return filename
    
    def process_data(self, json_file_path, enable_maxkb_upload=None):
        """
        已废弃：旧的数据处理方法
        请使用新的流程：crawl_monthly_data.py
        """
        print("⚠ 警告: process_data 方法已废弃")
        print("   请使用新的流程: python crawl_monthly_data.py <owner> <repo>")
        print("   新流程会自动处理数据并上传到MaxKB")


def main():
    print("="*60)
    print("GitHub 仓库文本内容爬取工具")
    print("="*60)
    print("\n说明:")
    print("- 需要在 .env 文件中配置 GITHUB_TOKEN")
    print("- 爬取配置文件、文档文件等核心内容")
    print("- 数据会保存为 Excel 和 JSON 两种格式")
    print()
    
    try:
        crawler = GitHubTextCrawler()
        
        repo_name = input("请输入仓库名 (例如: apache/echarts): ").strip()
        
        if not repo_name or '/' not in repo_name:
            print("错误: 仓库名格式不正确")
            return
        
        owner, repo = repo_name.split('/', 1)
        
        data = crawler.crawl_all(owner, repo)
        
        crawler.save_to_excel(data, owner, repo)
        json_file = crawler.save_to_json(data, owner, repo)
        
        print("\n开始处理数据...")
        crawler.process_data(json_file)
        
        print("\n" + "="*60)
        print("爬取统计:")
        if data.get('opendigger_metrics'):
            print(f"  OpenDigger 指标: {len(data.get('opendigger_metrics', {}))} 个")
        if data.get('fallback_metrics'):
            print(f"  备用指标: {len(data.get('fallback_metrics', {}))} 个")
        print(f"  配置文件: {len(data.get('config_files', []))} 个")
        print(f"  文档文件: {len(data.get('docs_files', []))} 个")
        print("="*60)
        
    except KeyboardInterrupt:
        print("\n\n用户中断")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
