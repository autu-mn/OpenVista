"""
OpenVista AI Agent 模块
用于项目数据问答和智能分析

支持的 AI 后端（按优先级）：
1. MaxKB - 使用 MAXKB_AI_API 环境变量配置
2. DeepSeek - 使用 DEEPSEEK_API_KEY 环境变量配置
"""

from .qa_agent import QAAgent
from .prediction_explainer import PredictionExplainer

try:
    from .maxkb_client import MaxKBClient, get_maxkb_client
except ImportError:
    MaxKBClient = None
    get_maxkb_client = None

try:
    from .deepseek_client import DeepSeekClient
except ImportError:
    DeepSeekClient = None

__all__ = [
    'QAAgent',
    'PredictionExplainer',
    'MaxKBClient',
    'get_maxkb_client',
    'DeepSeekClient',
]
