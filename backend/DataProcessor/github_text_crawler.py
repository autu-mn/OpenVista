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

load_dotenv()


class OpenDiggerMetrics:
    def __init__(self):
        self.base_url = "https://oss.open-digger.cn/github/"
    
    def get_metrics(self, owner, repo):
        metrics_config = {
            'activity': '活跃度',
            'openrank': '影响力',
            'stars': 'Star数',
            'participants': '参与者数',
            'technical_fork': 'Fork数',
            'issues_new': '新增Issue',
            'issues_closed': '关闭Issue',
            'change_requests_accepted': 'PR接受数',
            'change_requests_declined': 'PR拒绝数',
            'code_change_commits': '代码提交数',
        }
        
        result = {}
        success_count = 0
        missing_metrics = []
        
        for metric_key, metric_name in metrics_config.items():
            url = f"{self.base_url}{owner}/{repo}/{metric_key}.json"
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data:
                        result[metric_name] = data
                        success_count += 1
                    else:
                        missing_metrics.append(metric_name)
                else:
                    missing_metrics.append(metric_name)
            except:
                missing_metrics.append(metric_name)
        
        return result, missing_metrics


class GitHubTextCrawler:
    def __init__(self):
        self.tokens = []
        self.current_token_index = 0
        
        token = os.getenv('GITHUB_TOKEN')
        token_1 = os.getenv('GITHUB_TOKEN_1')
        token_2 = os.getenv('GITHUB_TOKEN_2')
        
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
                    time.sleep(1)
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
                    time.sleep(1)
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
        """获取 README 文件（包括英文版和中文版）"""
        readmes = []
        
        # 尝试获取默认 README（通常是英文）
        url = f"{self.base_url}/repos/{owner}/{repo}/readme"
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
                        'language': 'default'
                    })
                    print(f"    - {data['name']} (默认)")
        
        # 尝试获取中文版 README
        chinese_readme_names = [
            'README-cn.md', 'README-CN.md', 'README_CN.md', 'README_cn.md',
            'README-zh.md', 'README-ZH.md', 'README_ZH.md', 'README_zh.md',
            'README-zh-CN.md', 'README_zh_CN.md',
            'README.zh.md', 'README.zh-CN.md',
            'README中文.md', 'README.Chinese.md'
        ]
        
        for readme_name in chinese_readme_names:
            file_data = self.get_file_content(owner, repo, readme_name)
            if file_data:
                file_data['language'] = 'chinese'
                readmes.append(file_data)
                print(f"    - {readme_name} (中文)")
                break  # 找到一个中文版就停止
        
        # 返回所有找到的 README（如果有多个）或单个或 None
        if len(readmes) == 0:
            return None
        elif len(readmes) == 1:
            return readmes[0]
        else:
            # 返回列表，包含多个 README
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
        config_files = []
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
        
        for pattern in config_patterns:
            file_data = self.get_file_content(owner, repo, pattern)
            if file_data:
                config_files.append(file_data)
                time.sleep(0.3)
        
        return config_files
    
    def get_docs_files(self, owner, repo, path='docs', max_files=30, depth=0, max_depth=2):
        """获取 docs 目录下的文档文件（限制递归深度和文件数）"""
        if depth >= max_depth:
            return []
        
        if depth == 0:
            print(f"  获取 docs 目录文档（最多 {max_files} 个文件，最大深度 {max_depth}）...")
        
        docs_files = []
        url = f"{self.base_url}/repos/{owner}/{repo}/contents/{path}"
        response = self.safe_request(url)
        
        if not response or response.status_code != 200:
            if depth == 0:
                print(f"  docs 目录不存在或无法访问")
            return docs_files
        
        try:
            items = response.json()
            if not isinstance(items, list):
                return docs_files
        except:
            return docs_files
        
        # 只处理前 20 个项目（文件+目录），避免目录项过多
        items = items[:20]
        
        for item in items:
            # 检查是否已达到文件数限制
            if len(docs_files) >= max_files:
                if depth == 0:
                    print(f"  已达到文件数限制 ({max_files})，停止爬取")
                break
                
            if item['type'] == 'file':
                file_ext = os.path.splitext(item['name'])[1].lower()
                if file_ext in ['.md', '.txt', '.rst', '.adoc']:
                    if depth == 0:
                        print(f"    - {item['name']}")
                    file_data = self.get_file_content(owner, repo, item['path'])
                    if file_data:
                        docs_files.append(file_data)
                        time.sleep(0.2)  # 减少延迟
            elif item['type'] == 'dir' and depth < max_depth - 1:
                # 跳过一些常见的非重要目录
                skip_dirs = ['__pycache__', 'node_modules', '.git', 'build', 'dist', 
                           '_build', '_static', '_templates', 'test', 'tests', 'examples']
                if item['name'] not in skip_dirs:
                    remaining = max_files - len(docs_files)
                    if remaining > 0:
                        sub_docs = self.get_docs_files(owner, repo, item['path'], 
                                                       max_files=remaining, 
                                                       depth=depth + 1, 
                                                       max_depth=max_depth)
                        docs_files.extend(sub_docs)
        
        if depth == 0:
            print(f"  获取到 {len(docs_files)} 个文档文件")
        return docs_files
    
    def get_important_md_files(self, owner, repo, max_files=10):
        """获取仓库根目录下的重要 Markdown 文件"""
        print(f"  获取根目录重要 Markdown 文件...")
        important_files = []
        important_names = [
            'CONTRIBUTING.md', 'CHANGELOG.md', 'HISTORY.md',
            'LICENSE.md', 'SECURITY.md', 'CODE_OF_CONDUCT.md',
            'ROADMAP.md', 'ARCHITECTURE.md', 'DESIGN.md',
            'FAQ.md', 'INSTALL.md', 'USAGE.md'
        ]
        
        count = 0
        for filename in important_names:
            if count >= max_files:
                break
            file_data = self.get_file_content(owner, repo, filename)
            if file_data:
                print(f"    - {filename}")
                important_files.append(file_data)
                count += 1
                time.sleep(0.2)  # 减少延迟
        
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
        try:
            from data_processor import DataProcessor
            
            if enable_maxkb_upload is None:
                maxkb_knowledge_id = os.getenv('MAXKB_KNOWLEDGE_ID')
                enable_maxkb_upload = bool(maxkb_knowledge_id)
                if enable_maxkb_upload:
                    print("\n检测到MaxKB配置，将自动上传到知识库...")
            
            processor = DataProcessor(
                json_file_path=json_file_path,
                enable_maxkb_upload=enable_maxkb_upload
            )
            processor.process_all()
        except ImportError:
            print("警告: 未找到 data_processor 模块，跳过数据处理")
        except Exception as e:
            import traceback
            traceback.print_exc()


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
