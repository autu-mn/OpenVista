"""
GitPulse - 多模态时序预测模块
使用 GitPulse 模型进行时序预测
"""

# 优先使用 prediction_service 中的预测器（更稳定）
try:
    from .prediction_service import GitPulsePredictor, get_prediction_service, PredictionService
    GITPULSE_AVAILABLE = True
except ImportError as e:
    # 如果依赖未安装，提供空实现
    GITPULSE_AVAILABLE = False
    
    class GitPulsePredictor:
        """GitPulse 预测器（未安装依赖时的占位类）"""
        def __init__(self, *args, **kwargs):
            raise ImportError(f"GitPulse 依赖未安装，请运行: pip install torch transformers numpy")
    
    def get_prediction_service():
        return None
    
    class PredictionService:
        def is_available(self):
            return False
        def get_error(self):
            return "GitPulse 依赖未安装"

__all__ = ['GitPulsePredictor', 'get_prediction_service', 'PredictionService', 'GITPULSE_AVAILABLE']
















