"""问答Agent - 基于项目数据提供智能问答"""
import os
import json
from typing import Dict, Optional

try:
    from .deepseek_client import DeepSeekClient
    DEEPSEEK_AVAILABLE = True
except ImportError:
    try:
        from deepseek_client import DeepSeekClient
        DEEPSEEK_AVAILABLE = True
    except ImportError:
        DEEPSEEK_AVAILABLE = False


class QAAgent:
    def __init__(self, data_dir: str = None, use_ai: bool = True):
        if data_dir is None:
            current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.data_dir = os.path.join(current_dir, 'DataProcessor', 'data')
        else:
            self.data_dir = data_dir
        
        self.project_cache = {}
        self.use_ai = use_ai and DEEPSEEK_AVAILABLE
        
        if self.use_ai:
            try:
                self.deepseek = DeepSeekClient()
                print("✓ DeepSeek AI 已启用")
            except Exception as e:
                print(f"⚠ DeepSeek 初始化失败，将使用规则匹配模式")
                self.use_ai = False
        else:
            self.deepseek = None
    
    def load_project_data(self, project_name: str) -> Optional[Dict]:
        if project_name in self.project_cache:
            return self.project_cache[project_name]
        
        project_path = os.path.join(self.data_dir, project_name)
        if not os.path.exists(project_path):
            return None
        
        processed_folders = [
            f for f in os.listdir(project_path) 
            if os.path.isdir(os.path.join(project_path, f)) and '_processed' in f
        ]
        
        if not processed_folders:
            return None
        
        latest_folder = sorted(processed_folders)[-1]
        processed_path = os.path.join(project_path, latest_folder)
        
        data = {}
        
        summary_path = os.path.join(processed_path, 'processing_summary.json')
        if os.path.exists(summary_path):
            with open(summary_path, 'r', encoding='utf-8') as f:
                data['summary'] = json.load(f)
        
        text_path = os.path.join(processed_path, 'text_data_structured.json')
        if os.path.exists(text_path):
            with open(text_path, 'r', encoding='utf-8') as f:
                data['text_data'] = json.load(f)
        
        timeseries_path = os.path.join(processed_path, 'timeseries_data.json')
        if os.path.exists(timeseries_path):
            with open(timeseries_path, 'r', encoding='utf-8') as f:
                data['timeseries'] = json.load(f)
        
        self.project_cache[project_name] = data
        return data
    
    def answer_question(self, question: str, project_name: str) -> Dict:
        data = self.load_project_data(project_name)
        if not data:
            return {
                'answer': f'抱歉，未找到项目 {project_name} 的数据。',
                'sources': [],
                'confidence': 0.0
            }
        
        if self.use_ai and self.deepseek:
            return self._answer_with_ai(data, question, project_name)
        
        return self._answer_with_rules(data, question)
    
    def _answer_with_ai(self, data: Dict, question: str, project_name: str) -> Dict:
        summary = data.get('summary', {})
        
        context_parts = [
            f"项目名称: {project_name}",
            f"文档总数: {summary.get('text_documents_count', 0)}",
            f"时序指标数: {summary.get('timeseries_metrics_count', 0)}"
        ]
        
        by_type = summary.get('text_documents_by_type', {})
        if by_type:
            context_parts.append("文档类型分布:")
            for doc_type, count in by_type.items():
                context_parts.append(f"  - {doc_type}: {count}")
        
        text_data = data.get('text_data', [])
        if text_data:
            context_parts.append("\n项目相关文本数据（部分）:")
            for i, doc in enumerate(text_data[:3]):
                doc_type = doc.get('type', 'unknown')
                content = doc.get('content', '')[:500]
                context_parts.append(f"\n文档{i+1} ({doc_type}):\n{content}")
        
        context = "\n".join(context_parts)
        
        try:
            answer = self.deepseek.ask(question, context)
            return {
                'answer': answer,
                'sources': ['DeepSeek AI 分析'],
                'confidence': 0.9
            }
        except Exception as e:
            return self._answer_with_rules(data, question)
    
    def _answer_with_rules(self, data: Dict, question: str) -> Dict:
        summary = data.get('summary', {})
        question_lower = question.lower()
        
        if any(kw in question_lower for kw in ['什么', '介绍', '描述', '基本信息']):
            return self._get_basic_info(data)
        
        if any(kw in question_lower for kw in ['多少', '数量', '统计']):
            return self._get_statistics(summary)
        
        if 'issue' in question_lower or '问题' in question_lower:
            return self._get_issues_info(data)
        
        return self._get_general_info(summary)
    
    def _get_basic_info(self, data: Dict) -> Dict:
        text_data = data.get('text_data', [])
        repo_info = next((doc for doc in text_data if doc.get('type') == 'repo_info'), None)
        
        if repo_info:
            content = repo_info.get('content', '')
            lines = [l.strip() for l in content.split('\n')[:10] if ':' in l]
            answer = "根据项目数据，\n" + "\n".join(lines[:5])
        else:
            summary = data.get('summary', {})
            answer = f"这是一个开源项目，已处理 {summary.get('text_documents_count', 0)} 个文档。"
        
        return {'answer': answer, 'sources': ['项目基本信息'], 'confidence': 0.8}
    
    def _get_statistics(self, summary: Dict) -> Dict:
        stats = [
            f"文档总数: {summary.get('text_documents_count', 0)}",
            f"时序指标数: {summary.get('timeseries_metrics_count', 0)}"
        ]
        
        by_type = summary.get('text_documents_by_type', {})
        if by_type:
            stats.append("文档类型分布:")
            for doc_type, count in by_type.items():
                stats.append(f"  - {doc_type}: {count}")
        
        return {
            'answer': "项目统计信息：\n" + "\n".join(stats),
            'sources': ['处理摘要'],
            'confidence': 0.9
        }
    
    def _get_issues_info(self, data: Dict) -> Dict:
        text_data = data.get('text_data', [])
        issues = [doc for doc in text_data if doc.get('type') == 'issue']
        
        if not issues:
            return {'answer': '该项目暂无Issue数据。', 'sources': [], 'confidence': 0.7}
        
        return {
            'answer': f"项目共有 {len(issues)} 个Issue。",
            'sources': [f'Issue数据（共{len(issues)}条）'],
            'confidence': 0.85
        }
    
    def _get_general_info(self, summary: Dict) -> Dict:
        answer = (
            f"关于这个项目：\n"
            f"- 已处理 {summary.get('text_documents_count', 0)} 个文档\n"
            f"- 包含 {summary.get('timeseries_metrics_count', 0)} 个时序指标\n\n"
            f"您可以询问：\n"
            f"- 项目的基本信息\n"
            f"- 统计数据\n"
            f"- Issue情况"
        )
        return {'answer': answer, 'sources': ['项目数据'], 'confidence': 0.6}
    
    def get_project_summary(self, project_name: str) -> Dict:
        data = self.load_project_data(project_name)
        if not data:
            return {'exists': False, 'name': project_name}
        
        summary = data.get('summary', {})
        
        return {
            'exists': True,
            'name': project_name,
            'repo': project_name,
            'documents_count': summary.get('text_documents_count', 0),
            'metrics_count': summary.get('timeseries_metrics_count', 0),
            'processed_at': summary.get('processed_at', ''),
            'documents_by_type': summary.get('text_documents_by_type', {})
        }
