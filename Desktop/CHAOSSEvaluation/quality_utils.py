"""
数据质量评估和归一化工具函数
"""
import math
from typing import List, Dict, Optional
from .chaoss_metric_config import MetricConfig, MetricType


def evaluate_data_quality(values: List[float], config: MetricConfig) -> Dict:
    """
    评估数据质量
    
    Args:
        values: 指标值列表
        config: 指标配置
        
    Returns:
        {
            'clean': List[float],      # 清洗后的数据
            'quality': float,           # 质量得分 0~1
            'outliers': int,           # 异常值数量
            'zero_ratio': float        # 零值比例
        }
    """
    if len(values) < 3:
        return {
            'clean': values,
            'quality': 0.3,
            'outliers': 0,
            'zero_ratio': 0.0
        }
    
    # 过滤无效值
    valid_values = [
        v for v in values
        if v is not None
        and isinstance(v, (int, float))
        and not (math.isnan(v) or math.isinf(v))
        and v >= 0
    ]
    
    if not valid_values:
        return {
            'clean': [],
            'quality': 0.0,
            'outliers': 0,
            'zero_ratio': 1.0
        }
    
    # 计算IQR和异常值
    sorted_values = sorted(valid_values)
    n = len(sorted_values)
    
    if n < 4:
        # 数据点太少，直接返回
        zero_count = sum(1 for v in valid_values if v == 0)
        zero_ratio = zero_count / n if n > 0 else 0.0
        quality = max(0.1, 1.0 - zero_ratio * 0.5)
        return {
            'clean': valid_values,
            'quality': round(quality, 2),
            'outliers': 0,
            'zero_ratio': zero_ratio
        }
    
    # 计算分位数
    q1_idx = int(n * 0.25)
    q3_idx = int(n * 0.75)
    q1 = sorted_values[q1_idx]
    q3 = sorted_values[q3_idx]
    iqr = q3 - q1
    
    # 使用配置的IQR倍数
    multiplier = config.iqr_multiplier
    lower_bound = q1 - multiplier * iqr if iqr > 0 else q1
    upper_bound = q3 + multiplier * iqr if iqr > 0 else q3
    
    # 识别异常值
    clean_values = []
    outliers = 0
    for v in valid_values:
        if iqr > 0 and (v < lower_bound or v > upper_bound):
            outliers += 1
        else:
            clean_values.append(v)
    
    # 如果清洗后数据太少，保留原始数据
    if len(clean_values) < len(valid_values) * 0.5:
        clean_values = valid_values
        outliers = 0
    
    # 计算零值比例
    zero_count = sum(1 for v in clean_values if v == 0)
    zero_ratio = zero_count / len(clean_values) if clean_values else 0.0
    
    # 计算质量得分
    quality = 1.0
    # 异常值惩罚（最多扣40%）
    if len(valid_values) > 0:
        outlier_ratio = outliers / len(valid_values)
        quality -= min(0.4, outlier_ratio)
    # 零值过多惩罚（超过30%开始扣分，最多扣30%）
    if zero_ratio > 0.3:
        quality -= min(0.3, (zero_ratio - 0.3) * 0.5)
    
    quality = max(0.1, round(quality, 2))
    
    return {
        'clean': clean_values,
        'quality': quality,
        'outliers': outliers,
        'zero_ratio': zero_ratio
    }


def apply_quality_penalty(score: float, quality: float) -> float:
    """
    用"折损"而不是"乘法"应用数据质量
    - quality ∈ [0,1]
    - 最多扣 30%，避免系统性压分
    
    Args:
        score: 归一化后的得分
        quality: 数据质量得分 (0-1)
        
    Returns:
        应用质量折损后的得分
    """
    return score * (0.7 + 0.3 * quality)


def normalize_with_baseline(value: float, baseline: float) -> float:
    """
    baseline ≈ "健康但不优秀" → 对应 ~60 分
    
    Args:
        value: 当前值
        baseline: 基准值（健康水平）
        
    Returns:
        归一化后的得分 (0-100)
    """
    if value <= 0:
        return 20.0
    
    ratio = value / baseline
    
    if ratio >= 2.0:
        return min(100.0, 85 + (ratio - 2.0) * 5)
    elif ratio >= 1.0:
        return 60 + 25 * (ratio - 1.0)
    else:
        return 60 * ratio


def normalize_value(
    value: float,
    config: MetricConfig,
    historical_values: Optional[List[float]] = None,
    ref: Optional[Dict] = None
) -> float:
    """
    归一化指标值到0-100分
    
    支持三种归一化策略（按优先级）：
    1. 百分位归一化（如果配置了use_percentile）
    2. 基准值归一化（如果配置了baseline）
    3. 对数尺度归一化（如果配置了log_scale）
    4. 回退到简单线性归一化
    
    Args:
        value: 当前值
        config: 指标配置
        historical_values: 历史值列表（用于计算百分位）
        ref: 参考值字典（可包含p75等预计算的百分位值）
        
    Returns:
        归一化后的得分（0-100）
    """
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return 0.0
    
    if value < 0:
        return 0.0
    
    score = 0.0
    
    # 策略1: 百分位归一化
    if config.use_percentile and historical_values:
        clean_vals = [v for v in historical_values if v is not None and v >= 0 
                     and not (isinstance(v, float) and (math.isnan(v) or math.isinf(v)))]
        if clean_vals:
            sorted_vals = sorted(clean_vals)
            n = len(sorted_vals)
            p75_idx = int(n * config.percentile_ref / 100)
            p75_idx = min(p75_idx, n - 1)
            p75_value = sorted_vals[p75_idx] if sorted_vals[p75_idx] > 0 else sorted_vals[-1]
            
            if p75_value > 0:
                # 使用75%分位数作为参考，值达到p75时得70分
                ratio = value / p75_value
                score = min(100, ratio * 70)
            else:
                score = 0.0
        elif ref and 'p75' in ref and ref['p75'] > 0:
            ratio = value / ref['p75']
            score = min(100, ratio * 70)
        else:
            score = 0.0
    
    # 策略2: 基准值归一化（改进：baseline作为60分锚点）
    elif config.baseline and config.baseline > 0:
        score = normalize_with_baseline(value, config.baseline)
    
    # 策略3: 对数尺度归一化
    elif config.log_scale:
        # 使用对数尺度：log10(1 + value) * 50
        # 这样可以让大值和小值之间的差距更合理
        if value > 0:
            log_value = math.log10(1 + value)
            score = min(100, log_value * 50)
        else:
            score = 0.0
    
    # 策略4: 简单线性归一化（回退）
    else:
        if historical_values:
            clean_vals = [v for v in historical_values if v is not None and v >= 0 
                         and not (isinstance(v, float) and (math.isnan(v) or math.isinf(v)))]
            if clean_vals:
                max_value = max(clean_vals)
                if max_value > 0:
                    score = min(100, (value / max_value) * 100)
                else:
                    score = 0.0
            else:
                score = 0.0
        else:
            # 如果没有历史数据，使用简单的对数映射
            if value > 0:
                score = min(100, math.log10(1 + value) * 50)
            else:
                score = 0.0
    
    # 如果指标是"越小越好"类型（如Bus Factor），需要反转
    if not config.higher_is_better:
        score = 100.0 - score
    
    return round(max(0.0, min(100.0, score)), 1)


def calculate_percentile_reference(historical_values: List[float], percentile: float = 75.0) -> Dict:
    """
    计算历史数据的百分位参考值
    
    Args:
        historical_values: 历史值列表
        percentile: 百分位数（默认75%）
        
    Returns:
        包含百分位值的字典
    """
    clean_vals = [v for v in historical_values 
                 if v is not None and v >= 0 
                 and not (isinstance(v, float) and (math.isnan(v) or math.isinf(v)))]
    
    if not clean_vals:
        return {'p75': 0.0}
    
    sorted_vals = sorted(clean_vals)
    n = len(sorted_vals)
    idx = int(n * percentile / 100)
    idx = min(idx, n - 1)
    
    return {
        'p75': sorted_vals[idx] if sorted_vals[idx] > 0 else sorted_vals[-1] if sorted_vals else 0.0
    }

