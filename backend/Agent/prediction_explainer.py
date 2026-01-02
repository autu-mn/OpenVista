"""预测归因解释Agent - 使用LLM生成预测依据和风险分析"""
import os
import json
from typing import Dict, List, Optional
from datetime import datetime

try:
    from .deepseek_client import DeepSeekClient
    DEEPSEEK_AVAILABLE = True
except ImportError:
    try:
        from deepseek_client import DeepSeekClient
        DEEPSEEK_AVAILABLE = True
    except ImportError:
        DEEPSEEK_AVAILABLE = False


class PredictionExplainer:
    """预测归因解释器 - 生成预测依据、事件时间线和风险提示"""
    
    def __init__(self):
        self.use_ai = DEEPSEEK_AVAILABLE
        if self.use_ai:
            try:
                self.deepseek = DeepSeekClient()
                print("[OK] 预测解释器已启用 DeepSeek AI")
            except Exception as e:
                print(f"[WARN] DeepSeek 初始化失败: {e}")
                self.use_ai = False
                self.deepseek = None
        else:
            self.deepseek = None
    
    def generate_explanation(
        self,
        metric_name: str,
        historical_data: Dict[str, float],
        forecast_data: Dict[str, float],
        confidence: float,
        repo_context: Optional[Dict] = None,
        issue_stats: Optional[Dict] = None
    ) -> Dict:
        """
        生成预测归因解释
        
        Args:
            metric_name: 预测的指标名称
            historical_data: 历史数据 {"2020-08": 4.76, ...}
            forecast_data: 预测数据 {"2025-01": 5.2, ...}
            confidence: 预测置信度
            repo_context: 仓库上下文信息
            issue_stats: Issue统计信息
        
        Returns:
            {
                "summary": "预测摘要",
                "key_events": [{"date": "2024-03", "event": "...", "impact": "positive"}],
                "risk_alerts": [{"level": "warning", "message": "..."}],
                "driving_factors": ["因素1", "因素2"],
                "recommendations": ["建议1", "建议2"]
            }
        """
        if not self.use_ai or not self.deepseek:
            return self._generate_rule_based_explanation(
                metric_name, historical_data, forecast_data, confidence, issue_stats
            )
        
        return self._generate_ai_explanation(
            metric_name, historical_data, forecast_data, confidence, repo_context, issue_stats
        )
    
    def _generate_ai_explanation(
        self,
        metric_name: str,
        historical_data: Dict[str, float],
        forecast_data: Dict[str, float],
        confidence: float,
        repo_context: Optional[Dict],
        issue_stats: Optional[Dict]
    ) -> Dict:
        """使用AI生成解释"""
        
        # 计算趋势
        hist_values = list(historical_data.values())
        forecast_values = list(forecast_data.values())
        
        if len(hist_values) >= 2:
            recent_trend = "上升" if hist_values[-1] > hist_values[-6] else "下降"
            growth_rate = ((hist_values[-1] - hist_values[-6]) / max(hist_values[-6], 0.01)) * 100
        else:
            recent_trend = "稳定"
            growth_rate = 0
        
        forecast_trend = "上升" if forecast_values[-1] > hist_values[-1] else "下降"
        
        # 构建上下文
        context_parts = [
            f"## 预测任务",
            f"- 预测指标: {metric_name}",
            f"- 预测置信度: {confidence*100:.1f}%",
            f"- 历史数据点数: {len(historical_data)}",
            f"- 预测月数: {len(forecast_data)}",
            f"",
            f"## 历史趋势",
            f"- 最近趋势: {recent_trend}",
            f"- 近6个月增长率: {growth_rate:.1f}%",
            f"- 最新值: {hist_values[-1]:.2f}",
            f"- 预测终值: {forecast_values[-1]:.2f}",
            f"- 预测趋势: {forecast_trend}",
        ]
        
        if repo_context:
            context_parts.extend([
                f"",
                f"## 项目信息",
                f"- 项目名称: {repo_context.get('name', 'Unknown')}",
                f"- 描述: {repo_context.get('description', 'N/A')}",
                f"- 主语言: {repo_context.get('language', 'N/A')}",
                f"- Star数: {repo_context.get('stars', 0)}",
            ])
        
        if issue_stats:
            context_parts.extend([
                f"",
                f"## Issue统计",
                f"- Bug类Issue: {issue_stats.get('bug', 0)}",
                f"- Feature类Issue: {issue_stats.get('feature', 0)}",
                f"- 未分类Issue: {issue_stats.get('other', 0)}",
            ])
        
        context = "\n".join(context_parts)
        
        prompt = f"""基于以下GitHub项目数据分析，请生成预测归因解释。

{context}

请以JSON格式回复，包含以下字段：
{{
    "summary": "一句话总结预测结论和主要依据",
    "key_events": [
        {{"date": "YYYY-MM", "event": "事件描述", "impact": "positive/negative/neutral"}}
    ],
    "risk_alerts": [
        {{"level": "warning/critical/info", "message": "风险提示内容"}}
    ],
    "driving_factors": ["驱动因素1", "驱动因素2"],
    "recommendations": ["建议1", "建议2"]
}}

注意：
1. key_events 应该包含2-4个可能影响预测的关键事件（可以是预测的未来事件）
2. risk_alerts 应该包含1-3个潜在风险提示
3. driving_factors 应该包含3-5个驱动预测的主要因素
4. recommendations 应该包含2-3个建议

只返回JSON，不要其他内容。"""

        try:
            response = self.deepseek.ask(prompt, "")
            
            # 解析JSON
            try:
                # 尝试提取JSON部分
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response[json_start:json_end]
                    result = json.loads(json_str)
                    return result
            except json.JSONDecodeError:
                pass
            
            # 如果解析失败，返回基于规则的解释
            return self._generate_rule_based_explanation(
                metric_name, historical_data, forecast_data, confidence, issue_stats
            )
            
        except Exception as e:
            print(f"AI解释生成失败: {e}")
            return self._generate_rule_based_explanation(
                metric_name, historical_data, forecast_data, confidence, issue_stats
            )
    
    def _generate_rule_based_explanation(
        self,
        metric_name: str,
        historical_data: Dict[str, float],
        forecast_data: Dict[str, float],
        confidence: float,
        issue_stats: Optional[Dict]
    ) -> Dict:
        """基于规则生成解释"""
        
        hist_values = list(historical_data.values())
        forecast_values = list(forecast_data.values())
        hist_dates = list(historical_data.keys())
        forecast_dates = list(forecast_data.keys())
        
        # 趋势分析
        if len(hist_values) >= 6:
            recent_avg = sum(hist_values[-6:]) / 6
            older_avg = sum(hist_values[-12:-6]) / 6 if len(hist_values) >= 12 else recent_avg
            trend = "上升" if recent_avg > older_avg else "下降" if recent_avg < older_avg else "稳定"
            growth_rate = ((recent_avg - older_avg) / max(older_avg, 0.01)) * 100
        else:
            trend = "稳定"
            growth_rate = 0
        
        # 预测趋势
        forecast_change = forecast_values[-1] - hist_values[-1]
        forecast_trend = "增长" if forecast_change > 0 else "下降" if forecast_change < 0 else "持平"
        
        # 生成摘要
        summary = f"基于历史{len(historical_data)}个月的数据分析，{metric_name}预计将{forecast_trend}"
        if abs(growth_rate) > 10:
            summary += f"，近期{trend}趋势明显（增长率{growth_rate:.1f}%）"
        summary += f"。预测置信度为{confidence*100:.0f}%。"
        
        # 生成关键事件
        key_events = []
        
        # 找出历史高峰/低谷
        if len(hist_values) >= 3:
            max_idx = hist_values.index(max(hist_values))
            key_events.append({
                "date": hist_dates[max_idx],
                "event": f"{metric_name}达到历史峰值 ({hist_values[max_idx]:.2f})",
                "impact": "positive"
            })
        
        # 预测事件
        if forecast_values:
            key_events.append({
                "date": forecast_dates[-1],
                "event": f"预计{metric_name}将达到 {forecast_values[-1]:.2f}",
                "impact": "positive" if forecast_change > 0 else "negative"
            })
        
        # 生成风险提示
        risk_alerts = []
        
        if confidence < 0.5:
            risk_alerts.append({
                "level": "warning",
                "message": f"预测置信度较低（{confidence*100:.0f}%），建议结合其他因素综合判断"
            })
        
        if issue_stats:
            bug_count = issue_stats.get('bug', 0)
            if bug_count > 50:
                risk_alerts.append({
                    "level": "critical",
                    "message": f"Bug类Issue积压较多（{bug_count}个），可能影响项目活跃度"
                })
        
        # 波动性风险
        if len(hist_values) >= 6:
            volatility = max(hist_values[-6:]) - min(hist_values[-6:])
            avg_val = sum(hist_values[-6:]) / 6
            if volatility / max(avg_val, 0.01) > 0.5:
                risk_alerts.append({
                    "level": "info",
                    "message": "历史数据波动较大，预测结果可能存在偏差"
                })
        
        if not risk_alerts:
            risk_alerts.append({
                "level": "info",
                "message": "当前预测风险较低，建议持续关注项目动态"
            })
        
        # 驱动因素
        driving_factors = [
            f"历史{trend}趋势延续",
            "项目活跃度变化",
            "社区贡献者参与度"
        ]
        
        if abs(growth_rate) > 20:
            driving_factors.insert(0, f"近期显著{trend}（{growth_rate:.1f}%）")
        
        # 建议
        recommendations = []
        if forecast_trend == "增长":
            recommendations.append("继续保持当前发展势头，关注社区反馈")
            recommendations.append("适当增加维护投入，确保质量")
        else:
            recommendations.append("分析下降原因，采取针对性措施")
            recommendations.append("增加社区互动，提升项目活跃度")
        
        return {
            "summary": summary,
            "key_events": key_events,
            "risk_alerts": risk_alerts,
            "driving_factors": driving_factors,
            "recommendations": recommendations
        }
    
    def generate_scenario_analysis(
        self,
        metric_name: str,
        historical_data: Dict[str, float],
        baseline_forecast: Dict[str, float],
        scenario_params: Dict[str, float],
        repo_context: Optional[Dict] = None
    ) -> Dict:
        """
        生成场景模拟分析
        
        Args:
            metric_name: 指标名称
            historical_data: 历史数据
            baseline_forecast: 基线预测结果
            scenario_params: 场景参数 {"new_contributors": 10, "pr_merge_rate": 0.8, ...}
            repo_context: 仓库上下文
        
        Returns:
            {
                "adjusted_forecast": {"2025-01": 5.5, ...},
                "impact_summary": "场景影响摘要",
                "parameter_effects": [{"param": "...", "effect": "...", "magnitude": 0.1}]
            }
        """
        baseline_values = list(baseline_forecast.values())
        baseline_dates = list(baseline_forecast.keys())
        
        # 计算参数影响系数
        impact_multiplier = 1.0
        parameter_effects = []
        
        # 新增贡献者的影响
        if 'new_contributors' in scenario_params:
            nc = scenario_params['new_contributors']
            effect = 0.02 * nc  # 每个新贡献者增加2%
            impact_multiplier += effect
            parameter_effects.append({
                "param": "新增贡献者",
                "value": nc,
                "effect": f"预计提升{effect*100:.1f}%",
                "magnitude": effect
            })
        
        # PR合并率的影响
        if 'pr_merge_rate' in scenario_params:
            pmr = scenario_params['pr_merge_rate']
            effect = (pmr - 0.5) * 0.3  # 合并率每增加10%，影响3%
            impact_multiplier += effect
            parameter_effects.append({
                "param": "PR合并率",
                "value": f"{pmr*100:.0f}%",
                "effect": f"{'提升' if effect > 0 else '降低'}{abs(effect)*100:.1f}%",
                "magnitude": effect
            })
        
        # Issue解决率的影响
        if 'issue_close_rate' in scenario_params:
            icr = scenario_params['issue_close_rate']
            effect = (icr - 0.5) * 0.2
            impact_multiplier += effect
            parameter_effects.append({
                "param": "Issue解决率",
                "value": f"{icr*100:.0f}%",
                "effect": f"{'提升' if effect > 0 else '降低'}{abs(effect)*100:.1f}%",
                "magnitude": effect
            })
        
        # 版本发布的影响
        if 'major_release' in scenario_params and scenario_params['major_release']:
            effect = 0.15  # 大版本发布提升15%
            impact_multiplier += effect
            parameter_effects.append({
                "param": "大版本发布",
                "value": "是",
                "effect": f"预计提升{effect*100:.1f}%",
                "magnitude": effect
            })
        
        # 营销活动的影响
        if 'marketing_campaign' in scenario_params and scenario_params['marketing_campaign']:
            effect = 0.1
            impact_multiplier += effect
            parameter_effects.append({
                "param": "营销推广",
                "value": "是",
                "effect": f"预计提升{effect*100:.1f}%",
                "magnitude": effect
            })
        
        # 计算调整后的预测
        adjusted_forecast = {}
        for i, (date, value) in enumerate(baseline_forecast.items()):
            # 影响逐渐增强
            time_factor = (i + 1) / len(baseline_forecast)
            adjusted_value = value * (1 + (impact_multiplier - 1) * time_factor)
            adjusted_forecast[date] = round(adjusted_value, 2)
        
        # 生成影响摘要
        total_effect = impact_multiplier - 1
        if total_effect > 0.1:
            impact_summary = f"在假设场景下，{metric_name}预计将显著提升（约{total_effect*100:.1f}%），主要受益于"
            impact_summary += "、".join([pe['param'] for pe in parameter_effects if pe['magnitude'] > 0])
        elif total_effect < -0.1:
            impact_summary = f"在假设场景下，{metric_name}预计将有所下降（约{abs(total_effect)*100:.1f}%）"
        else:
            impact_summary = f"在假设场景下，{metric_name}预计变化不大（约{total_effect*100:+.1f}%）"
        
        return {
            "adjusted_forecast": adjusted_forecast,
            "baseline_forecast": baseline_forecast,
            "impact_multiplier": round(impact_multiplier, 3),
            "impact_summary": impact_summary,
            "parameter_effects": parameter_effects,
            "total_effect_percentage": round(total_effect * 100, 1)
        }




import json
from typing import Dict, List, Optional
from datetime import datetime

try:
    from .deepseek_client import DeepSeekClient
    DEEPSEEK_AVAILABLE = True
except ImportError:
    try:
        from deepseek_client import DeepSeekClient
        DEEPSEEK_AVAILABLE = True
    except ImportError:
        DEEPSEEK_AVAILABLE = False


class PredictionExplainer:
    """预测归因解释器 - 生成预测依据、事件时间线和风险提示"""
    
    def __init__(self):
        self.use_ai = DEEPSEEK_AVAILABLE
        if self.use_ai:
            try:
                self.deepseek = DeepSeekClient()
                print("[OK] 预测解释器已启用 DeepSeek AI")
            except Exception as e:
                print(f"[WARN] DeepSeek 初始化失败: {e}")
                self.use_ai = False
                self.deepseek = None
        else:
            self.deepseek = None
    
    def generate_explanation(
        self,
        metric_name: str,
        historical_data: Dict[str, float],
        forecast_data: Dict[str, float],
        confidence: float,
        repo_context: Optional[Dict] = None,
        issue_stats: Optional[Dict] = None
    ) -> Dict:
        """
        生成预测归因解释
        
        Args:
            metric_name: 预测的指标名称
            historical_data: 历史数据 {"2020-08": 4.76, ...}
            forecast_data: 预测数据 {"2025-01": 5.2, ...}
            confidence: 预测置信度
            repo_context: 仓库上下文信息
            issue_stats: Issue统计信息
        
        Returns:
            {
                "summary": "预测摘要",
                "key_events": [{"date": "2024-03", "event": "...", "impact": "positive"}],
                "risk_alerts": [{"level": "warning", "message": "..."}],
                "driving_factors": ["因素1", "因素2"],
                "recommendations": ["建议1", "建议2"]
            }
        """
        if not self.use_ai or not self.deepseek:
            return self._generate_rule_based_explanation(
                metric_name, historical_data, forecast_data, confidence, issue_stats
            )
        
        return self._generate_ai_explanation(
            metric_name, historical_data, forecast_data, confidence, repo_context, issue_stats
        )
    
    def _generate_ai_explanation(
        self,
        metric_name: str,
        historical_data: Dict[str, float],
        forecast_data: Dict[str, float],
        confidence: float,
        repo_context: Optional[Dict],
        issue_stats: Optional[Dict]
    ) -> Dict:
        """使用AI生成解释"""
        
        # 计算趋势
        hist_values = list(historical_data.values())
        forecast_values = list(forecast_data.values())
        
        if len(hist_values) >= 2:
            recent_trend = "上升" if hist_values[-1] > hist_values[-6] else "下降"
            growth_rate = ((hist_values[-1] - hist_values[-6]) / max(hist_values[-6], 0.01)) * 100
        else:
            recent_trend = "稳定"
            growth_rate = 0
        
        forecast_trend = "上升" if forecast_values[-1] > hist_values[-1] else "下降"
        
        # 构建上下文
        context_parts = [
            f"## 预测任务",
            f"- 预测指标: {metric_name}",
            f"- 预测置信度: {confidence*100:.1f}%",
            f"- 历史数据点数: {len(historical_data)}",
            f"- 预测月数: {len(forecast_data)}",
            f"",
            f"## 历史趋势",
            f"- 最近趋势: {recent_trend}",
            f"- 近6个月增长率: {growth_rate:.1f}%",
            f"- 最新值: {hist_values[-1]:.2f}",
            f"- 预测终值: {forecast_values[-1]:.2f}",
            f"- 预测趋势: {forecast_trend}",
        ]
        
        if repo_context:
            context_parts.extend([
                f"",
                f"## 项目信息",
                f"- 项目名称: {repo_context.get('name', 'Unknown')}",
                f"- 描述: {repo_context.get('description', 'N/A')}",
                f"- 主语言: {repo_context.get('language', 'N/A')}",
                f"- Star数: {repo_context.get('stars', 0)}",
            ])
        
        if issue_stats:
            context_parts.extend([
                f"",
                f"## Issue统计",
                f"- Bug类Issue: {issue_stats.get('bug', 0)}",
                f"- Feature类Issue: {issue_stats.get('feature', 0)}",
                f"- 未分类Issue: {issue_stats.get('other', 0)}",
            ])
        
        context = "\n".join(context_parts)
        
        prompt = f"""基于以下GitHub项目数据分析，请生成预测归因解释。

{context}

请以JSON格式回复，包含以下字段：
{{
    "summary": "一句话总结预测结论和主要依据",
    "key_events": [
        {{"date": "YYYY-MM", "event": "事件描述", "impact": "positive/negative/neutral"}}
    ],
    "risk_alerts": [
        {{"level": "warning/critical/info", "message": "风险提示内容"}}
    ],
    "driving_factors": ["驱动因素1", "驱动因素2"],
    "recommendations": ["建议1", "建议2"]
}}

注意：
1. key_events 应该包含2-4个可能影响预测的关键事件（可以是预测的未来事件）
2. risk_alerts 应该包含1-3个潜在风险提示
3. driving_factors 应该包含3-5个驱动预测的主要因素
4. recommendations 应该包含2-3个建议

只返回JSON，不要其他内容。"""

        try:
            response = self.deepseek.ask(prompt, "")
            
            # 解析JSON
            try:
                # 尝试提取JSON部分
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response[json_start:json_end]
                    result = json.loads(json_str)
                    return result
            except json.JSONDecodeError:
                pass
            
            # 如果解析失败，返回基于规则的解释
            return self._generate_rule_based_explanation(
                metric_name, historical_data, forecast_data, confidence, issue_stats
            )
            
        except Exception as e:
            print(f"AI解释生成失败: {e}")
            return self._generate_rule_based_explanation(
                metric_name, historical_data, forecast_data, confidence, issue_stats
            )
    
    def _generate_rule_based_explanation(
        self,
        metric_name: str,
        historical_data: Dict[str, float],
        forecast_data: Dict[str, float],
        confidence: float,
        issue_stats: Optional[Dict]
    ) -> Dict:
        """基于规则生成解释"""
        
        hist_values = list(historical_data.values())
        forecast_values = list(forecast_data.values())
        hist_dates = list(historical_data.keys())
        forecast_dates = list(forecast_data.keys())
        
        # 趋势分析
        if len(hist_values) >= 6:
            recent_avg = sum(hist_values[-6:]) / 6
            older_avg = sum(hist_values[-12:-6]) / 6 if len(hist_values) >= 12 else recent_avg
            trend = "上升" if recent_avg > older_avg else "下降" if recent_avg < older_avg else "稳定"
            growth_rate = ((recent_avg - older_avg) / max(older_avg, 0.01)) * 100
        else:
            trend = "稳定"
            growth_rate = 0
        
        # 预测趋势
        forecast_change = forecast_values[-1] - hist_values[-1]
        forecast_trend = "增长" if forecast_change > 0 else "下降" if forecast_change < 0 else "持平"
        
        # 生成摘要
        summary = f"基于历史{len(historical_data)}个月的数据分析，{metric_name}预计将{forecast_trend}"
        if abs(growth_rate) > 10:
            summary += f"，近期{trend}趋势明显（增长率{growth_rate:.1f}%）"
        summary += f"。预测置信度为{confidence*100:.0f}%。"
        
        # 生成关键事件
        key_events = []
        
        # 找出历史高峰/低谷
        if len(hist_values) >= 3:
            max_idx = hist_values.index(max(hist_values))
            key_events.append({
                "date": hist_dates[max_idx],
                "event": f"{metric_name}达到历史峰值 ({hist_values[max_idx]:.2f})",
                "impact": "positive"
            })
        
        # 预测事件
        if forecast_values:
            key_events.append({
                "date": forecast_dates[-1],
                "event": f"预计{metric_name}将达到 {forecast_values[-1]:.2f}",
                "impact": "positive" if forecast_change > 0 else "negative"
            })
        
        # 生成风险提示
        risk_alerts = []
        
        if confidence < 0.5:
            risk_alerts.append({
                "level": "warning",
                "message": f"预测置信度较低（{confidence*100:.0f}%），建议结合其他因素综合判断"
            })
        
        if issue_stats:
            bug_count = issue_stats.get('bug', 0)
            if bug_count > 50:
                risk_alerts.append({
                    "level": "critical",
                    "message": f"Bug类Issue积压较多（{bug_count}个），可能影响项目活跃度"
                })
        
        # 波动性风险
        if len(hist_values) >= 6:
            volatility = max(hist_values[-6:]) - min(hist_values[-6:])
            avg_val = sum(hist_values[-6:]) / 6
            if volatility / max(avg_val, 0.01) > 0.5:
                risk_alerts.append({
                    "level": "info",
                    "message": "历史数据波动较大，预测结果可能存在偏差"
                })
        
        if not risk_alerts:
            risk_alerts.append({
                "level": "info",
                "message": "当前预测风险较低，建议持续关注项目动态"
            })
        
        # 驱动因素
        driving_factors = [
            f"历史{trend}趋势延续",
            "项目活跃度变化",
            "社区贡献者参与度"
        ]
        
        if abs(growth_rate) > 20:
            driving_factors.insert(0, f"近期显著{trend}（{growth_rate:.1f}%）")
        
        # 建议
        recommendations = []
        if forecast_trend == "增长":
            recommendations.append("继续保持当前发展势头，关注社区反馈")
            recommendations.append("适当增加维护投入，确保质量")
        else:
            recommendations.append("分析下降原因，采取针对性措施")
            recommendations.append("增加社区互动，提升项目活跃度")
        
        return {
            "summary": summary,
            "key_events": key_events,
            "risk_alerts": risk_alerts,
            "driving_factors": driving_factors,
            "recommendations": recommendations
        }
    
    def generate_scenario_analysis(
        self,
        metric_name: str,
        historical_data: Dict[str, float],
        baseline_forecast: Dict[str, float],
        scenario_params: Dict[str, float],
        repo_context: Optional[Dict] = None
    ) -> Dict:
        """
        生成场景模拟分析
        
        Args:
            metric_name: 指标名称
            historical_data: 历史数据
            baseline_forecast: 基线预测结果
            scenario_params: 场景参数 {"new_contributors": 10, "pr_merge_rate": 0.8, ...}
            repo_context: 仓库上下文
        
        Returns:
            {
                "adjusted_forecast": {"2025-01": 5.5, ...},
                "impact_summary": "场景影响摘要",
                "parameter_effects": [{"param": "...", "effect": "...", "magnitude": 0.1}]
            }
        """
        baseline_values = list(baseline_forecast.values())
        baseline_dates = list(baseline_forecast.keys())
        
        # 计算参数影响系数
        impact_multiplier = 1.0
        parameter_effects = []
        
        # 新增贡献者的影响
        if 'new_contributors' in scenario_params:
            nc = scenario_params['new_contributors']
            effect = 0.02 * nc  # 每个新贡献者增加2%
            impact_multiplier += effect
            parameter_effects.append({
                "param": "新增贡献者",
                "value": nc,
                "effect": f"预计提升{effect*100:.1f}%",
                "magnitude": effect
            })
        
        # PR合并率的影响
        if 'pr_merge_rate' in scenario_params:
            pmr = scenario_params['pr_merge_rate']
            effect = (pmr - 0.5) * 0.3  # 合并率每增加10%，影响3%
            impact_multiplier += effect
            parameter_effects.append({
                "param": "PR合并率",
                "value": f"{pmr*100:.0f}%",
                "effect": f"{'提升' if effect > 0 else '降低'}{abs(effect)*100:.1f}%",
                "magnitude": effect
            })
        
        # Issue解决率的影响
        if 'issue_close_rate' in scenario_params:
            icr = scenario_params['issue_close_rate']
            effect = (icr - 0.5) * 0.2
            impact_multiplier += effect
            parameter_effects.append({
                "param": "Issue解决率",
                "value": f"{icr*100:.0f}%",
                "effect": f"{'提升' if effect > 0 else '降低'}{abs(effect)*100:.1f}%",
                "magnitude": effect
            })
        
        # 版本发布的影响
        if 'major_release' in scenario_params and scenario_params['major_release']:
            effect = 0.15  # 大版本发布提升15%
            impact_multiplier += effect
            parameter_effects.append({
                "param": "大版本发布",
                "value": "是",
                "effect": f"预计提升{effect*100:.1f}%",
                "magnitude": effect
            })
        
        # 营销活动的影响
        if 'marketing_campaign' in scenario_params and scenario_params['marketing_campaign']:
            effect = 0.1
            impact_multiplier += effect
            parameter_effects.append({
                "param": "营销推广",
                "value": "是",
                "effect": f"预计提升{effect*100:.1f}%",
                "magnitude": effect
            })
        
        # 计算调整后的预测
        adjusted_forecast = {}
        for i, (date, value) in enumerate(baseline_forecast.items()):
            # 影响逐渐增强
            time_factor = (i + 1) / len(baseline_forecast)
            adjusted_value = value * (1 + (impact_multiplier - 1) * time_factor)
            adjusted_forecast[date] = round(adjusted_value, 2)
        
        # 生成影响摘要
        total_effect = impact_multiplier - 1
        if total_effect > 0.1:
            impact_summary = f"在假设场景下，{metric_name}预计将显著提升（约{total_effect*100:.1f}%），主要受益于"
            impact_summary += "、".join([pe['param'] for pe in parameter_effects if pe['magnitude'] > 0])
        elif total_effect < -0.1:
            impact_summary = f"在假设场景下，{metric_name}预计将有所下降（约{abs(total_effect)*100:.1f}%）"
        else:
            impact_summary = f"在假设场景下，{metric_name}预计变化不大（约{total_effect*100:+.1f}%）"
        
        return {
            "adjusted_forecast": adjusted_forecast,
            "baseline_forecast": baseline_forecast,
            "impact_multiplier": round(impact_multiplier, 3),
            "impact_summary": impact_summary,
            "parameter_effects": parameter_effects,
            "total_effect_percentage": round(total_effect * 100, 1)
        }



