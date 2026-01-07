"""
CHAOSS 指标配置模块
定义每个指标的类型、权重、归一化规则等
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class MetricType(Enum):
    """指标类型枚举"""
    COUNT = "count"          # 计数类（PR数、Issue数等）
    RATE = "rate"            # 比率类（接受率、关闭率等）
    TIME = "time"            # 时间类（响应时间等）
    GROWTH = "growth"        # 增长类（新增贡献者等）
    INDEX = "index"          # 指数类（OpenRank、活跃度等）
    FACTOR = "factor"        # 因子类（Bus Factor等）


@dataclass
class MetricConfig:
    """指标配置"""
    key: str                          # 指标键名
    type: MetricType                  # 指标类型
    weight: float = 1.0               # 权重
    higher_is_better: bool = True     # 值越大越好（False表示越小越好，如Bus Factor）
    iqr_multiplier: float = 1.5       # IQR倍数（不同类型指标使用不同倍数）
    baseline: Optional[float] = None  # 基准值（用于归一化）
    use_percentile: bool = False      # 是否使用百分位归一化
    percentile_ref: float = 75.0      # 百分位参考值（默认75%）
    log_scale: bool = False           # 是否使用对数尺度


# 指标配置映射表
METRIC_CONFIGS = {
    # Activity 维度
    'opendigger_OpenRank': MetricConfig(
        key='opendigger_OpenRank',
        type=MetricType.INDEX,
        weight=1.5,
        baseline=100.0,
        use_percentile=True,
        percentile_ref=75.0
    ),
    'opendigger_活跃度': MetricConfig(
        key='opendigger_活跃度',
        type=MetricType.INDEX,
        weight=1.5,
        baseline=500.0,
        use_percentile=True,
        log_scale=True
    ),
    'opendigger_变更请求': MetricConfig(
        key='opendigger_变更请求',
        type=MetricType.COUNT,
        weight=1.0,
        iqr_multiplier=2.0,  # 计数类指标波动较大，使用更大的IQR倍数
        use_percentile=True
    ),
    'opendigger_PR接受数': MetricConfig(
        key='opendigger_PR接受数',
        type=MetricType.COUNT,
        weight=1.0,
        iqr_multiplier=2.0,
        use_percentile=True
    ),
    'opendigger_新增Issue': MetricConfig(
        key='opendigger_新增Issue',
        type=MetricType.COUNT,
        weight=1.0,
        iqr_multiplier=2.0,
        use_percentile=True
    ),
    
    # Contributors 维度
    'opendigger_参与者数': MetricConfig(
        key='opendigger_参与者数',
        type=MetricType.COUNT,
        weight=1.3,
        iqr_multiplier=2.0,
        use_percentile=True
    ),
    'opendigger_贡献者': MetricConfig(
        key='opendigger_贡献者',
        type=MetricType.COUNT,
        weight=1.3,
        iqr_multiplier=2.0,
        use_percentile=True
    ),
    'opendigger_新增贡献者': MetricConfig(
        key='opendigger_新增贡献者',
        type=MetricType.GROWTH,
        weight=1.0,
        iqr_multiplier=2.5,  # 增长类指标波动更大
        use_percentile=True
    ),
    
    # Responsiveness 维度
    'opendigger_关闭Issue': MetricConfig(
        key='opendigger_关闭Issue',
        type=MetricType.COUNT,
        weight=1.0,
        iqr_multiplier=2.0,
        use_percentile=True
    ),
    'opendigger_Issue评论': MetricConfig(
        key='opendigger_Issue评论',
        type=MetricType.COUNT,
        weight=1.0,
        iqr_multiplier=2.0,
        use_percentile=True
    ),
    
    # Quality 维度
    'opendigger_PR审查': MetricConfig(
        key='opendigger_PR审查',
        type=MetricType.COUNT,
        weight=1.0,
        iqr_multiplier=2.0,
        use_percentile=True
    ),
    'opendigger_代码新增行数': MetricConfig(
        key='opendigger_代码新增行数',
        type=MetricType.COUNT,
        weight=0.8,
        iqr_multiplier=2.5,
        log_scale=True,  # 代码行数使用对数尺度
        use_percentile=True
    ),
    'opendigger_代码删除行数': MetricConfig(
        key='opendigger_代码删除行数',
        type=MetricType.COUNT,
        weight=0.8,
        iqr_multiplier=2.5,
        log_scale=True,
        use_percentile=True
    ),
    'opendigger_代码变更总行数': MetricConfig(
        key='opendigger_代码变更总行数',
        type=MetricType.COUNT,
        weight=1.0,
        iqr_multiplier=2.5,
        log_scale=True,
        use_percentile=True
    ),
    
    # Risk 维度
    'opendigger_总线因子': MetricConfig(
        key='opendigger_总线因子',
        type=MetricType.FACTOR,
        weight=1.0,
        iqr_multiplier=1.5,
        higher_is_better=False,  # Bus Factor越小越好
        baseline=3.0,
        use_percentile=True
    ),
    
    # Community Interest 维度
    'opendigger_Star数': MetricConfig(
        key='opendigger_Star数',
        type=MetricType.COUNT,
        weight=1.0,
        iqr_multiplier=2.0,
        log_scale=True,  # Star数使用对数尺度
        use_percentile=True
    ),
    'opendigger_Fork数': MetricConfig(
        key='opendigger_Fork数',
        type=MetricType.COUNT,
        weight=1.0,
        iqr_multiplier=2.0,
        log_scale=True,
        use_percentile=True
    ),
}


def get_metric_config(metric_key: str) -> MetricConfig:
    """
    获取指标配置
    
    Args:
        metric_key: 指标键名
        
    Returns:
        MetricConfig对象，如果不存在则返回默认配置
    """
    return METRIC_CONFIGS.get(
        metric_key,
        MetricConfig(
            key=metric_key,
            type=MetricType.COUNT,
            weight=1.0
        )
    )

