"""
改进版 CHAOSS 指标计算器
按月计算评分，然后去除异常值后取平均值
- 按指标类型设置不同的IQR倍数
- 数据质量加权聚合
- 动态归一化（百分位/基准/回退）
- 降权而非删除异常值
"""
import os
import json
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict
import statistics
import math
from .chaoss_mapper import CHAOSSMapper
from .chaoss_metric_config import get_metric_config, MetricType
from .quality_utils import (
    evaluate_data_quality,
    normalize_value,
    calculate_percentile_reference,
    apply_quality_penalty
)


class CHAOSSEvaluator:
    """CHAOSS 评估器"""
    
    def __init__(self, data_service=None):
        """
        初始化评估器
        
        Args:
            data_service: DataService 实例，用于访问数据
        """
        self.data_service = data_service
        self.mapper = CHAOSSMapper()
    
    def evaluate_repo(self, repo_key: str) -> Dict:
        """
        评估仓库的 CHAOSS 指标
        
        Args:
            repo_key: 仓库标识
            
        Returns:
            CHAOSS 评价结果
        """
        if not self.data_service:
            return {'error': 'DataService 未提供'}
        
        print(f"[CHAOSS] 开始评估 {repo_key}...")
        
        # 1. 获取时序数据
        normalized_key = self.data_service._normalize_repo_key(repo_key)
        timeseries_data = self.data_service.get_all_metrics_historical_data(normalized_key)
        
        if not timeseries_data:
            return {'error': f'仓库 {normalized_key} 的时序数据不存在'}
        
        print(f"[CHAOSS] 找到 {len(timeseries_data)} 个指标")
        
        # 2. 获取仓库创建时间（用于过滤不合理的时间范围）
        repo_created_month = None
        try:
            # 尝试从 data_service 获取仓库信息
            normalized_key_for_text = normalized_key.replace('/', '_')
            if normalized_key_for_text in self.data_service.loaded_text:
                text_data = self.data_service.loaded_text[normalized_key_for_text]
                for doc in text_data:
                    if doc.get('type') == 'repo_info':
                        content = doc.get('content', '')
                        try:
                            repo_info = json.loads(content)
                            created_at = repo_info.get('created_at', '')
                            if created_at:
                                # 解析创建时间，转换为 YYYY-MM 格式
                                from datetime import datetime
                                try:
                                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                                    repo_created_month = dt.strftime('%Y-%m')
                                    print(f"[CHAOSS] 仓库创建时间: {repo_created_month}")
                                except:
                                    pass
                        except:
                            pass
                        break
        except Exception as e:
            print(f"[CHAOSS] 获取仓库创建时间失败: {e}")
        
        # 3. 提取所有月份
        all_months = set()
        for metric_data in timeseries_data.values():
            if isinstance(metric_data, dict) and 'raw' in metric_data:
                raw_data = metric_data['raw']
                if isinstance(raw_data, dict):
                    for month in raw_data.keys():
                        if isinstance(month, str) and len(month) == 7 and month[4] == '-':
                            # 过滤掉仓库创建之前的月份
                            if repo_created_month is None or month >= repo_created_month:
                                all_months.add(month)
        
        if not all_months:
            return {'error': '没有可用的月份数据'}
        
        sorted_months = sorted(all_months)
        
        # 如果设置了创建时间，确保起始月份不早于创建时间
        if repo_created_month and sorted_months[0] < repo_created_month:
            sorted_months = [m for m in sorted_months if m >= repo_created_month]
            if not sorted_months:
                return {'error': '没有可用的月份数据（所有数据都在仓库创建之前）'}
        
        print(f"[CHAOSS] 数据范围: {sorted_months[0]} 至 {sorted_months[-1]}，共 {len(sorted_months)} 个月")
        
        # 4. 按月计算评分（使用最近N个月）
        # 使用最近12个月的数据，如果不足12个月则使用所有可用数据
        months_to_evaluate = sorted_months[-12:] if len(sorted_months) >= 12 else sorted_months
        
        print(f"[CHAOSS] 评估最近 {len(months_to_evaluate)} 个月的数据")
        
        monthly_scores = []
        for month in months_to_evaluate:
            month_score = self._calculate_monthly_score(timeseries_data, month)
            if month_score:
                monthly_scores.append({
                    'month': month,
                    'score': month_score
                })
        
        if not monthly_scores:
            return {'error': '无法计算任何月份的评分'}
        
        print(f"[CHAOSS] 成功计算 {len(monthly_scores)} 个月的评分")
        
        # 5. 去除异常值后计算最终评分
        final_scores = self._calculate_final_scores(monthly_scores, normalized_key)
        
        # 6. 生成报告
        report = self._generate_report(final_scores, monthly_scores)
        
        # 计算实际有效月份范围（只包含有评分的月份）
        valid_months = [m['month'] for m in monthly_scores]
        actual_start = min(valid_months) if valid_months else sorted_months[0]
        actual_end = max(valid_months) if valid_months else sorted_months[-1]
        
        return {
            'repo_key': normalized_key,
            'time_range': {
                'start': actual_start,  # 使用实际有效起始月份
                'end': actual_end,  # 使用实际有效结束月份
                'total_months': len(sorted_months),
                'evaluated_months': len(months_to_evaluate),
                'valid_months': len(valid_months),  # 实际有评分的月份数
                'repo_created_month': repo_created_month  # 仓库创建月份
            },
            'monthly_scores': monthly_scores,
            'final_scores': final_scores,
            'report': report
        }
    
    def _calculate_monthly_score(self, timeseries_data: Dict, month: str) -> Optional[Dict]:
        """
        计算单个月的评分（改进版）
        
        改进点：
        1. 使用指标配置进行数据质量评估
        2. 数据质量作为权重参与计算
        3. 支持多种归一化策略
        """
        dimension_scores = {}
        total_metrics_count = 0
        valid_metrics_count = 0
        
        chaoss_dimensions = self.mapper.get_chaoss_dimensions()
        
        # 统计总指标数
        for dimension_info in chaoss_dimensions.values():
            total_metrics_count += len(dimension_info['metrics'])
        
        for dimension, dimension_info in chaoss_dimensions.items():
            dimension_metrics = dimension_info['metrics']
            metric_scores = []
            metric_weights = []
            metric_qualities = []  # 记录每个指标的质量得分
            
            for metric_key, metric_info in dimension_metrics.items():
                if metric_key in timeseries_data:
                    metric_data = timeseries_data[metric_key]
                    if isinstance(metric_data, dict) and 'raw' in metric_data:
                        raw_data = metric_data['raw']
                        if isinstance(raw_data, dict) and month in raw_data:
                            value = raw_data[month]
                            
                            # 重要：缺失数据不会被当作0处理
                            # 只有当月份存在于数据中且值有效时才会处理
                            # 如果某个月份某个指标不存在，会直接跳过该指标，不会影响评分
                            
                            # 基本有效性检查
                            if value is not None and isinstance(value, (int, float)):
                                if not (math.isnan(value) or math.isinf(value)) and value >= 0:
                                    # 获取指标配置
                                    config = get_metric_config(metric_key)
                                    
                                    # 获取历史数据用于归一化和质量评估
                                    all_values = [
                                        v for v in raw_data.values()
                                        if v is not None
                                        and isinstance(v, (int, float))
                                        and not (math.isnan(v) or math.isinf(v))
                                        and v >= 0
                                    ]
                                    
                                    if all_values:
                                        # 评估数据质量
                                        quality_result = evaluate_data_quality(all_values, config)
                                        
                                        # 如果质量太低，跳过该指标
                                        if quality_result['quality'] < 0.3:
                                            continue
                                        
                                        # Patch 3: 增长型指标不再被均值抹平
                                        # 对于增长型指标（GROWTH、INDEX），使用max(当前值, 最近3月均值)避免压制成长项目
                                        final_value = value
                                        if config.type in [MetricType.GROWTH, MetricType.INDEX]:
                                            # 获取最近3个月的有效值
                                            sorted_months = sorted([k for k in raw_data.keys() 
                                                                  if isinstance(k, str) and len(k) == 7 and k <= month])
                                            if len(sorted_months) > 0:
                                                month_idx = sorted_months.index(month) if month in sorted_months else len(sorted_months) - 1
                                                recent_values = []
                                                # 获取当前月及前2个月的值
                                                for i in range(max(0, month_idx - 2), month_idx + 1):
                                                    if i < len(sorted_months):
                                                        m = sorted_months[i]
                                                        v = raw_data.get(m)
                                                        if v is not None and isinstance(v, (int, float)) and v >= 0:
                                                            if not (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
                                                                recent_values.append(v)
                                                
                                                if len(recent_values) >= 2:
                                                    avg_recent = sum(recent_values) / len(recent_values)
                                                    final_value = max(value, avg_recent)
                                        
                                        # 计算百分位参考值（如果需要）
                                        ref = None
                                        if config.use_percentile:
                                            ref = calculate_percentile_reference(
                                                all_values,
                                                config.percentile_ref
                                            )
                                        
                                        # 归一化值（使用final_value而不是原始value）
                                        normalized_score = normalize_value(
                                            final_value,
                                            config,
                                            historical_values=all_values,
                                            ref=ref
                                        )
                                        
                                        # Patch 1: 使用质量折损而非乘法，避免系统性压分
                                        normalized_score = apply_quality_penalty(
                                            normalized_score,
                                            quality_result['quality']
                                        )
                                        
                                        # 质量加权：只使用基础权重，质量已通过折损应用
                                        base_weight = metric_info.get('weight', 1.0)
                                        
                                        metric_scores.append(normalized_score)
                                        metric_weights.append(base_weight)
                                        metric_qualities.append(quality_result['quality'])
                                        valid_metrics_count += 1
            
            if metric_scores:
                # 加权平均（权重 = 指标权重，质量已通过折损应用）
                if metric_weights and len(metric_weights) == len(metric_scores):
                    weighted_sum = sum(s * w for s, w in zip(metric_scores, metric_weights))
                    total_weight = sum(metric_weights)
                    dimension_score = weighted_sum / total_weight if total_weight > 0 else 0
                else:
                    dimension_score = sum(metric_scores) / len(metric_scores)
                
                # Patch 4: 维度分增加健康软下限，避免误伤持续维护的项目
                # 降低软下限到30分，允许真正表现差的维度得到低分
                # 但确保有基本数据的项目不会因为数据稀疏而得分过低
                dimension_score = max(30.0, dimension_score)
                
                # 计算平均质量得分
                avg_quality = sum(metric_qualities) / len(metric_qualities) if metric_qualities else 1.0
                
                dimension_scores[dimension] = {
                    'score': round(dimension_score, 1),
                    'metrics_count': len(metric_scores),
                    'quality': round(avg_quality, 2)  # 新增：维度数据质量
                }
        
        # 数据质量检测：如果有效指标少于总指标的30%，则认为数据不足，跳过该月份
        if total_metrics_count > 0:
            data_quality_ratio = valid_metrics_count / total_metrics_count
            if data_quality_ratio < 0.3:
                print(f"[CHAOSS] 跳过 {month}：数据质量过低 ({valid_metrics_count}/{total_metrics_count} = {data_quality_ratio:.1%})")
                return None
        
        if not dimension_scores:
            print(f"[CHAOSS] 跳过 {month}：没有可用的维度数据")
            return None
        
        # 计算总体得分（各维度平均）
        overall_score = sum(d['score'] for d in dimension_scores.values()) / len(dimension_scores)
        
        # 如果总体得分为0或接近0（可能是数据缺失），也跳过
        if overall_score < 0.1:
            print(f"[CHAOSS] 跳过 {month}：总体得分过低 ({overall_score:.1f})，可能是数据缺失")
            return None
        
        return {
            'overall_score': round(overall_score, 1),
            'dimensions': dimension_scores
        }
    
    def _calculate_final_scores(self, monthly_scores: List[Dict], repo_key: str) -> Dict:
        """
        改进版：去除异常值后计算最终评分
        
        使用改进的降权方法而非直接删除
        
        Args:
            monthly_scores: 月度评分列表
            repo_key: 仓库标识（用于缓存管理）
        """
        if not monthly_scores:
            return {}
        
        # 提取各维度的月度得分
        dimension_monthly_scores = defaultdict(list)
        overall_scores = []
        
        for month_data in monthly_scores:
            month = month_data['month']
            score_data = month_data['score']
            
            overall_scores.append(score_data['overall_score'])
            
            for dimension, dim_data in score_data['dimensions'].items():
                dimension_monthly_scores[dimension].append({
                    'month': month,
                    'score': dim_data['score'],
                    'quality': dim_data.get('quality', 1.0)  # 保留质量信息
                })
        
        # 计算总体得分的最终值（使用改进的降权方法）
        final_overall = self._remove_outliers_and_average(overall_scores)
        
        # 计算各维度的最终得分
        final_dimensions = {}
        for dimension, scores_list in dimension_monthly_scores.items():
            scores = [s['score'] for s in scores_list]
            qualities = [s.get('quality', 1.0) for s in scores_list]
            
            # 使用改进的降权方法
            final_score = self._remove_outliers_and_average(scores, dimension)
            
            # 计算平均质量
            avg_quality = sum(qualities) / len(qualities) if qualities else 1.0
            
            # 计算异常值数量（用于报告）
            valid_scores = self._get_valid_scores(scores, dimension)
            outliers_removed = len(scores) - len(valid_scores)
            
            final_dimensions[dimension] = {
                'score': round(final_score, 1),
                'level': self._get_score_level(final_score),
                'monthly_count': len(scores),
                'outliers_removed': outliers_removed,
                'quality': round(avg_quality, 2)  # 新增：维度数据质量
            }
        
        # 计算最终原始分数（不进行分布映射，确保评分稳定）
        # 移除分布对齐器，因为：
        # 1. 本地项目数量有限，无法构建稳定的参考分布
        # 2. 动态参考分布会导致评分不稳定
        # 3. 原始分数已经能够反映项目的真实健康度
        raw_overall_score = round(final_overall, 1)
        
        return {
            'overall_score': raw_overall_score,  # 直接使用原始分数，确保完全稳定
            'overall_level': self._get_score_level(raw_overall_score),
            '_raw_overall_score': raw_overall_score,  # 保留原始分数字段（向后兼容）
            '_percentile': None,  # 不再计算百分位排名（需要大量参考项目，本地不适用）
            'dimensions': final_dimensions
        }
    
    def _remove_outliers_and_average(self, scores: List[float], dimension: Optional[str] = None) -> float:
        """
        改进版：去除异常值后计算平均值（降权而非删除）
        
        改进点：
        1. 根据维度或指标类型使用不同的IQR倍数
        2. 异常值降权而非直接删除
        3. 保留更多信息
        
        Args:
            scores: 得分列表
            dimension: 维度名称（可选，用于选择IQR倍数）
            
        Returns:
            去除异常值后的加权平均值
        """
        if not scores:
            return 0.0
        
        if len(scores) < 4:
            # 数据点太少，直接返回平均值
            return sum(scores) / len(scores)
        
        # 根据维度选择IQR倍数（默认1.5）
        iqr_multiplier = 1.5
        if dimension:
            # 可以根据维度调整IQR倍数
            # 例如：Activity维度波动较大，可以使用更大的倍数
            if dimension == 'Activity':
                iqr_multiplier = 2.0
            elif dimension == 'Risk':
                iqr_multiplier = 1.5
        
        # 计算IQR（使用更精确的分位数计算方法）
        sorted_scores = sorted(scores)
        
        # 使用类方法计算分位数（0-100的百分位，需要转换为0-1）
        q1 = self._percentile(sorted_scores, 25.0)  # 25百分位
        q3 = self._percentile(sorted_scores, 75.0)  # 75百分位
        iqr = q3 - q1
        
        if iqr == 0:
            # 如果IQR为0，说明所有值相同，直接返回平均值
            return sum(scores) / len(scores)
        
        # 计算异常值边界
        lower_bound = q1 - iqr_multiplier * iqr
        upper_bound = q3 + iqr_multiplier * iqr
        
        # 改进：降权而非删除
        weighted_sum = 0.0
        total_weight = 0.0
        
        for score in scores:
            if lower_bound <= score <= upper_bound:
                # 正常值，权重为1.0
                weight = 1.0
            else:
                # 异常值，降权（权重为0.3）
                weight = 0.3
            
            weighted_sum += score * weight
            total_weight += weight
        
        if total_weight == 0:
            # 如果所有权重都为0，使用原始平均值
            return sum(scores) / len(scores)
        
        return weighted_sum / total_weight
    
    def _get_valid_scores(self, scores: List[float], dimension: Optional[str] = None) -> List[float]:
        """
        获取去除异常值后的有效得分（改进版）
        
        使用与_remove_outliers_and_average相同的IQR倍数和计算方法
        """
        if len(scores) < 4:
            return scores
        
        # 使用与计算平均值相同的IQR倍数
        iqr_multiplier = 2.0 if dimension == 'Activity' else 1.5
        
        # 使用与_remove_outliers_and_average相同的分位数计算方法
        sorted_scores = sorted(scores)
        q1 = self._percentile(sorted_scores, 25.0)  # 25百分位
        q3 = self._percentile(sorted_scores, 75.0)  # 75百分位
        iqr = q3 - q1
        
        if iqr == 0:
            return scores
        
        lower_bound = q1 - iqr_multiplier * iqr
        upper_bound = q3 + iqr_multiplier * iqr
        
        return [s for s in scores if lower_bound <= s <= upper_bound]
    
    def _percentile(self, data: List[float], p: float) -> float:
        """计算百分位数"""
        if not data:
            return 0.0
        
        sorted_data = sorted(data)
        n = len(sorted_data)
        k = (n - 1) * p / 100
        
        if k == int(k):
            return sorted_data[int(k)]
        
        lower_idx = int(math.floor(k))
        upper_idx = int(math.ceil(k))
        
        if upper_idx >= n:
            return sorted_data[-1]
        
        weight = k - lower_idx
        return sorted_data[lower_idx] * (1 - weight) + sorted_data[upper_idx] * weight
    
    def _get_score_level(self, score: float) -> str:
        """根据得分获取等级"""
        if score >= 80:
            return '优秀'
        elif score >= 60:
            return '良好'
        elif score >= 40:
            return '一般'
        elif score >= 20:
            return '较差'
        else:
            return '很差'
    
    def _generate_report(self, final_scores: Dict, monthly_scores: List[Dict]) -> Dict:
        """
        生成评价报告（改进版 - 更个性化、更具体）
        
        根据各维度得分、趋势、百分位排名、月度数据变化模式等生成具体、有针对性的建议
        """
        recommendations = []
        
        overall_score = final_scores.get('overall_score', 0)
        percentile = final_scores.get('_percentile')
        dimensions = final_scores.get('dimensions', {})
        
        # 1. 分析月度趋势（更详细的趋势分析）
        trend_analysis = self._analyze_trends(monthly_scores)
        if trend_analysis:
            recommendations.extend(trend_analysis)
        
        # 2. 总体评价（考虑百分位排名和趋势）
        overall_rec = self._generate_overall_recommendation(overall_score, percentile, trend_analysis)
        if overall_rec:
            recommendations.append(overall_rec)
        
        # 3. 分析各维度（找出多个薄弱维度和强项维度）
        dimension_analysis = self._analyze_dimensions(dimensions, monthly_scores)
        if dimension_analysis:
            recommendations.extend(dimension_analysis)
        
        # 4. 分析维度组合问题（识别关联性问题）
        combination_analysis = self._analyze_dimension_combinations(dimensions)
        if combination_analysis:
            recommendations.extend(combination_analysis)
        
        # 5. 分析数据质量和异常值
        quality_analysis = self._analyze_data_quality(dimensions)
        if quality_analysis:
            recommendations.extend(quality_analysis)
        
        # 6. 生成摘要（基于原始分数）
        summary = f'综合评分: {overall_score:.1f}分 ({final_scores.get("overall_level", "未知")})'
        
        # 去重并限制数量
        unique_recommendations = []
        seen = set()
        for rec in recommendations:
            if rec not in seen:
                seen.add(rec)
                unique_recommendations.append(rec)
                if len(unique_recommendations) >= 6:  # 最多6条建议
                    break
        
        return {
            'summary': summary,
            'recommendations': unique_recommendations
        }
    
    def _analyze_trends(self, monthly_scores: List[Dict]) -> List[str]:
        """分析月度趋势，生成更具体的趋势建议"""
        recommendations = []
        
        if len(monthly_scores) < 3:
            return recommendations
        
        # 提取所有月度分数
        scores = [m['score']['overall_score'] for m in monthly_scores if m.get('score', {}).get('overall_score', 0) > 0]
        
        if len(scores) < 3:
            return recommendations
        
        # 分析最近6个月 vs 前6个月（如果数据足够）
        if len(scores) >= 12:
            recent_6 = scores[-6:]
            earlier_6 = scores[:6]
            recent_avg = sum(recent_6) / len(recent_6)
            earlier_avg = sum(earlier_6) / len(earlier_6)
            trend_6m = recent_avg - earlier_avg
            
            if trend_6m > 8:
                recommendations.append(f'近6个月评分提升{trend_6m:.1f}分，项目发展势头强劲，建议继续保持并扩大优势')
            elif trend_6m > 3:
                recommendations.append(f'近6个月评分稳步提升{trend_6m:.1f}分，项目处于上升期，建议持续优化')
            elif trend_6m < -8:
                recommendations.append(f'近6个月评分下降{abs(trend_6m):.1f}分，需要立即关注项目活跃度和社区参与度，分析下降原因')
            elif trend_6m < -3:
                recommendations.append(f'近6个月评分下降{abs(trend_6m):.1f}分，建议加强社区互动，提升项目活跃度')
        
        # 分析最近3个月 vs 前3个月
        if len(scores) >= 6:
            recent_3 = scores[-3:]
            earlier_3 = scores[:3]
            recent_avg = sum(recent_3) / len(recent_3)
            earlier_avg = sum(earlier_3) / len(earlier_3)
            trend_3m = recent_avg - earlier_avg
            
            if trend_3m > 5 and trend_3m <= 8:
                recommendations.append(f'最近3个月评分提升{trend_3m:.1f}分，近期表现良好，建议保持当前节奏')
            elif trend_3m < -5:
                recommendations.append(f'最近3个月评分下降{abs(trend_3m):.1f}分，需要关注近期变化，及时调整策略')
        
        # 分析波动性
        if len(scores) >= 6:
            variance = statistics.variance(scores) if len(scores) > 1 else 0
            if variance > 200:  # 高波动性
                recommendations.append('评分波动较大，建议保持项目发展的稳定性，避免大起大落')
            elif variance < 50 and len(scores) >= 12:  # 低波动性且数据充足
                recommendations.append('评分保持稳定，项目发展平稳，建议在此基础上寻求突破')
        
        return recommendations
    
    def _generate_overall_recommendation(self, overall_score: float, percentile: Optional[float], trend_analysis: List[str]) -> Optional[str]:
        """生成总体评价建议（基于原始分数，不依赖百分位排名）"""
        # 如果有趋势分析，结合趋势生成更具体的建议
        has_positive_trend = any('提升' in t or '上升' in t for t in trend_analysis)
        has_negative_trend = any('下降' in t for t in trend_analysis)
        
        # 完全基于原始分数生成建议，确保稳定性
        if overall_score >= 80:
            if has_positive_trend:
                return '项目健康度优秀，且近期表现优异，建议继续保持并扩大影响力'
            else:
                return '项目健康度优秀，建议在保持优势的同时关注潜在风险'
        elif overall_score >= 70:
            if has_positive_trend:
                return '项目健康度良好且持续改善，建议继续优化薄弱环节'
            else:
                return '项目健康度良好，建议关注近期变化趋势'
        elif overall_score >= 60:
            if has_positive_trend:
                return '项目健康度中等偏上且呈上升趋势，建议重点提升薄弱维度'
            elif has_negative_trend:
                return '项目健康度中等偏上但近期有所下降，建议分析原因并采取针对性措施'
            else:
                return '项目健康度中等偏上，建议重点关注薄弱维度以进一步提升'
        elif overall_score >= 50:
            if has_positive_trend:
                return '项目健康度中等但呈上升趋势，建议持续改进以提升评分'
            elif has_negative_trend:
                return '项目健康度中等且近期下降，需要系统性改进'
            else:
                return '项目健康度中等，建议系统性改进薄弱环节'
        elif overall_score >= 40:
            if has_positive_trend:
                return '项目健康度中等偏下但呈改善趋势，建议加大改进力度'
            else:
                return '项目健康度中等偏下，需要系统性改进社区建设和代码质量'
        elif overall_score >= 30:
            return '项目健康度偏低，建议加强社区建设、代码质量管控和项目推广'
        else:
            return '项目健康度较低，建议全面改进社区建设、代码质量和项目活跃度'
    
    def _analyze_dimensions(self, dimensions: Dict, monthly_scores: List[Dict]) -> List[str]:
        """分析各维度，生成具体的维度建议"""
        recommendations = []
        
        dimension_scores_list = []
        for dimension, dim_data in dimensions.items():
            score = dim_data.get('score', 0)
            dim_name = self.mapper.CHAOSS_DIMENSIONS.get(dimension, {}).get('name', dimension)
            dimension_scores_list.append({
                'name': dim_name,
                'score': score,
                'dimension': dimension,
                'quality': dim_data.get('quality', 1.0)
            })
        
        if not dimension_scores_list:
            return recommendations
        
        # 按得分排序
        dimension_scores_list.sort(key=lambda x: x['score'])
        
        # 找出所有薄弱维度（得分 < 50）
        weak_dimensions = [d for d in dimension_scores_list if d['score'] < 50]
        
        # 找出所有中等维度（50 <= score < 65）
        medium_dimensions = [d for d in dimension_scores_list if 50 <= d['score'] < 65]
        
        # 找出所有强项维度（score >= 70）
        strong_dimensions = [d for d in dimension_scores_list if d['score'] >= 70]
        
        # 分析薄弱维度
        if len(weak_dimensions) >= 2:
            weak_names = [d['name'] for d in weak_dimensions[:2]]
            recommendations.append(f'{weak_names[0]}和{weak_names[1]}维度得分较低，建议优先改进这两个维度，可产生协同效应')
        elif len(weak_dimensions) == 1:
            weakest = weak_dimensions[0]
            dim_specific_rec = self._get_dimension_specific_recommendation(weakest)
            if dim_specific_rec:
                recommendations.append(dim_specific_rec)
        
        # 分析中等维度（有提升空间）
        if len(medium_dimensions) >= 2 and len(weak_dimensions) == 0:
            medium_names = [d['name'] for d in medium_dimensions[:2]]
            recommendations.append(f'{medium_names[0]}和{medium_names[1]}维度有提升空间，建议重点优化以提升整体评分')
        
        # 分析强项维度
        if len(strong_dimensions) >= 2:
            strong_names = [d['name'] for d in strong_dimensions[:2]]
            recommendations.append(f'{strong_names[0]}和{strong_names[1]}维度表现优秀，可作为项目亮点继续发扬，并考虑将成功经验应用到其他维度')
        elif len(strong_dimensions) == 1:
            strongest = strong_dimensions[0]
            recommendations.append(f'{strongest["name"]}维度表现优秀({strongest["score"]:.1f}分)，可作为项目亮点继续发扬')
        
        # 分析维度月度变化
        if monthly_scores and len(monthly_scores) >= 6:
            dim_trends = self._analyze_dimension_trends(dimensions, monthly_scores)
            if dim_trends:
                recommendations.extend(dim_trends)
        
        return recommendations
    
    def _get_dimension_specific_recommendation(self, dimension_info: Dict) -> Optional[str]:
        """获取特定维度的具体建议"""
        dim = dimension_info['dimension']
        name = dimension_info['name']
        score = dimension_info['score']
        
        if dim == 'Activity':
            if score < 30:
                return f'{name}维度得分很低({score:.1f}分)，建议立即增加PR提交频率、加快Issue响应速度，提升项目活跃度'
            else:
                return f'{name}维度得分较低({score:.1f}分)，建议增加PR提交频率、Issue响应速度，提升项目活跃度'
        elif dim == 'Contributors':
            if score < 30:
                return f'{name}维度得分很低({score:.1f}分)，建议立即鼓励新贡献者参与，建立贡献者社区，提升贡献者留存率，避免项目依赖少数核心成员'
            else:
                return f'{name}维度得分较低({score:.1f}分)，建议鼓励新贡献者参与，建立贡献者社区，提升贡献者留存率'
        elif dim == 'Responsiveness':
            if score < 30:
                return f'{name}维度得分很低({score:.1f}分)，建议立即加快Issue和PR的响应速度，设置响应时间目标，及时回复社区问题'
            else:
                return f'{name}维度得分较低({score:.1f}分)，建议加快Issue和PR的响应速度，及时回复社区问题，提升社区满意度'
        elif dim == 'Quality':
            if score < 30:
                return f'{name}维度得分很低({score:.1f}分)，建议立即加强代码审查，提高代码质量标准，减少技术债务，建立代码审查流程'
            else:
                return f'{name}维度得分较低({score:.1f}分)，建议加强代码审查，提高代码质量标准，减少技术债务'
        elif dim == 'Risk':
            if score < 30:
                return f'{name}维度得分很低({score:.1f}分)，建议立即分散项目风险，避免过度依赖少数核心贡献者，提升Bus Factor，建立知识共享机制'
            else:
                return f'{name}维度得分较低({score:.1f}分)，建议分散项目风险，避免过度依赖少数核心贡献者，提升Bus Factor'
        elif dim == 'Community Interest':
            if score < 30:
                return f'{name}维度得分很低({score:.1f}分)，建议立即提升项目知名度，完善文档和README，吸引更多Star和Fork，参与开源社区活动'
            else:
                return f'{name}维度得分较低({score:.1f}分)，建议提升项目知名度，完善文档，吸引更多Star和Fork'
        else:
            return f'{name}维度得分较低({score:.1f}分)，需要重点关注并制定改进计划'
    
    def _analyze_dimension_trends(self, dimensions: Dict, monthly_scores: List[Dict]) -> List[str]:
        """分析各维度的月度趋势"""
        recommendations = []
        
        for dimension, dim_data in dimensions.items():
            dim_name = self.mapper.CHAOSS_DIMENSIONS.get(dimension, {}).get('name', dimension)
            
            # 提取该维度的月度分数
            dim_monthly_scores = []
            for month_data in monthly_scores:
                if dimension in month_data.get('score', {}).get('dimensions', {}):
                    dim_score = month_data['score']['dimensions'][dimension].get('score', 0)
                    if dim_score > 0:
                        dim_monthly_scores.append(dim_score)
            
            if len(dim_monthly_scores) >= 6:
                recent_3 = dim_monthly_scores[-3:]
                earlier_3 = dim_monthly_scores[:3]
                recent_avg = sum(recent_3) / len(recent_3)
                earlier_avg = sum(earlier_3) / len(earlier_3)
                trend = recent_avg - earlier_avg
                
                current_score = dim_data.get('score', 0)
                
                # 如果维度得分低且还在下降
                if current_score < 50 and trend < -5:
                    recommendations.append(f'{dim_name}维度得分较低且呈下降趋势(下降{abs(trend):.1f}分)，需要立即采取改进措施')
                # 如果维度得分低但在改善
                elif current_score < 50 and trend > 3:
                    recommendations.append(f'{dim_name}维度得分较低但呈改善趋势(提升{trend:.1f}分)，建议继续保持改进势头')
                # 如果维度得分高但在下降
                elif current_score >= 70 and trend < -5:
                    recommendations.append(f'{dim_name}维度原本表现优秀但近期下降(下降{abs(trend):.1f}分)，需要关注并防止进一步下滑')
        
        return recommendations
    
    def _analyze_dimension_combinations(self, dimensions: Dict) -> List[str]:
        """分析维度组合问题，识别关联性问题"""
        recommendations = []
        
        dimension_scores = {}
        for dimension, dim_data in dimensions.items():
            dim_name = self.mapper.CHAOSS_DIMENSIONS.get(dimension, {}).get('name', dimension)
            dimension_scores[dimension] = {
                'name': dim_name,
                'score': dim_data.get('score', 0)
            }
        
        # Activity + Responsiveness 组合（活跃度和响应性相关）
        if (dimension_scores.get('Activity', {}).get('score', 0) < 50 and 
            dimension_scores.get('Responsiveness', {}).get('score', 0) < 50):
            recommendations.append('活动度和响应性维度都较低，建议同时提升PR提交频率和Issue响应速度，两者相互促进')
        
        # Contributors + Risk 组合（贡献者和风险相关）
        if (dimension_scores.get('Contributors', {}).get('score', 0) < 50 and 
            dimension_scores.get('Risk', {}).get('score', 0) < 50):
            recommendations.append('贡献者和风险维度都较低，建议鼓励新贡献者参与并分散项目风险，提升Bus Factor')
        
        # Quality + Activity 组合（质量和活跃度相关）
        if (dimension_scores.get('Quality', {}).get('score', 0) < 50 and 
            dimension_scores.get('Activity', {}).get('score', 0) >= 70):
            recommendations.append('代码质量维度较低但活跃度较高，建议在保持活跃度的同时加强代码审查，避免技术债务积累')
        
        # Community Interest + Activity 组合（社区兴趣和活跃度相关）
        if (dimension_scores.get('Community Interest', {}).get('score', 0) < 50 and 
            dimension_scores.get('Activity', {}).get('score', 0) >= 70):
            recommendations.append('社区兴趣维度较低但活跃度较高，建议加强项目推广和文档完善，将活跃度转化为社区关注')
        
        return recommendations
    
    def _analyze_data_quality(self, dimensions: Dict) -> List[str]:
        """分析数据质量和异常值"""
        recommendations = []
        
        # 分析数据质量
        low_quality_dims = []
        for dimension, dim_data in dimensions.items():
            quality = dim_data.get('quality', 1.0)
            if quality < 0.7:
                dim_name = self.mapper.CHAOSS_DIMENSIONS.get(dimension, {}).get('name', dimension)
                low_quality_dims.append(dim_name)
        
        if low_quality_dims:
            if len(low_quality_dims) >= 3:
                recommendations.append(f'多个维度({", ".join(low_quality_dims[:3])}等)的数据质量较低，可能影响评分准确性，建议补充相关数据')
            else:
                recommendations.append(f'{", ".join(low_quality_dims)}维度的数据质量较低，可能影响评分准确性，建议补充相关数据')
        
        # 分析异常值
        high_outlier_dims = []
        for dimension, dim_data in dimensions.items():
            outliers = dim_data.get('outliers_removed', 0)
            monthly_count = dim_data.get('monthly_count', 0)
            if monthly_count > 0 and outliers / monthly_count > 0.3:
                dim_name = self.mapper.CHAOSS_DIMENSIONS.get(dimension, {}).get('name', dimension)
                high_outlier_dims.append(dim_name)
        
        if high_outlier_dims:
            if len(high_outlier_dims) >= 2:
                recommendations.append(f'{", ".join(high_outlier_dims[:2])}等维度存在较多异常值，建议检查数据质量，确保指标计算的准确性')
            else:
                recommendations.append(f'{high_outlier_dims[0]}维度存在较多异常值，建议检查数据质量，确保指标计算的准确性')
        
        return recommendations
    
    def get_dimension_mapping(self) -> Dict:
        """获取维度映射信息"""
        return {
            'dimensions': self.mapper.get_chaoss_dimensions(),
            'description': 'CHAOSS 社区健康评估维度'
        }

