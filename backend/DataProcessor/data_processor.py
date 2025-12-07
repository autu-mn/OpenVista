import json
import os
import pandas as pd
from datetime import datetime
from collections import defaultdict
import re
from dotenv import load_dotenv

try:
    from .maxkb_uploader import MaxKBUploader
    MAXKB_AVAILABLE = True
except ImportError:
    try:
        from maxkb_uploader import MaxKBUploader
        MAXKB_AVAILABLE = True
    except ImportError:
        MAXKB_AVAILABLE = False

load_dotenv()


class DataProcessor:
    def __init__(self, json_file_path, enable_maxkb_upload: bool = False, maxkb_config: dict = None):
        with open(json_file_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        
        basename = os.path.basename(json_file_path)
        parts = basename.replace('_text_data_', '_').replace('.json', '').split('_')
        if len(parts) >= 2:
            self.owner = parts[0]
            self.repo = '_'.join(parts[1:-2])
        else:
            self.owner = 'unknown'
            self.repo = 'unknown'
        
        data_dir = os.path.join(os.path.dirname(__file__), 'data', f"{self.owner}_{self.repo}")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = os.path.join(data_dir, f"{self.owner}_{self.repo}_text_data_{timestamp}_processed")
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.enable_maxkb_upload = enable_maxkb_upload
        
        if maxkb_config:
            self.maxkb_config = maxkb_config
        else:
            self.maxkb_config = {
                'base_url': os.getenv('MAXKB_URL', 'http://localhost:8080'),
                'username': os.getenv('MAXKB_USERNAME', 'admin'),
                'password': os.getenv('MAXKB_PASSWORD', ''),
                'knowledge_id': os.getenv('MAXKB_KNOWLEDGE_ID', ''),
                'chunk_size': int(os.getenv('MAXKB_CHUNK_SIZE', '500'))
            }
    
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
    
    def process_timeseries_data(self):
        print("\n处理时序数据...")
        timeseries_dict = {}
        has_openrank = False
        
        if self.data.get('opendigger_metrics'):
            print(f"  处理 OpenDigger 指标...")
            for metric_name, metric_data in self.data['opendigger_metrics'].items():
                # OpenDigger 数据可能是字典格式（直接的日期->值映射）或列表格式
                if isinstance(metric_data, dict) and len(metric_data) > 0:
                    # 直接是字典格式，过滤掉年份数据（格式为 "YYYY"），只保留月份数据（"YYYY-MM"）
                    raw_data = {}
                    for date_key, value in metric_data.items():
                        # 只保留 YYYY-MM 格式的数据
                        if isinstance(date_key, str) and '-' in date_key and len(date_key) == 7:
                            raw_data[date_key] = value
                    if raw_data:
                        # 检查是否是 OpenRank 指标
                        if metric_name in ['影响力', 'openrank', 'OpenRank']:
                            timeseries_dict[f'opendigger_OpenRank'] = {'raw': raw_data}
                            print(f"    - ⭐ OpenRank (影响力): {len(raw_data)} 个数据点")
                            has_openrank = True
                        else:
                            timeseries_dict[f'opendigger_{metric_name}'] = {'raw': raw_data}
                            print(f"    - {metric_name}: {len(raw_data)} 个数据点")
                elif isinstance(metric_data, list) and len(metric_data) > 0:
                    # 列表格式，需要解析
                    raw_data = {}
                    for item in metric_data:
                        if isinstance(item, dict):
                            date = item.get('date') or item.get('month') or item.get('time')
                            value = item.get('value') or item.get('count') or item.get('score')
                            if date and value is not None:
                                raw_data[str(date)] = value
                    if raw_data:
                        if metric_name in ['影响力', 'openrank', 'OpenRank']:
                            timeseries_dict[f'opendigger_OpenRank'] = {'raw': raw_data}
                            print(f"    - ⭐ OpenRank (影响力): {len(raw_data)} 个数据点")
                            has_openrank = True
                        else:
                            timeseries_dict[f'opendigger_{metric_name}'] = {'raw': raw_data}
                            print(f"    - {metric_name}: {len(raw_data)} 个数据点")
            
            if has_openrank:
          x      print(f"  ✓ 已获取 OpenRank 指标数据")
        
        # 处理 GitHub API 指标
        if self.data.get('github_api_metrics'):
            print(f"  处理 GitHub API 指标...")
            github_metrics = self.data['github_api_metrics']
            
            # 处理月度提交数
            if 'github_api_commits' in github_metrics:
                monthly_commits = github_metrics['github_api_commits'].get('monthly_commits', {})
                if monthly_commits:
                    timeseries_dict['github_api_代码提交数'] = {'raw': monthly_commits}
                    print(f"    - 代码提交数: {len(monthly_commits)} 个数据点")
            
            # 处理聚合指标（作为单点数据存储，供后续使用）
            if 'github_api_aggregated' in github_metrics:
                agg = github_metrics['github_api_aggregated']
                if agg.get('avg_issue_response_days'):
                    print(f"    - Issue平均响应时间: {agg['avg_issue_response_days']:.1f} 天")
                if agg.get('avg_issue_resolution_days'):
                    print(f"    - Issue平均解决时长: {agg['avg_issue_resolution_days']:.1f} 天")
                if agg.get('avg_pr_processing_days'):
                    print(f"    - PR平均处理时长: {agg['avg_pr_processing_days']:.1f} 天")
                if agg.get('total_contributors'):
                    print(f"    - 总贡献者: {agg['total_contributors']} 人")
                if agg.get('inactive_contributors'):
                    print(f"    - 不活跃贡献者: {agg['inactive_contributors']} 人")
        
        # 不再处理估算数据（fallback_metrics）
        # 只使用真实数据源：OpenDigger 和 GitHub API
        
        print(f"  总共处理了 {len(timeseries_dict)} 个指标")
        
        timeseries_path = os.path.join(self.output_dir, 'timeseries_data.json')
        with open(timeseries_path, 'w', encoding='utf-8') as f:
            json.dump(timeseries_dict, f, ensure_ascii=False, indent=2)
        print(f"  已保存 JSON: {timeseries_path}")
        
        csv_path = os.path.join(self.output_dir, 'timeseries_data.csv')
        if timeseries_dict:
            all_dates = set()
            for metric_data in timeseries_dict.values():
                all_dates.update(metric_data.get('raw', {}).keys())
            
            if all_dates:
                sorted_dates = sorted(all_dates)
                csv_data = {'date': sorted_dates}
                for metric_name, metric_data in timeseries_dict.items():
                    raw_data = metric_data.get('raw', {})
                    csv_data[metric_name] = [raw_data.get(date) for date in sorted_dates]
                
                df = pd.DataFrame(csv_data)
                df.to_csv(csv_path, index=False, encoding='utf-8-sig')
                print(f"  已保存 CSV: {csv_path} ({len(sorted_dates)} 行, {len(csv_data)} 列)")
            else:
                print(f"  警告: 没有找到有效的日期数据")
                with open(csv_path, 'w', encoding='utf-8') as f:
                    f.write('')
        else:
            print(f"  警告: 没有时序数据可处理")
            with open(csv_path, 'w', encoding='utf-8') as f:
                f.write('')
        
        return timeseries_dict
    
    def _format_doc(self, doc_type, title, content, metadata):
        cleaned_content = self.clean_text_for_segmentation(content)
        return {
            'type': doc_type,
            'title': title,
            'content': cleaned_content,
            'metadata': metadata
        }
    
    def format_text_for_training(self):
        print("\n处理文本数据...")
        
        text_documents = []
        
        if self.data.get('repo_info'):
            r = self.data['repo_info']
            doc = f"""# 仓库基本信息

仓库名称: {r.get('full_name', '')}
描述: {r.get('description', '')}
主页: {r.get('homepage', '')}
编程语言: {r.get('language', '')}
Star数: {r.get('stars', 0)}
Fork数: {r.get('forks', 0)}
Watcher数: {r.get('watchers', 0)}
开放Issue数: {r.get('open_issues', 0)}
创建时间: {r.get('created_at', '')}
更新时间: {r.get('updated_at', '')}
许可证: {r.get('license', '')}
标签: {', '.join(r.get('topics', []))}
"""
            text_documents.append(self._format_doc('repo_info', '仓库基本信息', doc, 
                {'source': 'repo_info', 'repo': r.get('full_name', '')}))
        
        if self.data.get('readme'):
            readme_data = self.data['readme']
            # 可能是单个 README 或多个 README 的列表
            if isinstance(readme_data, list):
                # 多个 README（中英文）
                for r in readme_data:
                    lang_label = r.get('language', 'default')
                    lang_text = '中文' if lang_label == 'chinese' else '默认'
                    doc = f"""# README文档 ({lang_text})

文件路径: {r.get('path', '')}
文件大小: {r.get('size', 0)} 字节

内容:
{r.get('content', '')}
"""
                    text_documents.append(self._format_doc('readme', 
                        f"README: {r.get('name', 'README.md')} ({lang_text})", doc,
                        {'source': 'readme', 'path': r.get('path', ''), 'language': lang_label}))
            else:
                # 单个 README
                r = readme_data
                doc = f"""# README文档

文件路径: {r.get('path', '')}
文件大小: {r.get('size', 0)} 字节

内容:
{r.get('content', '')}
"""
                text_documents.append(self._format_doc('readme', f"README: {r.get('name', 'README.md')}", doc,
                    {'source': 'readme', 'path': r.get('path', '')}))
        
        for docs_file in self.data.get('docs_files', []):
            doc = f"""# 文档文件: {docs_file.get('name', '')}

文件路径: {docs_file.get('path', '')}
文件大小: {docs_file.get('size', 0)} 字节

内容:
{docs_file.get('content', '')}
"""
            text_documents.append(self._format_doc('docs_file', 
                f"文档: {docs_file.get('name', '')}", doc,
                {'source': 'docs_file', 'path': docs_file.get('path', '')}))
        
        for important_md in self.data.get('important_md_files', []):
            doc = f"""# 重要文档: {important_md.get('name', '')}

文件路径: {important_md.get('path', '')}
文件大小: {important_md.get('size', 0)} 字节

内容:
{important_md.get('content', '')}
"""
            text_documents.append(self._format_doc('important_md', 
                f"重要文档: {important_md.get('name', '')}", doc,
                {'source': 'important_md', 'path': important_md.get('path', '')}))
        
        for release in self.data.get('releases', []):
            doc = f"""# 发布版本: {release.get('tag_name', '')}

版本名称: {release.get('name', '')}
发布时间: {release.get('published_at', '')}
创建时间: {release.get('created_at', '')}
作者: {release.get('author', '')}

发布说明:
{release.get('body', '')}
"""
            text_documents.append(self._format_doc('release', 
                f"版本: {release.get('tag_name', '')}", doc,
                {'source': 'release', 'tag': release.get('tag_name', '')}))
        
        structured_path = os.path.join(self.output_dir, 'text_data_structured.json')
        with open(structured_path, 'w', encoding='utf-8') as f:
            json.dump(text_documents, f, ensure_ascii=False, indent=2)
        
        training_text = []
        for doc in text_documents:
            training_text.append(f"## {doc['title']}\n\n{doc['content']}\n")
        
        training_path = os.path.join(self.output_dir, 'text_data_for_training.txt')
        with open(training_path, 'w', encoding='utf-8') as f:
            f.write('\n\n'.join(training_text))
        
        print(f"  已处理 {len(text_documents)} 个文档")
        return text_documents
    
    def _upload_to_maxkb(self, file_path: str):
        if not self.enable_maxkb_upload:
            return
        
        if not MAXKB_AVAILABLE:
            print("⚠ MaxKB上传模块未找到")
            return
        
        try:
            # 移除 chunk_size，因为 MaxKBUploader 不接受这个参数
            maxkb_init_config = {k: v for k, v in self.maxkb_config.items() if k != 'chunk_size'}
            uploader = MaxKBUploader(**maxkb_init_config)
            
            if uploader.login():
                chunk_size = self.maxkb_config.get('chunk_size', 500)
                
                # 重命名文件，添加仓库前缀
                import shutil
                original_filename = os.path.basename(file_path)
                new_filename = f"{self.owner}_{self.repo}_{original_filename}"
                new_file_path = os.path.join(os.path.dirname(file_path), new_filename)
                
                # 创建副本用于上传
                shutil.copy2(file_path, new_file_path)
                
                try:
                    print(f"  上传文件: {new_filename}")
                    uploader.upload_text_file(new_file_path, chunk_size=chunk_size)
                finally:
                    # 清理临时文件
                    if os.path.exists(new_file_path):
                        os.remove(new_file_path)
            else:
                print("✗ MaxKB登录失败，无法上传文件")
        except Exception as e:
            print(f"✗ MaxKB上传失败: {str(e)}")
    
    def process_all(self):
        print(f"\n{'='*60}\n开始处理数据: {self.owner}/{self.repo}\n{'='*60}")
        
        timeseries_data = self.process_timeseries_data()
        text_data = self.format_text_for_training()
        
        summary = {
            'repo': f"{self.owner}/{self.repo}",
            'processed_at': datetime.now().isoformat(),
            'timeseries_metrics_count': len(timeseries_data),
            'text_documents_count': len(text_data),
            'text_documents_by_type': {}
        }
        
        for doc in text_data:
            doc_type = doc['type']
            summary['text_documents_by_type'][doc_type] = summary['text_documents_by_type'].get(doc_type, 0) + 1
        
        summary_path = os.path.join(self.output_dir, 'processing_summary.json')
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        print(f"\n{'='*60}\n处理完成！\n{'='*60}")
        print(f"输出目录: {self.output_dir}")
        print(f"时序指标数: {summary['timeseries_metrics_count']}")
        print(f"文本文档数: {summary['text_documents_count']}")
        
        training_file = os.path.join(self.output_dir, 'text_data_for_training.txt')
        if os.path.exists(training_file) and self.enable_maxkb_upload:
            print("\n开始上传到MaxKB知识库...")
            self._upload_to_maxkb(training_file)
        
        return summary


def main():
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python data_processor.py <json_file_path>")
        return
    
    json_file_path = sys.argv[1]
    
    if not os.path.exists(json_file_path):
        print(f"错误: 文件不存在: {json_file_path}")
        return
    
    try:
        processor = DataProcessor(json_file_path)
        processor.process_all()
    except Exception as e:
        print(f"处理失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
