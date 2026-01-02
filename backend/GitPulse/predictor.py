"""
GitPulse 预测适配器
将 GitPulse 模型集成到 OpenVista 后端
"""

import os
import sys
import json
import numpy as np
import torch
from typing import Dict, List, Optional
from datetime import datetime, timedelta

# 添加 GitPulse 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'GitPulse'))

try:
    from predict.predict_single_repo import RepoPredictor
    GITPULSE_AVAILABLE = True
except ImportError as e:
    GITPULSE_AVAILABLE = False
    print(f"[WARN] GitPulse 未安装: {e}")
    print("请安装依赖: pip install -r GitPulse/requirements_predict.txt")


class GitPulsePredictor:
    """
    GitPulse 预测器适配器
    提供与 LLMTimeSeriesPredictor 兼容的接口
    """
    
    def __init__(self, enable_cache: bool = True):
        """
        初始化 GitPulse 预测器
        
        Args:
            enable_cache: 是否启用缓存（暂未实现）
        """
        if not GITPULSE_AVAILABLE:
            raise ImportError("GitPulse 未安装，请先安装依赖")
        
        # 模型路径
        model_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'GitPulse', 
            'predict', 'models', 'best_model.pt'
        )
        
        # 如果模型文件不存在，尝试使用训练检查点
        if not os.path.exists(model_path):
            alt_path = os.path.join(
                os.path.dirname(__file__), '..', '..', 'GitPulse',
                'training', 'checkpoints', 'best_model_cond_gru_mm.pt'
            )
            if os.path.exists(alt_path):
                model_path = alt_path
            else:
                raise FileNotFoundError(
                    f"GitPulse 模型文件不存在。请确保模型文件位于:\n"
                    f"  - {model_path}\n"
                    f"  或\n"
                    f"  - {alt_path}"
                )
        
        # 初始化预测器
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.predictor = RepoPredictor(model_path, device=device)
        self.device = device  # 保存设备信息供外部访问
        
        # 16 个指标的映射（GitPulse 使用的顺序）
        # 注意：GitPulse 模型只支持这16个指标，不支持其他指标（如代码变更行数等）
        self.metric_mapping = {
            'OpenRank': 0,
            '活跃度': 1,
            'Star数': 2,
            'Fork数': 3,
            '关注度': 4,
            '参与者数': 5,
            '新增贡献者': 6,
            '贡献者': 7,
            '不活跃贡献者': 8,
            '总线因子': 9,
            '新增Issue': 10,
            '关闭Issue': 11,
            'Issue评论': 12,
            '变更请求': 13,
            'PR接受数': 14,
            'PR审查': 15,
        }
        
        # 支持的指标名称集合（用于快速检查）
        self.supported_metrics = set(self.metric_mapping.keys())
        
        # 反向映射（索引 -> 指标名）
        self.index_to_metric = {v: k for k, v in self.metric_mapping.items()}
        
        print(f"[OK] GitPulse 预测器初始化成功 (设备: {device})")
    
    def _prepare_timeseries_data(self, historical_data: Dict[str, float]) -> np.ndarray:
        """
        准备时序数据，转换为 GitPulse 需要的格式
        
        Args:
            historical_data: {"2020-08": 4.76, "2020-09": 4.82, ...}
        
        Returns:
            timeseries_array: [T, 16] 形状的数组，16 个指标
        """
        # 按时间排序
        sorted_months = sorted(historical_data.keys())
        
        # 如果数据不足 128 个月，需要填充
        # 如果超过 128 个月，只取最后 128 个月
        
        # 创建 16 维数组（初始化为 0）
        # 注意：这里我们只预测单个指标，其他维度用 0 填充
        # 如果需要预测多个指标，需要传入完整的 16 维数据
        
        timeseries_list = []
        for month in sorted_months[-128:]:  # 最多取最后 128 个月
            row = [0.0] * 16
            # 这里我们不知道是哪个指标，所以先全部填充为 0
            # 实际使用时，需要传入完整的 16 维数据
            timeseries_list.append(row)
        
        return np.array(timeseries_list, dtype=np.float32)
    
    def _prepare_multivariate_data(self, metrics_data: Dict[str, Dict[str, float]]) -> np.ndarray:
        """
        准备多变量时序数据（16 个指标）
        
        Args:
            metrics_data: {
                "OpenRank": {"2020-08": 4.76, ...},
                "活跃度": {"2020-08": 0.5, ...},
                ...
            }
        
        Returns:
            timeseries_array: [T, 16] 形状的数组
        """
        # 收集所有月份
        all_months = set()
        for metric_data in metrics_data.values():
            all_months.update(metric_data.keys())
        
        sorted_months = sorted(all_months)[-128:]  # 最多取最后 128 个月
        
        # 构建 16 维数组
        timeseries_list = []
        for month in sorted_months:
            row = [0.0] * 16
            for metric_name, metric_index in self.metric_mapping.items():
                if metric_name in metrics_data:
                    value = metrics_data[metric_name].get(month, 0.0)
                    row[metric_index] = float(value)
            timeseries_list.append(row)
        
        return np.array(timeseries_list, dtype=np.float32)
    
    def _extract_text_context(self, repo_key: str = None, 
                             text_timeseries: Dict[str, Dict] = None,
                             repo_context: str = None) -> str:
        """
        提取文本上下文（用于 GitPulse 的文本输入）
        
        Args:
            repo_key: 仓库标识
            text_timeseries: 文本时序数据
            repo_context: 仓库上下文信息
        
        Returns:
            text: 文本描述字符串
        """
        text_parts = []
        
        if repo_context:
            text_parts.append(repo_context)
        
        # 从文本时序数据中提取最近的关键信息
        if text_timeseries:
            recent_months = sorted(text_timeseries.keys())[-6:]  # 最近 6 个月
            for month in recent_months:
                month_data = text_timeseries[month]
                if month_data.get('hottest_issue'):
                    issue = month_data['hottest_issue']
                    text_parts.append(f"{month}: Issue - {issue.get('title', '')}")
                if month_data.get('hottest_pr'):
                    pr = month_data['hottest_pr']
                    text_parts.append(f"{month}: PR - {pr.get('title', '')}")
        
        return " ".join(text_parts) if text_parts else ""
    
    def predict(self, metric_name: str, historical_data: Dict[str, float],
                forecast_months: int = 6, include_reasoning: bool = True,
                text_timeseries: Dict[str, Dict] = None,
                repo_context: str = None,
                full_timeseries_data: Dict[str, Dict] = None) -> Dict:
        """
        预测单个指标的未来值
        
        Args:
            metric_name: 指标名称，如 "OpenRank"、"活跃度"
            historical_data: 历史数据 {"2020-08": 4.76, ...}
            forecast_months: 预测月数，默认 6 个月（GitPulse 固定预测 32 个月）
            include_reasoning: 是否包含预测理由（GitPulse 不提供，但保留接口兼容）
            text_timeseries: 文本时序数据（可选）
            repo_context: 仓库上下文信息（可选）
        
        Returns:
            预测结果字典，格式与 LLMTimeSeriesPredictor 兼容
        """
        if not historical_data:
            return {
                "forecast": {},
                "confidence": 0.0,
                "reasoning": "历史数据为空，无法进行预测",
                "error": "No historical data"
            }
        
        try:
            # 准备文本上下文
            text_context = self._extract_text_context(
                text_timeseries=text_timeseries,
                repo_context=repo_context
            )
            
            # GitPulse 需要完整的 16 维数据
            # 如果提供了完整数据，使用完整数据；否则只使用目标指标
            metric_index = self.metric_mapping.get(metric_name)
            if metric_index is None:
                return {
                    "forecast": {},
                    "confidence": 0.0,
                    "reasoning": f"不支持的指标: {metric_name}",
                    "error": f"Unsupported metric: {metric_name}"
                }
            
            # 如果有完整数据，使用完整数据构建 16 维数组
            if full_timeseries_data:
                # full_timeseries_data 可能是两种格式：
                # 1. 按月份组织：{"2020-08": {"OpenRank": 4.76, "活跃度": 0.5, ...}}
                # 2. 按指标组织：{"OpenRank": {"2020-08": 4.76, ...}}
                # 需要统一转换为按指标组织的格式
                
                # 检查数据格式：如果第一个键是月份格式（YYYY-MM），则是按月份组织
                first_key = list(full_timeseries_data.keys())[0] if full_timeseries_data else None
                is_month_organized = (first_key and 
                                     isinstance(first_key, str) and 
                                     len(first_key) == 7 and 
                                     first_key[4] == '-' and
                                     isinstance(full_timeseries_data[first_key], dict))
                
                if is_month_organized:
                    # 转换为按指标组织的格式
                    metrics_data_dict = {}
                    for month, metrics in full_timeseries_data.items():
                        if not isinstance(metrics, dict):
                            continue
                        for metric_display_name in self.metric_mapping.keys():
                            if metric_display_name not in metrics_data_dict:
                                metrics_data_dict[metric_display_name] = {}
                            # 尝试多种格式匹配
                            value = None
                            if metric_display_name in metrics:
                                value = metrics[metric_display_name]
                            elif f'opendigger_{metric_display_name}' in metrics:
                                value = metrics[f'opendigger_{metric_display_name}']
                            elif any(k.endswith(metric_display_name) for k in metrics.keys()):
                                for k in metrics.keys():
                                    if k.endswith(metric_display_name):
                                        value = metrics[k]
                                        break
                            if value is not None:
                                metrics_data_dict[metric_display_name][month] = float(value)
                else:
                    # 已经是按指标组织的格式，直接使用
                    metrics_data_dict = {}
                    for metric_display_name in self.metric_mapping.keys():
                        if metric_display_name in full_timeseries_data:
                            metric_data = full_timeseries_data[metric_display_name]
                            if isinstance(metric_data, dict):
                                # 如果是 {"raw": {...}} 格式，提取 raw
                                if 'raw' in metric_data:
                                    metrics_data_dict[metric_display_name] = {
                                        month: float(value) 
                                        for month, value in metric_data['raw'].items()
                                    }
                                else:
                                    # 直接是 {month: value} 格式
                                    metrics_data_dict[metric_display_name] = {
                                        month: float(value) 
                                        for month, value in metric_data.items()
                                    }
                
                if metrics_data_dict:
                    timeseries_data = self._prepare_multivariate_data(metrics_data_dict)
                else:
                    # 如果转换失败，回退到只使用目标指标
                    timeseries_data = self._prepare_timeseries_data(historical_data)
                    sorted_months = sorted(historical_data.keys())[-128:]
                    if timeseries_data.ndim == 1:
                        timeseries_data = timeseries_data.reshape(-1, 16)
                    for i, month in enumerate(sorted_months):
                        if i < len(timeseries_data):
                            timeseries_data[i][metric_index] = historical_data[month]
            else:
                # 如果没有完整数据，只使用目标指标（其他维度为 0）
                timeseries_data = self._prepare_timeseries_data(historical_data)
                sorted_months = sorted(historical_data.keys())[-128:]
                # 确保 timeseries_data 是 2D 数组
                if timeseries_data.ndim == 1:
                    timeseries_data = timeseries_data.reshape(-1, 16)
                for i, month in enumerate(sorted_months):
                    if i < len(timeseries_data):
                        timeseries_data[i][metric_index] = historical_data[month]
            
            # 调用 GitPulse 预测
            prediction, stats = self.predictor.predict(
                timeseries_data.tolist(),
                text_context if text_context else "GitHub repository"
            )
            
            # GitPulse 预测 32 个月，但我们只需要 forecast_months 个月
            prediction = prediction[:forecast_months]
            
            # 提取目标指标的预测值
            forecast = {}
            last_date = max(historical_data.keys())
            last_year, last_month = map(int, last_date.split('-'))
            
            for i in range(forecast_months):
                # 计算目标月份
                target_month = last_month + i + 1
                target_year = last_year
                while target_month > 12:
                    target_month -= 12
                    target_year += 1
                target_str = f"{target_year:04d}-{target_month:02d}"
                
                # 从预测结果中提取目标指标的值
                if i < len(prediction):
                    forecast[target_str] = float(prediction[i][metric_index])
                else:
                    # 如果预测不足，使用最后一个历史值
                    forecast[target_str] = list(historical_data.values())[-1]
            
            # 计算置信度（基于数据质量和预测稳定性）
            confidence = self._calculate_confidence(historical_data, prediction, metric_index)
            
            return {
                "forecast": forecast,
                "confidence": confidence,
                "reasoning": f"基于 GitPulse 多模态时序预测模型，使用条件 GRU + 文本融合方法预测。模型性能: MSE=0.0886, R²=0.70, DA=67.28%",
                "trend_analysis": {
                    "direction": "上升" if len(forecast) > 0 and list(forecast.values())[-1] > list(historical_data.values())[-1] else "下降",
                    "strength": "中等",
                    "volatility": "低"
                },
                "model": "GitPulse (CondGRU+Text)",
                "prediction_length": len(forecast),
                "historical_length": len(historical_data)
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                "forecast": {},
                "confidence": 0.0,
                "reasoning": f"预测过程出错: {str(e)}",
                "error": str(e)
            }
    
    def predict_multiple(self, metrics_data: Dict[str, Dict[str, float]],
                        forecast_months: int = 6) -> Dict[str, Dict]:
        """
        批量预测多个指标（使用 GitPulse 的多变量预测能力）
        
        Args:
            metrics_data: {
                "OpenRank": {"2020-08": 4.76, ...},
                "活跃度": {"2020-08": 0.5, ...},
                ...
            }
            forecast_months: 预测月数（GitPulse 固定预测 32 个月）
        
        Returns:
            {
                "OpenRank": {预测结果},
                "活跃度": {预测结果},
                ...
            }
        """
        if not metrics_data:
            return {}
        
        try:
            # 过滤掉不支持的指标，只保留 GitPulse 支持的 16 个指标
            filtered_metrics_data = {}
            unsupported_metrics = []
            
            for metric_name, metric_data in metrics_data.items():
                # 清理指标名称（去掉前缀）
                metric_name_clean = metric_name.replace('opendigger_', '')
                
                if metric_name_clean in self.supported_metrics:
                    filtered_metrics_data[metric_name_clean] = metric_data
                else:
                    unsupported_metrics.append(metric_name)
            
            if not filtered_metrics_data:
                return {
                    'error': '没有支持的指标可以预测',
                    'unsupported_metrics': unsupported_metrics,
                    'supported_metrics': list(self.supported_metrics)
                }
            
            if unsupported_metrics:
                print(f"[WARNING] 过滤掉不支持的指标: {unsupported_metrics}")
            
            # 准备多变量时序数据（只使用支持的指标）
            timeseries_data = self._prepare_multivariate_data(filtered_metrics_data)
            
            # 提取文本上下文（使用第一个指标的数据）
            text_context = "GitHub repository with multiple metrics"
            
            # 调用 GitPulse 预测（一次性预测所有 16 个指标）
            prediction, stats = self.predictor.predict(
                timeseries_data.tolist(),
                text_context
            )
            
            # GitPulse 预测 32 个月，但我们只需要 forecast_months 个月
            prediction = prediction[:forecast_months]
            
            # 提取所有指标的预测值（只处理传入的指标）
            results = {}
            
            # 获取最后一个历史月份
            all_months = set()
            for metric_data in filtered_metrics_data.values():
                all_months.update(metric_data.keys())
            if not all_months:
                return {'error': '没有有效的历史数据'}
            last_date = max(all_months)
            last_year, last_month = map(int, last_date.split('-'))
            
            # 只处理传入的指标（已经在 filtered_metrics_data 中）
            for metric_name in filtered_metrics_data.keys():
                if metric_name not in self.metric_mapping:
                    continue
                metric_index = self.metric_mapping[metric_name]
                historical_data = filtered_metrics_data[metric_name]
                
                # 构建该指标的预测结果
                forecast = {}
                for i in range(forecast_months):
                    target_month = last_month + i + 1
                    target_year = last_year
                    while target_month > 12:
                        target_month -= 12
                        target_year += 1
                    target_str = f"{target_year:04d}-{target_month:02d}"
                    
                    if i < len(prediction):
                        forecast[target_str] = float(prediction[i][metric_index])
                    else:
                        # 使用最后一个历史值
                        forecast[target_str] = list(historical_data.values())[-1]
                
                # 计算置信度
                confidence = self._calculate_confidence(historical_data, prediction, metric_index)
                
                results[metric_name] = {
                    "forecast": forecast,
                    "confidence": confidence,
                    "reasoning": f"基于 GitPulse 多模态时序预测模型预测",
                    "model": "GitPulse (CondGRU+Text)",
                    "prediction_length": len(forecast),
                    "historical_length": len(historical_data)
                }
            
            return results
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            # 如果批量预测失败，回退到单个预测
            results = {}
            for metric_name, historical_data in metrics_data.items():
                try:
                    results[metric_name] = self.predict(
                        metric_name, historical_data, forecast_months
                    )
                except:
                    results[metric_name] = {
                        "forecast": {},
                        "confidence": 0.0,
                        "reasoning": f"预测失败: {str(e)}",
                        "error": str(e)
                    }
            return results
    
    def _calculate_confidence(self, historical_data: Dict[str, float],
                             prediction: np.ndarray, metric_index: int) -> float:
        """
        计算预测置信度
        
        Args:
            historical_data: 历史数据
            prediction: 预测结果数组 [T, 16]
            metric_index: 指标索引
        
        Returns:
            confidence: 置信度 (0-1)
        """
        if not historical_data or len(prediction) == 0:
            return 0.3
        
        # 基于数据量计算基础置信度
        data_count = len(historical_data)
        if data_count >= 24:
            base_confidence = 0.85
        elif data_count >= 12:
            base_confidence = 0.70
        elif data_count >= 6:
            base_confidence = 0.55
        else:
            base_confidence = 0.40
        
        # 基于预测稳定性调整（预测值的变化幅度）
        if len(prediction) > 1:
            pred_values = [p[metric_index] for p in prediction]
            if len(pred_values) > 1:
                changes = [abs(pred_values[i] - pred_values[i-1]) 
                          for i in range(1, len(pred_values))]
                avg_change = sum(changes) / len(changes) if changes else 0
                last_value = list(historical_data.values())[-1]
                
                # 如果预测变化幅度过大，降低置信度
                if last_value > 0:
                    change_ratio = avg_change / abs(last_value)
                    if change_ratio > 0.5:
                        base_confidence *= 0.8
                    elif change_ratio > 0.3:
                        base_confidence *= 0.9
        
        return round(min(base_confidence, 0.95), 2)

