"""
按月数据处理模块
- 数据分离：描述性文本→MaxKB，时序数据→双塔模型
- LLM摘要生成
"""

import os
import json
import sys
from typing import Dict, List, Optional
from datetime import datetime

# 添加项目路径以导入LLM客户端
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from backend.Agent.deepseek_client import DeepSeekClient
    LLM_AVAILABLE = True
except ImportError:
    try:
        from Agent.deepseek_client import DeepSeekClient
        LLM_AVAILABLE = True
    except ImportError:
        LLM_AVAILABLE = False
        print("  ⚠ LLM客户端不可用，将跳过摘要生成")


class MonthlyDataProcessor:
    """按月数据处理"""
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        if not self.llm_client and LLM_AVAILABLE:
            try:
                self.llm_client = DeepSeekClient()
            except:
                print("  ⚠ 无法初始化LLM客户端")
        
        # 定义所有25个指标（用于确保所有指标都被保存，缺失的用0填充）
        self.all_metrics_list = [
            'OpenRank', '活跃度', 'Star数', 'Fork数', '关注度', '参与者数',
            '新增贡献者', '贡献者', '不活跃贡献者', '总线因子',
            '新增Issue', '关闭Issue', 'Issue评论', 'Issue响应时间', 'Issue解决时长', 'Issue存活时间',
            '变更请求', 'PR接受数', 'PR审查', 'PR响应时间', 'PR处理时长', 'PR存活时间',
            '代码新增行数', '代码删除行数', '代码变更总行数'
        ]
    
    def _ensure_all_metrics(self, opendigger_metrics: Dict) -> Dict:
        """
        确保所有25个指标都存在
        优先级：OpenDigger > GitHub API补充 > 0填充（用于模型训练）
        
        Args:
            opendigger_metrics: OpenDigger返回的指标数据（可能已包含GitHub API补充的数据）
            
        Returns:
            完整的指标数据（所有25个指标都存在）
        """
        complete_metrics = {}
        
        # 提取时间范围（从有数据的指标中提取）
        all_months = set()
        for metric_name, metric_data in opendigger_metrics.items():
            if isinstance(metric_data, dict):
                all_months.update(metric_data.keys())
        
        # 为所有指标创建完整数据
        for metric_name in self.all_metrics_list:
            if metric_name in opendigger_metrics:
                # 有数据（OpenDigger或GitHub API补充），使用实际数据
                metric_data = opendigger_metrics[metric_name]
                if isinstance(metric_data, dict):
                    # 为所有月份填充数据（缺失的用0）
                    complete_data = {}
                    for month in sorted(all_months):
                        if len(month) >= 7:
                            month_str = month[:7]
                            # 优先使用实际数据，没有则用0
                            complete_data[month_str] = metric_data.get(month_str, 0.0)
                    complete_metrics[metric_name] = complete_data
                else:
                    # 非字典格式，创建全0数据
                    complete_data = {}
                    for month in sorted(all_months):
                        if len(month) >= 7:
                            month_str = month[:7]
                            complete_data[month_str] = 0.0
                    complete_metrics[metric_name] = complete_data
            else:
                # 没有数据（既没有OpenDigger也没有GitHub API补充），创建全0数据
                complete_data = {}
                for month in sorted(all_months):
                    if len(month) >= 7:
                        month_str = month[:7]
                        complete_data[month_str] = 0.0
                complete_metrics[metric_name] = complete_data
        
        return complete_metrics
    
    def _preprocess_text(self, text: str) -> str:
        """
        预处理文本内容，清理和格式化
        """
        if not text:
            return ""
        
        # 1. 移除过多的空行（保留最多2个连续空行）
        import re
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # 2. 移除行首行尾空白
        lines = text.split('\n')
        text = '\n'.join(line.rstrip() for line in lines)
        
        # 3. 移除Markdown中的HTML注释
        text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
        
        # 4. 移除代码块中的过长行（超过200字符的行可能是base64编码等，不适合作为知识库）
        # 但保留代码块结构
        lines = text.split('\n')
        processed_lines = []
        in_code_block = False
        
        for line in lines:
            if line.strip().startswith('```'):
                in_code_block = not in_code_block
                processed_lines.append(line)
            elif in_code_block and len(line) > 500:
                # 跳过过长的行（可能是base64编码等）
                continue
            else:
                processed_lines.append(line)
        
        text = '\n'.join(processed_lines)
        
        # 5. 移除URL中的敏感信息（可选）
        # text = re.sub(r'https?://[^\s]+', '[URL]', text)
        
        return text.strip()
    
    def extract_static_texts(self, static_docs: Dict) -> Dict:
        """
        提取静态描述性文本（用于MaxKB）
        包括：README、文档文件等
        会对文本进行预处理：清理、格式化、提取关键信息
        """
        static_texts = {
            'repo_info': static_docs.get('repo_info', {}),
            'readme': None,
            'license': None,
            'docs': [],
            'config_files': []
        }
        
        # 提取README并预处理
        readme_data = static_docs.get('readme')
        if readme_data:
            if isinstance(readme_data, list):
                # 多个README，合并并预处理
                readme_content = '\n\n'.join(
                    item.get('content', '') for item in readme_data if item.get('content')
                )
                static_texts['readme'] = self._preprocess_text(readme_content)
            elif isinstance(readme_data, dict):
                readme_content = readme_data.get('content', '')
                static_texts['readme'] = self._preprocess_text(readme_content)
        
        # 提取LICENSE并预处理
        license_data = static_docs.get('license')
        if license_data:
            license_content = license_data.get('content', '')
            static_texts['license'] = self._preprocess_text(license_content)
        
        # 提取文档文件（合并所有来源）
        docs_files = static_docs.get('docs_files', [])
        important_md = static_docs.get('important_md_files', [])
        all_docs = static_docs.get('all_doc_files', [])
        
        # 合并所有文档，去重（按path），并预处理内容
        all_doc_dict = {}
        for doc_list in [docs_files, important_md, all_docs]:
            for doc in doc_list:
                path = doc.get('path', '')
                if path and path not in all_doc_dict:
                    content = doc.get('content', '')
                    # 预处理文档内容
                    processed_content = self._preprocess_text(content)
                    
                    # 只保留有实际内容的文档（至少50个字符）
                    if len(processed_content) >= 50:
                        all_doc_dict[path] = {
                            'name': doc.get('name', 'unknown.md'),
                            'path': path,
                            'content': processed_content
                        }
        
        static_texts['docs'] = list(all_doc_dict.values())
        
        # 提取配置文件并预处理
        config_files = static_docs.get('config_files', [])
        for config in config_files:
            content = config.get('content', '')
            processed_content = self._preprocess_text(content)
            
            # 配置文件也保留（即使内容较短）
            static_texts['config_files'].append({
                'name': config.get('name', ''),
                'path': config.get('path', ''),
                'content': processed_content
            })
        
        print(f"  ✓ 文本预处理完成:")
        print(f"    - README: {'✓' if static_texts['readme'] else '✗'}")
        print(f"    - LICENSE: {'✓' if static_texts['license'] else '✗'}")
        print(f"    - 文档文件: {len(static_texts['docs'])} 个（已预处理）")
        print(f"    - 配置文件: {len(static_texts['config_files'])} 个（已预处理）")
        
        return static_texts
    
    def process_monthly_data_for_model(self, monthly_data: Dict, opendigger_metrics: Dict) -> Dict:
        """
        处理月度数据用于双塔模型
        返回格式：
        {
          '2024-01': {
            'timeseries_features': [17维特征],
            'text_data': {
              'full_text': '完整文本',
              'llm_summary': 'LLM摘要',
              'breakdown': {...}
            },
            'opendigger_metrics': {
              'OpenRank': 10.5,
              '活跃度': 20.3,
              ... (所有25个指标，缺失的用0填充)
            }
          },
          ...
        }
        """
        processed = {}
        
        # 定义所有25个指标（用于确保所有指标都被保存，缺失的用0填充）
        all_metrics_list = [
            'OpenRank', '活跃度', 'Star数', 'Fork数', '关注度', '参与者数',
            '新增贡献者', '贡献者', '不活跃贡献者', '总线因子',
            '新增Issue', '关闭Issue', 'Issue评论', 'Issue响应时间', 'Issue解决时长', 'Issue存活时间',
            '变更请求', 'PR接受数', 'PR审查', 'PR响应时间', 'PR处理时长', 'PR存活时间',
            '代码新增行数', '代码删除行数', '代码变更总行数'
        ]
        
        for month, month_data in monthly_data.items():
            # 提取数值特征
            timeseries_features = self._extract_timeseries_features(month, opendigger_metrics)
            
            # 拼接完整文本
            full_text = self._concatenate_full_text(month_data)
            
            # 生成LLM摘要
            llm_summary = self._generate_llm_summary(month_data, full_text)
            
            # 提取该月的所有OpenDigger指标（缺失的用0填充，用于模型训练）
            month_metrics = {}
            for metric_name in all_metrics_list:
                if metric_name in opendigger_metrics:
                    metric_data = opendigger_metrics[metric_name]
                    if isinstance(metric_data, dict):
                        # 获取该月的值，如果没有则用0
                        value = metric_data.get(month, 0.0)
                        month_metrics[metric_name] = float(value) if value is not None else 0.0
                    else:
                        month_metrics[metric_name] = 0.0
                else:
                    # 指标不存在，用0填充
                    month_metrics[metric_name] = 0.0
            
            # 组织数据
            processed[month] = {
                'timeseries_features': timeseries_features,
                'opendigger_metrics': month_metrics,  # 保存所有25个指标，缺失的用0填充
                'text_data': {
                    'full_text': full_text,
                    'llm_summary': llm_summary,
                    'breakdown': {
                        'issues_text': self._extract_issues_text(month_data.get('issues', [])),
                        'prs_text': self._extract_prs_text(month_data.get('prs', [])),
                        'commits_text': self._extract_commits_text(month_data.get('commits', [])),
                        'releases_text': self._extract_releases_text(month_data.get('releases', []))
                    }
                }
            }
        
        return processed
    
    def _extract_timeseries_features(self, month: str, opendigger_metrics: Dict) -> List[float]:
        """
        提取17维时序特征
        从OpenDigger指标中提取该月的特征值
        """
        features = []
        
        # OpenDigger指标（10个）
        metric_keys = [
            'openrank', 'activity', 'stars', 'forks', 'participants',
            'issues_new', 'issues_closed', 'prs_accepted', 'prs_declined', 'commits'
        ]
        
        for key in metric_keys:
            # 查找对应的指标数据
            metric_data = None
            for metric_name, data in opendigger_metrics.items():
                if key.lower() in metric_name.lower():
                    metric_data = data
                    break
            
            if metric_data and isinstance(metric_data, dict):
                value = metric_data.get(month, 0.0)
            else:
                value = 0.0
            
            features.append(float(value))
        
        # GitHub API指标（7个）- 需要从月度数据中计算
        # 这里先填充默认值，实际应该从github_api_metrics获取
        features.extend([
            0.0,  # avg_issue_response_days
            0.0,  # avg_issue_resolution_days
            0.0,  # avg_pr_processing_days
            0.0,  # contributors_count
            0.0,  # activity_score
            0.0,  # community_engagement
            0.0   # releases_count
        ])
        
        return features
    
    def _concatenate_full_text(self, month_data: Dict) -> str:
        """拼接该月的完整文本"""
        texts = []
        
        # Issues文本
        issues_text = self._extract_issues_text(month_data.get('issues', []))
        if issues_text:
            texts.append(f"=== Issues ===\n{issues_text}")
        
        # PRs文本
        prs_text = self._extract_prs_text(month_data.get('prs', []))
        if prs_text:
            texts.append(f"=== Pull Requests ===\n{prs_text}")
        
        # Commits文本
        commits_text = self._extract_commits_text(month_data.get('commits', []))
        if commits_text:
            texts.append(f"=== Commits ===\n{commits_text}")
        
        # Releases文本
        releases_text = self._extract_releases_text(month_data.get('releases', []))
        if releases_text:
            texts.append(f"=== Releases ===\n{releases_text}")
        
        return "\n\n".join(texts)
    
    def _extract_issues_text(self, issues: List[Dict]) -> str:
        """提取Issues的完整文本"""
        texts = []
        for issue in issues:
            issue_text = f"Issue #{issue.get('number', '')}: {issue.get('title', '')}\n"
            issue_text += f"{issue.get('body', '')}\n"
            
            # 添加评论
            for comment in issue.get('comments', []):
                issue_text += f"\nComment by {comment.get('user', '')}: {comment.get('body', '')}\n"
            
            texts.append(issue_text)
        
        return "\n---\n".join(texts)
    
    def _extract_prs_text(self, prs: List[Dict]) -> str:
        """提取PRs的完整文本"""
        texts = []
        for pr in prs:
            pr_text = f"PR #{pr.get('number', '')}: {pr.get('title', '')}\n"
            pr_text += f"{pr.get('body', '')}\n"
            
            # 添加评论
            for comment in pr.get('comments', []):
                pr_text += f"\nComment by {comment.get('user', '')}: {comment.get('body', '')}\n"
            
            # 添加review comments
            for review_comment in pr.get('review_comments', []):
                pr_text += f"\nReview comment by {review_comment.get('user', '')} on {review_comment.get('path', '')}: {review_comment.get('body', '')}\n"
            
            texts.append(pr_text)
        
        return "\n---\n".join(texts)
    
    def _extract_commits_text(self, commits: List[Dict]) -> str:
        """提取Commits的完整文本"""
        texts = []
        for commit in commits:
            commit_text = f"Commit {commit.get('sha', '')[:8]}: {commit.get('message', '')}\n"
            commit_text += f"Author: {commit.get('author', {}).get('name', '')}\n"
            
            # 添加文件变更信息
            files = commit.get('files', [])
            if files:
                commit_text += f"Changed files: {len(files)}\n"
                for f in files[:5]:  # 最多显示5个文件
                    commit_text += f"  - {f.get('filename', '')} (+{f.get('additions', 0)}/-{f.get('deletions', 0)})\n"
            
            texts.append(commit_text)
        
        return "\n---\n".join(texts)
    
    def _extract_releases_text(self, releases: List[Dict]) -> str:
        """提取Releases的完整文本"""
        texts = []
        for release in releases:
            release_text = f"Release {release.get('tag_name', '')}: {release.get('name', '')}\n"
            release_text += f"{release.get('body', '')}\n"
            texts.append(release_text)
        
        return "\n---\n".join(texts)
    
    def _generate_llm_summary(self, month_data: Dict, full_text: str) -> str:
        """使用LLM生成月度摘要"""
        if not self.llm_client:
            return "LLM客户端不可用，无法生成摘要"
        
        # 统计信息
        stats = {
            'issues_count': len(month_data.get('issues', [])),
            'prs_count': len(month_data.get('prs', [])),
            'commits_count': len(month_data.get('commits', [])),
            'releases_count': len(month_data.get('releases', []))
        }
        
        prompt = f"""你是开源项目分析专家。请为以下月度数据生成简洁的摘要（2-3句话）。

【月度统计】
- Issues: {stats['issues_count']}个
- PRs: {stats['prs_count']}个
- Commits: {stats['commits_count']}个
- Releases: {stats['releases_count']}个

【主要内容】
{full_text[:2000]}  # 限制长度

请生成简洁的摘要，突出该月的主要活动和变化。"""
        
        try:
            # DeepSeekClient使用ask方法，不是generate方法
            summary = self.llm_client.ask(prompt, context="")
            return summary.strip() if summary else f"该月有{stats['issues_count']}个Issues，{stats['prs_count']}个PRs，{stats['commits_count']}个Commits。"
        except Exception as e:
            print(f"  ⚠ LLM摘要生成失败: {str(e)}")
            return f"该月有{stats['issues_count']}个Issues，{stats['prs_count']}个PRs，{stats['commits_count']}个Commits。"
    
    def save_for_maxkb(self, static_texts: Dict, output_dir: str):
        """保存用于MaxKB的静态文本"""
        maxkb_dir = os.path.join(output_dir, 'text_for_maxkb')
        os.makedirs(maxkb_dir, exist_ok=True)
        
        # 保存README
        if static_texts.get('readme'):
            readme_path = os.path.join(maxkb_dir, 'README.md')
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(static_texts['readme'])
        
        # 保存LICENSE
        if static_texts.get('license'):
            license_path = os.path.join(maxkb_dir, 'LICENSE')
            with open(license_path, 'w', encoding='utf-8') as f:
                f.write(static_texts['license'])
        
        # 保存文档（保持目录结构）
        docs_dir = os.path.join(maxkb_dir, 'docs')
        os.makedirs(docs_dir, exist_ok=True)
        for doc in static_texts.get('docs', []):
            doc_path = doc.get('path', doc.get('name', 'unknown.md'))
            # 处理路径，避免目录遍历
            doc_path = doc_path.replace('..', '').lstrip('/')
            if not doc_path:
                doc_path = doc.get('name', 'unknown.md')
            
            full_path = os.path.join(docs_dir, doc_path)
            # 确保目录存在
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            try:
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(doc.get('content', ''))
            except Exception as e:
                # 如果写入失败（可能是二进制文件），跳过
                print(f"    ⚠ 跳过文件 {doc_path}: {str(e)}")
        
        print(f"  ✓ MaxKB文本已保存到: {maxkb_dir}")
        print(f"    - README: {'✓' if static_texts.get('readme') else '✗'}")
        print(f"    - LICENSE: {'✓' if static_texts.get('license') else '✗'}")
        print(f"    - 文档文件: {len(static_texts.get('docs', []))} 个")
        
        return maxkb_dir
    
    def upload_to_maxkb(self, maxkb_dir: str, owner: str, repo: str):
        """上传描述文本到MaxKB知识库"""
        try:
            from backend.DataProcessor.maxkb_uploader import MaxKBUploader
        except ImportError:
            try:
                from maxkb_uploader import MaxKBUploader
            except ImportError:
                print("  ⚠ MaxKB上传模块不可用，跳过上传")
                return
        
        # 检查是否配置了MaxKB
        import os
        maxkb_password = os.getenv('MAXKB_PASSWORD')
        maxkb_knowledge_id = os.getenv('MAXKB_KNOWLEDGE_ID')
        
        if not maxkb_password or not maxkb_knowledge_id:
            print("  ℹ MaxKB未配置（需要MAXKB_PASSWORD和MAXKB_KNOWLEDGE_ID），跳过上传")
            return
        
        print("\n  → 开始上传到MaxKB知识库...")
        
        try:
            uploader = MaxKBUploader()
            
            if not uploader.login():
                print("  ✗ MaxKB登录失败，跳过上传")
                return
            
            # 上传README
            readme_path = os.path.join(maxkb_dir, 'README.md')
            if os.path.exists(readme_path):
                print(f"    - 上传 README.md...")
                if uploader.upload_document(readme_path, chunk_size=500, document_name=f"{owner}/{repo} - README"):
                    print(f"      ✓ README上传成功")
                else:
                    print(f"      ✗ README上传失败")
            
            # 上传LICENSE
            license_path = os.path.join(maxkb_dir, 'LICENSE')
            if os.path.exists(license_path):
                print(f"    - 上传 LICENSE...")
                if uploader.upload_document(license_path, chunk_size=500, document_name=f"{owner}/{repo} - LICENSE"):
                    print(f"      ✓ LICENSE上传成功")
                else:
                    print(f"      ✗ LICENSE上传失败")
            
            # 上传文档文件
            docs_dir = os.path.join(maxkb_dir, 'docs')
            if os.path.exists(docs_dir):
                print(f"    - 上传文档文件（{docs_dir}）...")
                uploaded_count = 0
                failed_count = 0
                
                for root, dirs, files in os.walk(docs_dir):
                    for file in files:
                        if file.endswith(('.md', '.txt', '.rst', '.adoc')):
                            file_path = os.path.join(root, file)
                            # 计算相对路径作为文档名
                            rel_path = os.path.relpath(file_path, docs_dir)
                            doc_name = f"{owner}/{repo} - {rel_path}"
                            
                            if uploader.upload_document(file_path, chunk_size=500, document_name=doc_name):
                                uploaded_count += 1
                            else:
                                failed_count += 1
                            
                            # 避免请求过快
                            import time
                            time.sleep(0.5)
                
                print(f"      ✓ 成功上传 {uploaded_count} 个文档")
                if failed_count > 0:
                    print(f"      ⚠ 失败 {failed_count} 个文档")
            
            print("  ✓ MaxKB上传完成")
            
        except Exception as e:
            print(f"  ✗ MaxKB上传出错: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def save_for_model(self, processed_data: Dict, output_dir: str):
        """保存用于双塔模型的时序数据"""
        model_dir = os.path.join(output_dir, 'timeseries_for_model')
        os.makedirs(model_dir, exist_ok=True)
        
        # 保存月度数据
        for month, data in processed_data.items():
            month_file = os.path.join(model_dir, f"{month}.json")
            with open(month_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        
        # 保存汇总文件
        summary_file = os.path.join(model_dir, 'all_months.json')
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(processed_data, f, ensure_ascii=False, indent=2)
        
        print(f"  ✓ 双塔模型数据已保存到: {model_dir}")
        print(f"    共 {len(processed_data)} 个月的数据")

