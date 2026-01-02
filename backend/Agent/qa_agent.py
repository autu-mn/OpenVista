"""
问答 Agent - 基于项目数据提供智能问答
支持 MaxKB AI API
"""
import os
import json
import logging
from typing import Dict, Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# 尝试导入 AI 客户端
MAXKB_AVAILABLE = False

try:
    from .maxkb_client import MaxKBClient, get_maxkb_client
    MAXKB_AVAILABLE = True
except ImportError:
    try:
        from maxkb_client import MaxKBClient, get_maxkb_client
        MAXKB_AVAILABLE = True
    except ImportError:
        pass


class QAAgent:
    """问答 Agent - 支持多种 AI 后端"""
    
    def __init__(self, data_dir: str = None, use_ai: bool = True):
        """
        初始化问答 Agent
        
        Args:
            data_dir: 数据目录
            use_ai: 是否启用 AI（优先使用 MaxKB，回退到 DeepSeek）
        """
        if data_dir is None:
            current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.data_dir = os.path.join(current_dir, 'DataProcessor', 'data')
        else:
            self.data_dir = data_dir
        
        self.project_cache = {}
        self.use_ai = use_ai
        self.ai_client = None
        self.ai_type = None
        
        if self.use_ai:
            self._init_ai_client()
    
    def _init_ai_client(self):
        """初始化 AI 客户端（使用 MaxKB）"""
        if MAXKB_AVAILABLE:
            try:
                self.ai_client = get_maxkb_client()
                if self.ai_client:
                    self.ai_type = 'MaxKB'
                    logger.info("[QAAgent] 使用 MaxKB AI 作为后端")
                    print("[OK] MaxKB AI 已启用")
                    return
            except Exception as e:
                logger.warning(f"[QAAgent] MaxKB 初始化失败: {e}")
                print(f"[WARN] MaxKB 初始化失败: {e}")
        
        # MaxKB 不可用，使用规则匹配模式
        logger.warning("[QAAgent] MaxKB 未配置或初始化失败，将使用规则匹配模式")
        print("[WARN] MaxKB 未启用，AI 助手将使用规则匹配模式")
        print("  请配置环境变量: MAXKB_AI_URL 和 MAXKB_API_KEY")
        self.use_ai = False
    
    def load_project_data(self, project_name: str) -> Optional[Dict]:
        """加载项目数据"""
        if project_name in self.project_cache:
            return self.project_cache[project_name]
        
        project_path = os.path.join(self.data_dir, project_name)
        if not os.path.exists(project_path):
            logger.debug(f"[QAAgent] 项目目录不存在: {project_path}")
            return None
        
        # 支持两种格式：_processed 和 monthly_data_
        processed_folders = [
            f for f in os.listdir(project_path) 
            if os.path.isdir(os.path.join(project_path, f)) and ('_processed' in f or 'monthly_data_' in f)
        ]
        
        if not processed_folders:
            logger.debug(f"[QAAgent] 未找到处理后的数据文件夹: {project_path}")
            return None
        
        latest_folder = sorted(processed_folders)[-1]
        processed_path = os.path.join(project_path, latest_folder)
        
        data = {}
        
        # 尝试加载 processing_summary.json（旧格式）
        summary_path = os.path.join(processed_path, 'processing_summary.json')
        if os.path.exists(summary_path):
            with open(summary_path, 'r', encoding='utf-8') as f:
                data['summary'] = json.load(f)
        
        # 尝试加载 project_summary.json（新格式）
        project_summary_path = os.path.join(processed_path, 'project_summary.json')
        if os.path.exists(project_summary_path):
            with open(project_summary_path, 'r', encoding='utf-8') as f:
                project_summary = json.load(f)
                # 转换为旧格式兼容
                if 'summary' not in data:
                    data['summary'] = {}
                data['summary']['text_documents_count'] = len(project_summary.get('issue_stats', {}))
                data['summary']['timeseries_metrics_count'] = 18  # OpenDigger指标数量
                data['summary']['processed_at'] = project_summary.get('data_range', {}).get('end', '')
                data['project_summary'] = project_summary
        
        # 尝试加载 text_data_structured.json（旧格式）
        text_path = os.path.join(processed_path, 'text_data_structured.json')
        if os.path.exists(text_path):
            with open(text_path, 'r', encoding='utf-8') as f:
                data['text_data'] = json.load(f)
        
        timeseries_path = os.path.join(processed_path, 'timeseries_data.json')
        if os.path.exists(timeseries_path):
            with open(timeseries_path, 'r', encoding='utf-8') as f:
                data['timeseries'] = json.load(f)
        
        self.project_cache[project_name] = data
        logger.info(f"[QAAgent] 加载项目数据: {project_name}")
        return data
    
    def answer_question(self, question: str, project_name: str) -> Dict:
        """回答问题"""
        data = self.load_project_data(project_name)
        if not data:
            return {
                'answer': f'抱歉，未找到项目 {project_name} 的数据。',
                'sources': [],
                'confidence': 0.0
            }
        
        if self.use_ai and self.ai_client:
            return self._answer_with_ai(data, question, project_name)
        
        return self._answer_with_rules(data, question)
    
    def _answer_with_ai(self, data: Dict, question: str, project_name: str) -> Dict:
        """使用 MaxKB AI 回答问题 - 完全依赖 MaxKB 知识库"""
        try:
            # 直接发送用户问题给 MaxKB
            # MaxKB 会使用其配置的知识库、系统提示词和用户提示词模板
            answer = self.ai_client.ask(question)
            
            # 检查是否返回了错误消息
            if answer.startswith('抱歉') or 'AI 调用失败' in answer or 'Exception' in answer:
                logger.warning(f"[QAAgent] MaxKB 返回错误，回退到本地数据: {answer[:100]}")
                return self._answer_with_local_data(data, question, project_name)
            
            return {
                'answer': answer,
                'sources': ['MaxKB 知识库'],
                'confidence': 0
            }
        except Exception as e:
            logger.error(f"[QAAgent] AI 调用失败: {e}")
            return self._answer_with_local_data(data, question, project_name)
    
    def _answer_with_local_data(self, data: Dict, question: str, project_name: str) -> Dict:
        """基于本地数据生成详细回答（MaxKB 不可用时的备用方案）"""
        project_summary = data.get('project_summary', {})
        summary = data.get('summary', {})
        
        # 提取项目信息
        repo_info = project_summary.get('repo_info', {})
        data_range = project_summary.get('data_range', {})
        issue_stats = project_summary.get('issue_stats', {})
        
        # 构建详细回答
        parts = []
        
        # 项目基本信息
        display_name = project_name.replace('_', '/')
        description = repo_info.get('description', '')
        language = repo_info.get('language', '未知')
        stars = repo_info.get('stargazers_count', repo_info.get('stars', 0))
        forks = repo_info.get('forks_count', repo_info.get('forks', 0))
        
        parts.append(f"## {display_name} 项目分析\n")
        
        if description:
            parts.append(f"**项目描述**: {description}\n")
        
        parts.append(f"**主要语言**: {language}")
        parts.append(f"**Star 数**: {stars:,}")
        parts.append(f"**Fork 数**: {forks:,}")
        
        # 数据范围
        if data_range:
            start = data_range.get('start', '?')
            end = data_range.get('end', '?')
            parts.append(f"\n**数据时间范围**: {start} 至 {end}")
        
        # Issue 统计
        if issue_stats:
            parts.append("\n### Issue 分类统计")
            total_issues = sum(issue_stats.values()) if isinstance(issue_stats, dict) else 0
            parts.append(f"- 抽样总数: {total_issues}")
            if isinstance(issue_stats, dict):
                for category, count in issue_stats.items():
                    if count > 0:
                        parts.append(f"- {category}: {count}")
        
        # AI 摘要（如果有）
        ai_summary = project_summary.get('aiSummary', project_summary.get('ai_summary', ''))
        if ai_summary:
            parts.append(f"\n### AI 项目摘要\n{ai_summary}")
        
        # 根据问题类型添加更多信息
        question_lower = question.lower()
        if '特点' in question_lower or '特色' in question_lower or '功能' in question_lower:
            parts.append("\n### 主要特点")
            parts.append("根据项目数据分析，该项目具有活跃的社区参与和持续的开发活动。")
            parts.append(f"项目使用 {language} 作为主要开发语言，拥有 {stars:,} 个 Star。")
        
        if '趋势' in question_lower or '发展' in question_lower:
            parts.append("\n### 发展趋势")
            parts.append("请查看时序分析图表获取详细的发展趋势数据。")
        
        answer = "\n".join(parts)
        
        return {
            'answer': answer,
            'sources': ['本地项目数据'],
            'confidence': 0
        }
    
    def _answer_with_rules(self, data: Dict, question: str) -> Dict:
        """使用规则匹配回答问题"""
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
        """获取基本信息"""
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
        """获取统计信息"""
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
        """获取 Issue 信息"""
        text_data = data.get('text_data', [])
        issues = [doc for doc in text_data if doc.get('type') == 'issue']
        
        if not issues:
            return {'answer': '该项目暂无 Issue 数据。', 'sources': [], 'confidence': 0.7}
        
        return {
            'answer': f"项目共有 {len(issues)} 个 Issue。",
            'sources': [f'Issue 数据（共 {len(issues)} 条）'],
            'confidence': 0.85
        }
    
    def _get_general_info(self, summary: Dict) -> Dict:
        """获取通用信息"""
        answer = (
            f"关于这个项目：\n"
            f"- 已处理 {summary.get('text_documents_count', 0)} 个文档\n"
            f"- 包含 {summary.get('timeseries_metrics_count', 0)} 个时序指标\n\n"
            f"您可以询问：\n"
            f"- 项目的基本信息\n"
            f"- 统计数据\n"
            f"- Issue 情况"
        )
        return {'answer': answer, 'sources': ['项目数据'], 'confidence': 0.6}
    
    def get_project_summary(self, project_name: str) -> Dict:
        """获取项目摘要"""
        data = self.load_project_data(project_name)
        if not data:
            return {'exists': False, 'name': project_name}
        
        summary = data.get('summary', {})
        project_summary = data.get('project_summary', {})
        
        # 如果有新格式的项目摘要，优先使用
        if project_summary:
            repo_info = project_summary.get('repo_info', {})
            return {
                'exists': True,
                'name': project_name,
                'repo': project_name,
                'full_name': repo_info.get('full_name', project_name),
                'description': repo_info.get('description', ''),
                'language': repo_info.get('language', ''),
                'stars': repo_info.get('stargazers_count', repo_info.get('stars', 0)),
                'documents_count': len(project_summary.get('issue_stats', {})),
                'metrics_count': summary.get('timeseries_metrics_count', 18),
                'processed_at': project_summary.get('data_range', {}).get('end', ''),
                'documents_by_type': project_summary.get('issue_stats', {})
            }
        
        return {
            'exists': True,
            'name': project_name,
            'repo': project_name,
            'documents_count': summary.get('text_documents_count', 0),
            'metrics_count': summary.get('timeseries_metrics_count', 0),
            'processed_at': summary.get('processed_at', ''),
            'documents_by_type': summary.get('text_documents_by_type', {})
        }
