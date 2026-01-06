"""
CHAOSS 指标计算器
按月计算评分，然后去除异常值后取平均值
"""
import os
import json
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict
import statistics
import math
from .chaoss_mapper import CHAOSSMapper


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
        
        # 2. 提取所有月份
        all_months = set()
        for metric_data in timeseries_data.values():
            if isinstance(metric_data, dict) and 'raw' in metric_data:
                raw_data = metric_data['raw']
                if isinstance(raw_data, dict):
                    for month in raw_data.keys():
                        if isinstance(month, str) and len(month) == 7 and month[4] == '-':
                            all_months.add(month)
        
        if not all_months:
            return {'error': '没有可用的月份数据'}
        
        sorted_months = sorted(all_months)
        print(f"[CHAOSS] 数据范围: {sorted_months[0]} 至 {sorted_months[-1]}，共 {len(sorted_months)} 个月")
        
        # 3. 按月计算评分（使用最近N个月）
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
        
        # 4. 去除异常值后计算最终评分
        final_scores = self._calculate_final_scores(monthly_scores)
        
        # 5. 生成报告
        report = self._generate_report(final_scores, monthly_scores)
        
        return {
            'repo_key': normalized_key,
            'time_range': {
                'start': sorted_months[0],
                'end': sorted_months[-1],
                'total_months': len(sorted_months),
                'evaluated_months': len(months_to_evaluate)
            },
            'monthly_scores': monthly_scores,
            'final_scores': final_scores,
            'report': report
        }
    
    def _calculate_monthly_score(self, timeseries_data: Dict, month: str) -> Optional[Dict]:
        """
        计算单个月的评分
        
        会检查数据质量，如果数据不足或质量太低则返回None
        """
        dimension_scores = {}
        total_metrics_count = 0  # 总指标数
        valid_metrics_count = 0  # 有效指标数
        
        chaoss_dimensions = self.mapper.get_chaoss_dimensions()
        
        # 统计总指标数
        for dimension_info in chaoss_dimensions.values():
            total_metrics_count += len(dimension_info['metrics'])
        
        for dimension, dimension_info in chaoss_dimensions.items():
            dimension_metrics = dimension_info['metrics']
            metric_scores = []
            metric_weights = []
            
            for metric_key, metric_info in dimension_metrics.items():
                if metric_key in timeseries_data:
                    metric_data = timeseries_data[metric_key]
                    if isinstance(metric_data, dict) and 'raw' in metric_data:
                        raw_data = metric_data['raw']
                        if isinstance(raw_data, dict) and month in raw_data:
                            value = raw_data[month]
                            # 检查值是否有效：非None、非负数、非NaN、非Inf
                            if value is not None and isinstance(value, (int, float)):
                                if not (math.isnan(value) or math.isinf(value)) and value >= 0:
                                    # 获取历史最大值用于归一化
                                    all_values = [v for v in raw_data.values() 
                                                if v is not None and isinstance(v, (int, float))
                                                and not (math.isnan(v) or math.isinf(v)) and v >= 0]
                                    if all_values:
                                        max_value = max(all_values)
                                        if max_value > 0:
                                            # 归一化到0-100
                                            normalized = min(100, (value / max_value * 100))
                                            metric_scores.append(normalized)
                                            metric_weights.append(metric_info['weight'])
                                            valid_metrics_count += 1
            
            if metric_scores:
                # 加权平均
                if metric_weights and len(metric_weights) == len(metric_scores):
                    weighted_sum = sum(s * w for s, w in zip(metric_scores, metric_weights))
                    total_weight = sum(metric_weights)
                    dimension_score = weighted_sum / total_weight if total_weight > 0 else 0
                else:
                    dimension_score = sum(metric_scores) / len(metric_scores)
                
                dimension_scores[dimension] = {
                    'score': round(dimension_score, 1),
                    'metrics_count': len(metric_scores)
                }
        
        # 数据质量检测：如果有效指标少于总指标的30%，则认为数据不足，跳过该月份
        if total_metrics_count > 0:
            data_quality_ratio = valid_metrics_count / total_metrics_count
            if data_quality_ratio < 0.3:  # 数据质量低于30%
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
    
    def _calculate_final_scores(self, monthly_scores: List[Dict]) -> Dict:
        """
        去除异常值后计算最终评分
        
        使用IQR方法检测异常值，然后计算平均值
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
                    'score': dim_data['score']
                })
        
        # 计算总体得分的最终值（去除异常值）
        final_overall = self._remove_outliers_and_average(overall_scores)
        
        # 计算各维度的最终得分
        final_dimensions = {}
        for dimension, scores_list in dimension_monthly_scores.items():
            scores = [s['score'] for s in scores_list]
            final_score = self._remove_outliers_and_average(scores)
            final_dimensions[dimension] = {
                'score': round(final_score, 1),
                'level': self._get_score_level(final_score),
                'monthly_count': len(scores),
                'outliers_removed': len(scores) - len(self._get_valid_scores(scores))
            }
        
        return {
            'overall_score': round(final_overall, 1),
            'overall_level': self._get_score_level(final_overall),
            'dimensions': final_dimensions
        }
    
    def _remove_outliers_and_average(self, scores: List[float]) -> float:
        """
        使用IQR方法去除异常值后计算平均值
        
        Args:
            scores: 得分列表
            
        Returns:
            去除异常值后的平均值
        """
        if not scores:
            return 0.0
        
        if len(scores) < 4:
            # 数据点太少，直接返回平均值
            return sum(scores) / len(scores)
        
        # 计算IQR
        sorted_scores = sorted(scores)
        q1 = self._percentile(sorted_scores, 25)
        q3 = self._percentile(sorted_scores, 75)
        iqr = q3 - q1
        
        if iqr == 0:
            # 如果IQR为0，说明所有值相同，直接返回平均值
            return sum(scores) / len(scores)
        
        # 使用1.5倍IQR作为异常值阈值（标准方法）
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        # 过滤异常值
        valid_scores = [s for s in scores if lower_bound <= s <= upper_bound]
        
        if not valid_scores:
            # 如果所有值都被过滤，使用原始平均值
            valid_scores = scores
        
        return sum(valid_scores) / len(valid_scores)
    
    def _get_valid_scores(self, scores: List[float]) -> List[float]:
        """获取去除异常值后的有效得分"""
        if len(scores) < 4:
            return scores
        
        sorted_scores = sorted(scores)
        q1 = self._percentile(sorted_scores, 25)
        q3 = self._percentile(sorted_scores, 75)
        iqr = q3 - q1
        
        if iqr == 0:
            return scores
        
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
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
        """生成评价报告"""
        recommendations = []
        
        overall_score = final_scores.get('overall_score', 0)
        
        if overall_score < 40:
            recommendations.append('项目整体健康度较低，建议加强社区建设和代码质量管控')
        elif overall_score < 60:
            recommendations.append('项目健康度中等，有改进空间，建议持续优化')
        else:
            recommendations.append('项目健康度良好，继续保持当前发展态势')
        
        # 分析各维度
        dimensions = final_scores.get('dimensions', {})
        for dimension, dim_data in dimensions.items():
            score = dim_data.get('score', 0)
            if score < 40:
                dim_name = self.mapper.CHAOSS_DIMENSIONS.get(dimension, {}).get('name', dimension)
                recommendations.append(f'{dim_name}维度得分较低({score:.1f}分)，需要重点关注')
        
        return {
            'summary': f'综合评分: {overall_score:.1f}分 ({final_scores.get("overall_level", "未知")})',
            'recommendations': recommendations
        }
    
    def get_dimension_mapping(self) -> Dict:
        """获取维度映射信息"""
        return {
            'dimensions': self.mapper.get_chaoss_dimensions(),
            'description': 'CHAOSS 社区健康评估维度'
        }

