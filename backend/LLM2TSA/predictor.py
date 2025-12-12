"""
LLM为中心的预测器 - 模块2核心实现
使用LLM进行时序预测，无需训练传统时序模型
"""

import os
import json
import re
import hashlib
import warnings
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

# Prophet导入（可选，如果没安装会fallback到简单方法）
try:
    from prophet import Prophet
    import pandas as pd
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False
    warnings.warn("Prophet未安装，将使用简单线性外推。安装命令: pip install prophet")


class LLMClient:
    """LLM客户端封装"""
    
    def __init__(self):
        self.client = None
        self._init_client()
    
    def _init_client(self):
        """初始化LLM客户端"""
        try:
            from Agent.deepseek_client import DeepSeekClient
            self.client = DeepSeekClient()
            print("[OK] DeepSeek客户端初始化成功")
        except Exception as e:
            print(f"[WARN] LLM客户端初始化失败: {e}")
            self.client = None
    
    def generate(self, prompt: str, max_tokens: int = 2000) -> str:
        """生成文本"""
        if not self.client:
            return "[LLM不可用]"
        
        try:
            result = self.client.ask(prompt, context="")
            return result.strip() if result else "[生成失败]"
        except Exception as e:
            print(f"  [WARN] LLM生成失败: {e}")
            return "[生成失败]"


class PredictionCache:
    """预测结果缓存"""
    
    def __init__(self, cache_dir: str = None):
        self.cache_dir = cache_dir or os.path.join(os.path.dirname(__file__), 'cache')
        os.makedirs(self.cache_dir, exist_ok=True)
        self.memory_cache = {}
    
    def _get_cache_key(self, metric_name: str, historical_data: Dict, forecast_months: int) -> str:
        """生成缓存键"""
        # 只使用最近24个月的数据和关键参数生成缓存键
        recent_data = dict(list(historical_data.items())[-24:])
        cache_data = {
            'metric': metric_name,
            'data': recent_data,
            'months': forecast_months
        }
        data_str = json.dumps(cache_data, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(data_str.encode()).hexdigest()
    
    def get(self, metric_name: str, historical_data: Dict, forecast_months: int) -> Optional[Dict]:
        """获取缓存"""
        key = self._get_cache_key(metric_name, historical_data, forecast_months)
        
        # 先查内存缓存
        if key in self.memory_cache:
            return self.memory_cache[key]
        
        # 再查文件缓存
        cache_file = os.path.join(self.cache_dir, f"predict_{key}.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached = json.load(f)
                    # 检查缓存是否过期（24小时）
                    cache_time = datetime.fromisoformat(cached.get('timestamp', '2000-01-01'))
                    if (datetime.now() - cache_time).total_seconds() < 86400:
                        self.memory_cache[key] = cached['result']
                        return cached['result']
            except:
                pass
        
        return None
    
    def set(self, metric_name: str, historical_data: Dict, forecast_months: int, result: Dict):
        """设置缓存"""
        key = self._get_cache_key(metric_name, historical_data, forecast_months)
        self.memory_cache[key] = result
        
        # 写入文件缓存
        cache_file = os.path.join(self.cache_dir, f"predict_{key}.json")
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'metric': metric_name,
                    'forecast_months': forecast_months,
                    'result': result,
                    'timestamp': datetime.now().isoformat()
                }, f, ensure_ascii=False, indent=2)
        except:
            pass


class LLMTimeSeriesPredictor:
    """
    LLM时序预测器
    
    功能：
    1. 基于历史数据预测未来值
    2. 提供置信度和预测理由
    3. 支持多种时序指标预测
    """
    
    def __init__(self, enable_cache: bool = True):
        self.llm_client = LLMClient()
        self.cache = PredictionCache() if enable_cache else None
    
    def predict(self, metric_name: str, historical_data: Dict[str, float], 
                forecast_months: int = 6, include_reasoning: bool = True,
                text_timeseries: Dict[str, Dict] = None, repo_context: str = None) -> Dict:
        """
        预测未来时序值（融合文本时序数据）
        
        参数:
            metric_name: 指标名称，如 "OpenRank"、"活跃度"
            historical_data: 历史数据 {"2020-08": 4.76, ..., "2025-11": 4.58}
            forecast_months: 预测月数，默认6个月
            include_reasoning: 是否包含预测理由
            text_timeseries: 文本时序数据 {"2020-08": {"hottest_issue": {...}, ...}, ...}
            repo_context: 仓库上下文信息（如仓库描述、主要技术栈）
        
        返回:
        {
            "forecast": {
                "2025-12": 4.8,
                "2026-01": 5.1,
                ...
            },
            "confidence": 0.75,  # 基于数据质量、趋势稳定性等科学计算
            "confidence_factors": {  # 置信度因子详情
                "data_completeness": 0.95,
                "trend_stability": 0.80,
                "data_volume": 0.85,
                "text_alignment": 0.70
            },
            "reasoning": "基于历史趋势和关键事件分析...",
            "trend_analysis": {
                "direction": "上升",
                "strength": "中等",
                "volatility": "低"
            },
            "key_events": [...]  # 影响预测的关键事件
        }
        """
        if not historical_data:
            return {
                "forecast": {},
                "confidence": 0.0,
                "reasoning": "历史数据为空，无法进行预测",
                "error": "No historical data"
            }
        
        # 检查缓存（注意：加入了文本数据，缓存键需要考虑文本）
        # 为了简化，我们先不缓存融合文本的预测
        
        # 1. 数据质量分析
        data_quality = self._analyze_data_quality(historical_data)
        
        # 2. 格式化历史数据
        formatted_data = self._format_timeseries(historical_data)
        
        # 3. 分析历史趋势
        trend_analysis = self._analyze_trend(historical_data)
        
        # 4. 提取关键事件（从文本时序数据）
        key_events = self._extract_key_events(historical_data, text_timeseries, trend_analysis)
        
        # 5. 计算科学置信度
        confidence_factors = self._calculate_confidence_factors(
            historical_data, trend_analysis, text_timeseries
        )
        
        # 6. 构建预测 Prompt（融合文本和趋势）
        prompt = self._build_enhanced_predict_prompt(
            metric_name, formatted_data, forecast_months, trend_analysis, 
            key_events, repo_context, include_reasoning
        )
        
        # 7. 调用 LLM
        print(f"  [LLM预测] {metric_name}, 预测{forecast_months}个月...")
        print(f"  [数据质量] 完整性:{data_quality['completeness']:.2%}, 异常值:{data_quality['outlier_count']}个")
        response = self.llm_client.generate(prompt, max_tokens=2000)
        
        # 8. 解析结果
        result = self._parse_prediction(response, historical_data, forecast_months)
        
        # 9. 添加增强信息
        result['trend_analysis'] = trend_analysis
        result['key_events'] = key_events
        result['confidence_factors'] = confidence_factors
        result['confidence'] = sum(confidence_factors.values()) / len(confidence_factors)  # 综合置信度
        result['data_quality'] = data_quality
        
        return result
    
    def _format_timeseries(self, data: Dict[str, float]) -> str:
        """将时序数据格式化为文本"""
        # 使用表格格式，显示最近24个月的数据
        sorted_items = sorted(data.items())
        recent_items = sorted_items[-24:] if len(sorted_items) > 24 else sorted_items
        
        lines = ["时间\t值"]
        for date, value in recent_items:
            if value is not None:
                lines.append(f"{date}\t{value:.2f}")
        
        return "\n".join(lines)
    
    def _analyze_trend(self, data: Dict[str, float]) -> Dict:
        """分析历史趋势"""
        if len(data) < 2:
            return {
                "direction": "未知",
                "strength": "未知",
                "volatility": "未知"
            }
        
        sorted_items = sorted([(k, v) for k, v in data.items() if v is not None])
        if len(sorted_items) < 2:
            return {
                "direction": "未知",
                "strength": "未知",
                "volatility": "未知"
            }
        
        values = [v for _, v in sorted_items]
        
        # 计算趋势方向
        first_half = values[:len(values)//2]
        second_half = values[len(values)//2:]
        first_avg = sum(first_half) / len(first_half) if first_half else 0
        second_avg = sum(second_half) / len(second_half) if second_half else 0
        
        if second_avg > first_avg * 1.1:
            direction = "上升"
        elif second_avg < first_avg * 0.9:
            direction = "下降"
        else:
            direction = "稳定"
        
        # 计算变化强度
        change_rate = abs((second_avg - first_avg) / first_avg * 100) if first_avg > 0 else 0
        if change_rate > 30:
            strength = "强"
        elif change_rate > 10:
            strength = "中等"
        else:
            strength = "弱"
        
        # 计算波动性（标准差）
        if len(values) > 1:
            mean_val = sum(values) / len(values)
            variance = sum((v - mean_val) ** 2 for v in values) / len(values)
            std_dev = variance ** 0.5
            cv = std_dev / mean_val if mean_val > 0 else 0  # 变异系数
            
            if cv > 0.3:
                volatility = "高"
            elif cv > 0.15:
                volatility = "中等"
            else:
                volatility = "低"
        else:
            volatility = "未知"
        
        return {
            "direction": direction,
            "strength": strength,
            "volatility": volatility,
            "recent_avg": round(second_avg, 2),
            "change_rate": round(change_rate, 1),
            "coefficient_of_variation": round(cv, 3) if len(values) > 1 else 0
        }
    
    def _analyze_data_quality(self, data: Dict[str, float]) -> Dict:
        """分析数据质量"""
        if not data:
            return {
                "completeness": 0.0,
                "outlier_count": 0,
                "missing_count": 0,
                "total_points": 0
            }
        
        values = [v for v in data.values() if v is not None]
        total_points = len(data)
        missing_count = total_points - len(values)
        completeness = len(values) / total_points if total_points > 0 else 0
        
        # 检测异常值（使用IQR方法）
        outlier_count = 0
        if len(values) >= 4:
            sorted_values = sorted(values)
            q1_idx = len(sorted_values) // 4
            q3_idx = 3 * len(sorted_values) // 4
            q1 = sorted_values[q1_idx]
            q3 = sorted_values[q3_idx]
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            outlier_count = sum(1 for v in values if v < lower_bound or v > upper_bound)
        
        return {
            "completeness": round(completeness, 3),
            "outlier_count": outlier_count,
            "missing_count": missing_count,
            "total_points": total_points
        }
    
    def _extract_key_events(self, historical_data: Dict[str, float], 
                           text_timeseries: Dict[str, Dict], 
                           trend_analysis: Dict) -> List[Dict]:
        """从文本时序数据中提取关键事件"""
        if not text_timeseries:
            return []
        
        key_events = []
        sorted_months = sorted(historical_data.keys())
        
        # 找出指标变化最大的月份
        changes = []
        for i in range(1, len(sorted_months)):
            prev_month = sorted_months[i-1]
            curr_month = sorted_months[i]
            prev_val = historical_data.get(prev_month)
            curr_val = historical_data.get(curr_month)
            
            if prev_val and curr_val and prev_val > 0:
                change_rate = (curr_val - prev_val) / prev_val * 100
                if abs(change_rate) > 15:  # 变化超过15%
                    changes.append((curr_month, change_rate))
        
        # 对于变化显著的月份，提取文本事件
        for month, change_rate in sorted(changes, key=lambda x: abs(x[1]), reverse=True)[:5]:
            if month in text_timeseries:
                text_data = text_timeseries[month]
                event = {
                    "month": month,
                    "change_rate": round(change_rate, 1),
                    "direction": "上升" if change_rate > 0 else "下降"
                }
                
                # 提取Issue/PR/Commit信息
                if text_data.get('hottest_issue'):
                    event['issue'] = text_data['hottest_issue'].get('title', '')[:100]
                if text_data.get('hottest_pr'):
                    event['pr'] = text_data['hottest_pr'].get('title', '')[:100]
                if text_data.get('hottest_commit'):
                    event['commit'] = text_data['hottest_commit'].get('message', '')[:100]
                
                key_events.append(event)
        
        return key_events
    
    def _calculate_confidence_factors(self, historical_data: Dict[str, float],
                                      trend_analysis: Dict,
                                      text_timeseries: Dict[str, Dict] = None) -> Dict:
        """
        计算科学的置信度因子
        
        置信度由以下因素决定：
        1. data_completeness: 数据完整性（缺失值比例）
        2. trend_stability: 趋势稳定性（基于变异系数）
        3. data_volume: 数据量充足性（样本数量）
        4. text_alignment: 文本数据对齐度（如果有文本数据）
        """
        factors = {}
        
        # 1. 数据完整性 (0-1)
        values = [v for v in historical_data.values() if v is not None]
        completeness = len(values) / len(historical_data) if historical_data else 0
        factors['data_completeness'] = round(completeness, 3)
        
        # 2. 趋势稳定性 (0-1)
        # 基于变异系数：CV越小，趋势越稳定
        cv = trend_analysis.get('coefficient_of_variation', 0)
        if cv == 0:
            stability = 0.5  # 无法判断
        elif cv < 0.1:
            stability = 0.95
        elif cv < 0.2:
            stability = 0.85
        elif cv < 0.3:
            stability = 0.70
        elif cv < 0.5:
            stability = 0.50
        else:
            stability = 0.30
        factors['trend_stability'] = round(stability, 3)
        
        # 3. 数据量充足性 (0-1)
        # 至少需要12个月数据才能较好预测
        data_count = len(values)
        if data_count >= 24:
            volume_score = 0.95
        elif data_count >= 12:
            volume_score = 0.80
        elif data_count >= 6:
            volume_score = 0.60
        else:
            volume_score = 0.40
        factors['data_volume'] = round(volume_score, 3)
        
        # 4. 文本数据对齐度 (0-1)
        if text_timeseries:
            # 计算有文本数据的月份比例
            months_with_text = sum(1 for month in historical_data.keys() 
                                  if month in text_timeseries and text_timeseries[month])
            alignment = months_with_text / len(historical_data) if historical_data else 0
            factors['text_alignment'] = round(alignment, 3)
        else:
            # 没有文本数据，不影响置信度（使用中性值）
            factors['text_alignment'] = 0.50
        
        return factors
    
    def _build_enhanced_predict_prompt(self, metric_name: str, formatted_data: str, 
                                      forecast_months: int, trend_analysis: Dict,
                                      key_events: List[Dict], repo_context: str,
                                      include_reasoning: bool) -> str:
        """构建增强的预测 Prompt（融合文本和时序数据）"""
        
        # 构建关键事件描述
        events_desc = ""
        if key_events:
            events_desc = "\n【关键事件与指标变化】\n"
            for event in key_events[:5]:  # 最多5个关键事件
                month = event['month']
                change = event['change_rate']
                direction = event['direction']
                events_desc += f"\n{month} ({direction}{abs(change):.1f}%):\n"
                if event.get('issue'):
                    events_desc += f"  - Issue: {event['issue']}\n"
                if event.get('pr'):
                    events_desc += f"  - PR: {event['pr']}\n"
                if event.get('commit'):
                    events_desc += f"  - Commit: {event['commit']}\n"
        
        # 构建仓库上下文
        context_desc = ""
        if repo_context:
            context_desc = f"\n【项目背景】\n{repo_context}\n"
        
        prompt = f"""你是一个专业的开源项目时序数据分析专家。请基于历史数据、趋势分析和关键事件，预测未来{forecast_months}个月的{metric_name}指标值。

{context_desc}
【指标名称】
{metric_name}

【历史数据】（最近24个月）
{formatted_data}

【趋势分析】
- 趋势方向：{trend_analysis.get('direction', '未知')}
- 变化强度：{trend_analysis.get('strength', '未知')}
- 波动性：{trend_analysis.get('volatility', '未知')}（变异系数：{trend_analysis.get('coefficient_of_variation', 0):.3f}）
- 最近平均值：{trend_analysis.get('recent_avg', 0)}
- 变化率：{trend_analysis.get('change_rate', 0)}%
{events_desc}

【预测策略】
1. **趋势延续**：分析历史趋势是否会延续，考虑增长/下降的可持续性
2. **事件影响**：关键事件（重大Issue/PR/Commit）对指标的影响是短期还是长期
3. **季节性模式**：是否存在周期性波动（如年度发布、假期影响）
4. **回归均值**：极端值后通常会回归到正常水平
5. **波动性考虑**：历史波动性高的指标，预测应更保守

【输出要求】
请严格按照以下JSON格式输出：
```json
{{
    "forecast": {{
        "2025-12": <预测值>,
        "2026-01": <预测值>,
        ...
    }},
    "reasoning": "<150字以内的预测理由，说明：1)主要依据的趋势 2)关键事件的影响 3)预测的不确定性>"
}}
```

**重要提示**：
- 预测值应基于数据和事件的综合分析，不要简单线性外推
- 如果关键事件显示项目活跃度变化，预测应反映这种变化
- 波动性高的指标，预测变化幅度应更小
- reasoning必须结合历史趋势和关键事件，不要只描述数字
"""
        
        return prompt
    
    def _parse_prediction(self, response: str, historical_data: Dict[str, float],
                         forecast_months: int) -> Dict:
        """解析LLM返回的预测结果"""
        
        # 尝试提取JSON
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
        if not json_match:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
        
        if json_match:
            try:
                result = json.loads(json_match.group(1))
                
                # 验证和修复预测结果
                forecast = result.get('forecast', {})
                if not forecast:
                    return self._generate_fallback_prediction(historical_data, forecast_months)
                
                # 确保月份格式正确
                fixed_forecast = {}
                last_date = max(historical_data.keys())
                last_year, last_month = map(int, last_date.split('-'))
                
                for i in range(1, forecast_months + 1):
                    # 计算目标月份
                    target_month = last_month + i
                    target_year = last_year
                    while target_month > 12:
                        target_month -= 12
                        target_year += 1
                    target_str = f"{target_year:04d}-{target_month:02d}"
                    
                    # 尝试从LLM结果中获取，如果没有则使用最后一个值
                    if target_str in forecast:
                        fixed_forecast[target_str] = forecast[target_str]
                    else:
                        # 使用最后一个历史值作为fallback
                        last_value = list(historical_data.values())[-1]
                        fixed_forecast[target_str] = last_value
                
                result['forecast'] = fixed_forecast
                
                # 确保置信度在合理范围内
                confidence = result.get('confidence', 0.5)
                if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
                    confidence = 0.5
                result['confidence'] = round(float(confidence), 2)
                
                # 确保reasoning存在
                if 'reasoning' not in result or not result['reasoning']:
                    result['reasoning'] = "基于历史趋势进行预测"
                
                return result
                
            except json.JSONDecodeError as e:
                print(f"  [WARN] JSON解析失败: {e}")
        
        # 如果解析失败，生成fallback预测
        print("  [WARN] LLM返回格式不正确，使用fallback预测")
        return self._generate_fallback_prediction(historical_data, forecast_months)
    
    def _generate_fallback_prediction(self, historical_data: Dict[str, float],
                                     forecast_months: int) -> Dict:
        """生成fallback预测（简单线性外推）"""
        if not historical_data:
            return {
                "forecast": {},
                "confidence": 0.0,
                "reasoning": "历史数据不足，无法进行预测"
            }
        
        sorted_items = sorted([(k, v) for k, v in historical_data.items() if v is not None])
        if len(sorted_items) < 2:
            last_value = sorted_items[0][1] if sorted_items else 0
            forecast = {}
            last_date = max(historical_data.keys())
            last_year, last_month = map(int, last_date.split('-'))
            
            for i in range(1, forecast_months + 1):
                # 计算目标月份
                target_month = last_month + i
                target_year = last_year
                while target_month > 12:
                    target_month -= 12
                    target_year += 1
                target_str = f"{target_year:04d}-{target_month:02d}"
                forecast[target_str] = last_value
            
            return {
                "forecast": forecast,
                "confidence": 0.3,
                "reasoning": "历史数据不足，使用最后一个值作为预测"
            }
        
        # 计算简单线性趋势
        values = [v for _, v in sorted_items[-6:]]  # 使用最近6个月
        if len(values) >= 2:
            # 计算平均变化率
            changes = [values[i] - values[i-1] for i in range(1, len(values))]
            avg_change = sum(changes) / len(changes) if changes else 0
            last_value = values[-1]
        else:
            avg_change = 0
            last_value = sorted_items[-1][1]
        
        # 生成预测
        forecast = {}
        last_date = max(historical_data.keys())
        last_year, last_month = map(int, last_date.split('-'))
        
        for i in range(1, forecast_months + 1):
            # 计算目标月份
            target_month = last_month + i
            target_year = last_year
            while target_month > 12:
                target_month -= 12
                target_year += 1
            target_str = f"{target_year:04d}-{target_month:02d}"
            # 简单线性外推，但限制变化幅度
            predicted_value = last_value + avg_change * i
            # 确保预测值不会出现极端变化（限制在±50%以内）
            if last_value > 0:
                predicted_value = max(last_value * 0.5, min(last_value * 1.5, predicted_value))
            forecast[target_str] = round(predicted_value, 2)
        
        return {
            "forecast": forecast,
            "confidence": 0.4,
            "reasoning": "使用简单线性外推进行预测，置信度较低"
        }
    
    def predict_multiple(self, metrics_data: Dict[str, Dict[str, float]], 
                        forecast_months: int = 6) -> Dict[str, Dict]:
        """
        批量预测多个指标
        
        参数:
            metrics_data: {"OpenRank": {"2020-08": 4.76, ...}, "活跃度": {...}}
            forecast_months: 预测月数
        
        返回:
            {"OpenRank": {预测结果}, "活跃度": {预测结果}}
        """
        results = {}
        for metric_name, historical_data in metrics_data.items():
            print(f"[批量预测] {metric_name}...")
            results[metric_name] = self.predict(metric_name, historical_data, forecast_months)
        
        return results

