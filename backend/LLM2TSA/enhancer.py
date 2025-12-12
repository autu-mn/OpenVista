"""
LLM辅助增强器 - 模块1核心实现
为时序数据添加语义信息，提升可解释性
"""

import os
import json
import hashlib
from typing import Dict, List, Optional, Tuple
from datetime import datetime


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
    
    def generate(self, prompt: str, max_tokens: int = 1000) -> str:
        """生成文本"""
        if not self.client:
            return "[LLM不可用]"
        
        try:
            result = self.client.ask(prompt, context="")
            return result.strip() if result else "[生成失败]"
        except Exception as e:
            print(f"  [WARN] LLM生成失败: {e}")
            return "[生成失败]"


class EnhancerCache:
    """增强结果缓存"""
    
    def __init__(self, cache_dir: str = None):
        self.cache_dir = cache_dir or os.path.join(os.path.dirname(__file__), 'cache')
        os.makedirs(self.cache_dir, exist_ok=True)
        self.memory_cache = {}
    
    def _get_cache_key(self, data: dict) -> str:
        """生成缓存键"""
        data_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(data_str.encode()).hexdigest()
    
    def get(self, data: dict) -> Optional[str]:
        """获取缓存"""
        key = self._get_cache_key(data)
        
        # 先查内存缓存
        if key in self.memory_cache:
            return self.memory_cache[key]
        
        # 再查文件缓存
        cache_file = os.path.join(self.cache_dir, f"{key}.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached = json.load(f)
                    self.memory_cache[key] = cached['result']
                    return cached['result']
            except:
                pass
        
        return None
    
    def set(self, data: dict, result: str):
        """设置缓存"""
        key = self._get_cache_key(data)
        self.memory_cache[key] = result
        
        # 写入文件缓存
        cache_file = os.path.join(self.cache_dir, f"{key}.json")
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'data': data,
                    'result': result,
                    'timestamp': datetime.now().isoformat()
                }, f, ensure_ascii=False, indent=2)
        except:
            pass


class TimeSeriesEnhancer:
    """
    时序数据增强器
    
    功能：
    1. 单月数据增强：生成综合描述
    2. 趋势识别增强：识别趋势并关联事件
    3. 关键点增强：解释峰值/谷值
    4. 语义特征提取：生成语义标签
    """
    
    def __init__(self, use_cache: bool = True):
        self.llm = LLMClient()
        self.cache = EnhancerCache() if use_cache else None
    
    # ========== 1. 单月数据增强 ==========
    
    def enhance_month(self, month: str, metrics: Dict, text_data: Dict) -> str:
        """
        为单月数据生成综合描述
        
        参数:
            month: 月份 "2020-08"
            metrics: 数值指标 {"OpenRank": 4.76, "Star数": 10, ...}
            text_data: 文本数据 {"hottest_issue": {...}, "hottest_pr": {...}, ...}
        
        返回:
            综合描述字符串
        """
        # 检查缓存
        cache_key = {'type': 'month', 'month': month, 'metrics': metrics, 'text_data': text_data}
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached
        
        # 准备指标描述（优先显示重要指标）- 完整版
        important_metrics = [
            # 基础活跃度指标
            'OpenRank', 'opendigger_OpenRank', '影响力',
            '活跃度', 'opendigger_活跃度', 'Activity',
            'Star数', 'opendigger_Star数', 'stars',
            'Fork数', 'opendigger_Fork数', 'forks',
            'Watch数', 'opendigger_Watch数', 'watchers',
            
            # Issue相关
            '新增Issue', 'opendigger_新增Issue', 'issues_opened',
            '已关闭Issue', 'opendigger_已关闭Issue', 'issues_closed',
            'Issue评论数', 'opendigger_Issue评论数', 'issue_comments',
            'Issue响应时间', 'opendigger_Issue响应时间', 'issue_response_time',
            'Issue解决时间', 'opendigger_Issue解决时间', 'issue_resolution_time',
            'avg_issue_response_days', 'avg_issue_resolution_days', 'avg_issue_lifetime_days',
            
            # PR相关
            'PR接受数', 'opendigger_PR接受数', 'pull_requests_accepted',
            'PR拒绝数', 'opendigger_PR拒绝数', 'pull_requests_declined',
            '新增PR', 'opendigger_新增PR', 'pull_requests_opened',
            'PR处理时间', 'opendigger_PR处理时间', 'pr_processing_time',
            'PR响应时间', 'opendigger_PR响应时间', 'pr_response_time',
            'avg_pr_response_days', 'avg_pr_processing_days', 'avg_pr_lifetime_days',
            
            # 代码提交
            '代码提交数', 'opendigger_代码提交数', 'commits',
            '代码变更行数', 'opendigger_代码变更行数', 'code_changes',
            '代码增加行数', 'opendigger_代码增加行数', 'lines_added',
            '代码删除行数', 'opendigger_代码删除行数', 'lines_deleted',
            
            # 贡献者
            '参与者数', 'opendigger_参与者数', 'participants',
            '新增贡献者数', 'opendigger_新增贡献者数', 'new_contributors',
            '活跃贡献者数', 'opendigger_活跃贡献者数', 'active_contributors',
            '核心贡献者数', 'opendigger_核心贡献者数', 'core_contributors',
            'total_contributors',
            
            # GitHub API补充指标
            'issues_count', 'prs_count', 'commits_count',
            'contributors_count', 'releases_count',
            'avg_issue_hot_score', 'avg_pr_hot_score',
            'activity_score', 'community_engagement'
        ]
        
        metrics_desc = []
        # 先添加重要指标
        for metric_name in important_metrics:
            value = metrics.get(metric_name)
            if value is not None:
                # 简化指标名称
                simple_name = metric_name.replace('opendigger_', '').replace('github_api_', '')
                metrics_desc.append(f"{simple_name}: {value}")
        
        # 再添加其他指标（避免重复）
        for name, value in metrics.items():
            if value is not None and name not in important_metrics:
                simple_name = name.replace('opendigger_', '').replace('github_api_', '')
                if simple_name not in [m.split(':')[0] for m in metrics_desc]:
                    metrics_desc.append(f"{simple_name}: {value}")
        
        metrics_str = ", ".join(metrics_desc) if metrics_desc else "无数据"
        
        # 准备文本事件描述
        issue_title = text_data.get('hottest_issue', {}).get('title', '') if text_data.get('hottest_issue') else ''
        pr_title = text_data.get('hottest_pr', {}).get('title', '') if text_data.get('hottest_pr') else ''
        commit_msg = text_data.get('hottest_commit', {}).get('message', '') if text_data.get('hottest_commit') else ''
        
        prompt = f"""请为以下开源项目的{month}月数据生成简洁的综合描述（80字以内）：

【数值指标】
{metrics_str}

【重要事件】
- 热门Issue: {issue_title or '无'}
- 热门PR: {pr_title or '无'}
- 重要Commit: {commit_msg[:100] if commit_msg else '无'}

要求：
1. 描述该月项目的整体状态
2. 如果有显著的指标变化或事件，简要提及
3. 语言简洁自然，不要堆砌数据"""
        
        result = self.llm.generate(prompt, max_tokens=200)
        
        # 如果LLM失败，使用规则生成
        if result in ["[LLM不可用]", "[生成失败]"]:
            result = self._fallback_month_description(month, metrics, text_data)
        
        # 缓存结果
        if self.cache:
            self.cache.set(cache_key, result)
        
        return result
    
    def _fallback_month_description(self, month: str, metrics: Dict, text_data: Dict) -> str:
        """规则生成的月度描述（降级方案）"""
        openrank = metrics.get('OpenRank') or metrics.get('opendigger_OpenRank')
        activity = metrics.get('活跃度') or metrics.get('opendigger_活跃度')
        
        desc = f"{month}月"
        if openrank:
            desc += f"，OpenRank为{openrank:.2f}"
        if activity:
            desc += f"，活跃度{activity:.2f}"
        
        issue = text_data.get('hottest_issue')
        if issue and issue.get('title'):
            desc += f"。热门Issue：{issue['title'][:30]}"
        
        return desc if len(desc) > 10 else f"{month}月项目运行平稳。"
    
    # ========== 2. 趋势识别增强 ==========
    
    def detect_trends(self, timeseries_data: Dict[str, Dict], 
                      text_timeseries: Dict[str, Dict]) -> List[Dict]:
        """
        识别趋势并关联文本事件
        
        参数:
            timeseries_data: 按月组织的指标数据 {"2020-08": {"OpenRank": 4.76, ...}, ...}
            text_timeseries: 按月组织的文本数据 {"2020-08": {"hottest_issue": {...}, ...}, ...}
        
        返回:
            趋势列表 [{"period": "...", "type": "...", "description": "...", "key_events": [...]}]
        """
        time_axis = sorted(timeseries_data.keys())
        if len(time_axis) < 3:
            return []
        
        # 提取主要指标的趋势（按优先级尝试多个指标）
        main_metric_values = []
        metric_name = None
        
        # 按优先级尝试指标
        metric_candidates = [
            ('OpenRank', ['OpenRank', 'opendigger_OpenRank', '影响力']),
            ('活跃度', ['活跃度', 'opendigger_活跃度', 'Activity', 'activity_score']),
            ('Star数', ['Star数', 'opendigger_Star数', 'stars']),
            ('参与者数', ['参与者数', 'opendigger_参与者数', 'participants', 'contributors_count']),
            ('代码提交数', ['代码提交数', 'opendigger_代码提交数', 'commits', 'commits_count'])
        ]
        
        for candidate_name, candidate_keys in metric_candidates:
            for month in time_axis:
                metrics = timeseries_data[month]
                for key in candidate_keys:
                    value = metrics.get(key)
                    if value is not None:
                        metric_name = candidate_name
                        break
                if metric_name:
                    break
            if metric_name:
                break
        
        # 提取该指标的值
        for month in time_axis:
            metrics = timeseries_data[month]
            value = None
            
            # 根据选定的指标提取值
            if metric_name == 'OpenRank':
                value = metrics.get('OpenRank') or metrics.get('opendigger_OpenRank') or metrics.get('影响力')
            elif metric_name == '活跃度':
                value = metrics.get('活跃度') or metrics.get('opendigger_活跃度') or metrics.get('Activity') or metrics.get('activity_score')
            elif metric_name == 'Star数':
                value = metrics.get('Star数') or metrics.get('opendigger_Star数') or metrics.get('stars')
            elif metric_name == '参与者数':
                value = metrics.get('参与者数') or metrics.get('opendigger_参与者数') or metrics.get('participants') or metrics.get('contributors_count')
            elif metric_name == '代码提交数':
                value = metrics.get('代码提交数') or metrics.get('opendigger_代码提交数') or metrics.get('commits') or metrics.get('commits_count')
            
            main_metric_values.append((month, value))
        
        # 简单趋势检测：分段分析
        trends = []
        
        # 整体趋势
        valid_values = [(m, v) for m, v in main_metric_values if v is not None]
        if len(valid_values) >= 2:
            first_value = valid_values[0][1]
            last_value = valid_values[-1][1]
            
            if first_value > 0:
                change_rate = (last_value - first_value) / first_value * 100
                
                if change_rate > 20:
                    trend_type = "上升"
                elif change_rate < -20:
                    trend_type = "下降"
                else:
                    trend_type = "稳定"
                
                # 收集关键事件
                key_events = self._collect_key_events(text_timeseries, time_axis)
                
                metric_display_name = metric_name if metric_name else "主要指标"
                trends.append({
                    "period": f"{time_axis[0]} to {time_axis[-1]}",
                    "type": trend_type,
                    "change_rate": round(change_rate, 1),
                    "metric": metric_display_name,
                    "description": f"项目整体呈{trend_type}趋势（{metric_display_name}变化幅度{abs(change_rate):.1f}%）",
                    "key_events": key_events[:5]
                })
        
        # 使用LLM生成更详细的趋势分析
        if len(time_axis) >= 6:
            llm_trends = self._llm_detect_trends(timeseries_data, text_timeseries, time_axis[-6:])
            if llm_trends:
                trends.extend(llm_trends)
        
        return trends
    
    def _collect_key_events(self, text_timeseries: Dict, time_axis: List[str]) -> List[str]:
        """收集关键事件"""
        events = []
        for month in time_axis:
            text_data = text_timeseries.get(month, {})
            
            issue = text_data.get('hottest_issue')
            if issue and issue.get('title') and issue.get('hot_score', 0) > 5:
                events.append(f"[{month}] Issue: {issue['title'][:40]}")
            
            pr = text_data.get('hottest_pr')
            if pr and pr.get('title') and pr.get('hot_score', 0) > 5:
                events.append(f"[{month}] PR: {pr['title'][:40]}")
        
        return events
    
    def _llm_detect_trends(self, timeseries_data: Dict, text_timeseries: Dict, 
                           recent_months: List[str]) -> List[Dict]:
        """使用LLM检测趋势"""
        # 准备数据摘要
        data_summary = []
        for month in recent_months:
            metrics = timeseries_data.get(month, {})
            text_data = text_timeseries.get(month, {})
            
            # 提取所有可用的关键指标
            openrank = metrics.get('OpenRank') or metrics.get('opendigger_OpenRank')
            activity = metrics.get('活跃度') or metrics.get('opendigger_活跃度') or metrics.get('activity_score')
            star = metrics.get('Star数') or metrics.get('opendigger_Star数') or metrics.get('stars')
            fork = metrics.get('Fork数') or metrics.get('opendigger_Fork数') or metrics.get('forks')
            issues = metrics.get('新增Issue') or metrics.get('issues_count')
            prs = metrics.get('PR接受数') or metrics.get('prs_count')
            commits = metrics.get('代码提交数') or metrics.get('commits_count')
            contributors = metrics.get('参与者数') or metrics.get('contributors_count')
            
            issue_title = text_data.get('hottest_issue', {}).get('title', '') if text_data.get('hottest_issue') else ''
            
            # 构建数据摘要行
            line_parts = [f"{month}:"]
            if openrank:
                line_parts.append(f"OpenRank={openrank}")
            if activity:
                line_parts.append(f"活跃度={activity}")
            if star:
                line_parts.append(f"Star={star}")
            if fork:
                line_parts.append(f"Fork={fork}")
            if issues:
                line_parts.append(f"Issue={issues}")
            if prs:
                line_parts.append(f"PR={prs}")
            if commits:
                line_parts.append(f"提交={commits}")
            if contributors:
                line_parts.append(f"贡献者={contributors}")
            if issue_title:
                line_parts.append(f"热门Issue={issue_title[:30]}")
            
            data_summary.append(" ".join(line_parts))
        
        prompt = f"""基于以下开源项目最近6个月的数据，识别趋势模式：

{chr(10).join(data_summary)}

请识别：
1. 趋势类型（上升/下降/波动/周期性）
2. 趋势描述（50字以内）
3. 是否有关键转折点

直接输出描述，不要JSON格式。"""
        
        result = self.llm.generate(prompt, max_tokens=300)
        
        if result not in ["[LLM不可用]", "[生成失败]"]:
            return [{
                "period": f"{recent_months[0]} to {recent_months[-1]}",
                "type": "分析",
                "description": result,
                "key_events": []
            }]
        
        return []
    
    # ========== 3. 关键点增强 ==========
    
    def enhance_key_points(self, timeseries_data: Dict[str, Dict], 
                           text_timeseries: Dict[str, Dict]) -> List[Dict]:
        """
        为关键点（峰值/谷值）生成解释
        
        返回:
            关键点列表 [{"date": "...", "value": ..., "type": "...", "explanation": "..."}]
        """
        time_axis = sorted(timeseries_data.keys())
        
        # 提取主要指标值（优先OpenRank，其次活跃度）
        values = []
        metric_name = None
        
        # 确定使用哪个指标
        for month in time_axis:
            metrics = timeseries_data[month]
            value = metrics.get('OpenRank') or metrics.get('opendigger_OpenRank') or metrics.get('影响力')
            if value is not None:
                metric_name = 'OpenRank'
                break
        
        if not metric_name:
            for month in time_axis:
                metrics = timeseries_data[month]
                value = metrics.get('活跃度') or metrics.get('opendigger_活跃度')
                if value is not None:
                    metric_name = '活跃度'
                    break
        
        # 提取该指标的值
        for month in time_axis:
            metrics = timeseries_data[month]
            value = None
            
            if metric_name == 'OpenRank':
                value = metrics.get('OpenRank') or metrics.get('opendigger_OpenRank') or metrics.get('影响力')
            elif metric_name == '活跃度':
                value = metrics.get('活跃度') or metrics.get('opendigger_活跃度') or metrics.get('Activity') or metrics.get('activity_score')
            elif metric_name == 'Star数':
                value = metrics.get('Star数') or metrics.get('opendigger_Star数') or metrics.get('stars')
            elif metric_name == '参与者数':
                value = metrics.get('参与者数') or metrics.get('opendigger_参与者数') or metrics.get('participants') or metrics.get('contributors_count')
            elif metric_name == '代码提交数':
                value = metrics.get('代码提交数') or metrics.get('opendigger_代码提交数') or metrics.get('commits') or metrics.get('commits_count')
            
            if value is not None:
                values.append((month, value))
        
        if len(values) < 3:
            return []
        
        key_points = []
        
        # 找峰值
        max_item = max(values, key=lambda x: x[1])
        max_month, max_value = max_item
        
        # 找谷值
        min_item = min(values, key=lambda x: x[1])
        min_month, min_value = min_item
        
        # 为峰值生成解释
        if max_month != min_month:
            peak_text = text_timeseries.get(max_month, {})
            peak_explanation = self._explain_key_point(
                max_month, max_value, "峰值", 
                timeseries_data.get(max_month, {}), peak_text
            )
            metric_display = metric_name if metric_name else "主要指标"
            key_points.append({
                "date": max_month,
                "value": max_value,
                "type": "峰值",
                "metric": metric_display,
                "explanation": peak_explanation
            })
            
            # 为谷值生成解释
            valley_text = text_timeseries.get(min_month, {})
            valley_explanation = self._explain_key_point(
                min_month, min_value, "谷值",
                timeseries_data.get(min_month, {}), valley_text, metric_name
            )
            key_points.append({
                "date": min_month,
                "value": min_value,
                "type": "谷值",
                "metric": metric_display,
                "explanation": valley_explanation
            })
        
        # 最新值
        latest_month, latest_value = values[-1]
        metric_display = metric_name if metric_name else "主要指标"
        key_points.append({
            "date": latest_month,
            "value": latest_value,
            "type": "最新",
            "metric": metric_display,
            "explanation": f"最新数据（{latest_month}）：{metric_display}为{latest_value:.2f}"
        })
        
        return key_points
    
    def _explain_key_point(self, month: str, value: float, point_type: str,
                           metrics: Dict, text_data: Dict, metric_name: str = 'OpenRank') -> str:
        """使用LLM解释关键点"""
        issue_title = text_data.get('hottest_issue', {}).get('title', '') if text_data.get('hottest_issue') else ''
        pr_title = text_data.get('hottest_pr', {}).get('title', '') if text_data.get('hottest_pr') else ''
        
        metric_display = metric_name if metric_name else "主要指标"
        prompt = f"""{month}月{metric_display}达到{point_type}（{value:.2f}），请简要解释可能原因（50字以内）：

当月事件：
- Issue: {issue_title or '无'}
- PR: {pr_title or '无'}

直接输出解释，不要格式符号。"""
        
        result = self.llm.generate(prompt, max_tokens=150)
        
        if result in ["[LLM不可用]", "[生成失败]"]:
            metric_display = metric_name if metric_name else "主要指标"
            return f"{month}月{metric_display}达到{point_type}（{value:.2f}）"
        
        return result
    
    # ========== 4. 语义特征提取 ==========
    
    def extract_semantic_features(self, timeseries_data: Dict[str, Dict],
                                   text_timeseries: Dict[str, Dict]) -> Dict:
        """
        提取语义特征
        
        返回:
            {
                "growth_rate": "高/中/低",
                "stability": "高/中/低",
                "text_activity": "高/中/低",
                "overall_status": "..."
            }
        """
        time_axis = sorted(timeseries_data.keys())
        
        # 提取主要指标值（按优先级尝试多个指标）
        values = []
        metric_name = None
        
        # 按优先级尝试指标
        metric_candidates = [
            ('OpenRank', ['OpenRank', 'opendigger_OpenRank', '影响力']),
            ('活跃度', ['活跃度', 'opendigger_活跃度', 'Activity', 'activity_score']),
            ('Star数', ['Star数', 'opendigger_Star数', 'stars']),
            ('参与者数', ['参与者数', 'opendigger_参与者数', 'participants', 'contributors_count']),
            ('代码提交数', ['代码提交数', 'opendigger_代码提交数', 'commits', 'commits_count'])
        ]
        
        for candidate_name, candidate_keys in metric_candidates:
            for month in time_axis:
                metrics = timeseries_data[month]
                for key in candidate_keys:
                    value = metrics.get(key)
                    if value is not None:
                        metric_name = candidate_name
                        break
                if metric_name:
                    break
            if metric_name:
                break
        
        # 提取该指标的值
        for month in time_axis:
            metrics = timeseries_data[month]
            value = None
            
            if metric_name == 'OpenRank':
                value = metrics.get('OpenRank') or metrics.get('opendigger_OpenRank') or metrics.get('影响力')
            elif metric_name == '活跃度':
                value = metrics.get('活跃度') or metrics.get('opendigger_活跃度') or metrics.get('Activity') or metrics.get('activity_score')
            elif metric_name == 'Star数':
                value = metrics.get('Star数') or metrics.get('opendigger_Star数') or metrics.get('stars')
            elif metric_name == '参与者数':
                value = metrics.get('参与者数') or metrics.get('opendigger_参与者数') or metrics.get('participants') or metrics.get('contributors_count')
            elif metric_name == '代码提交数':
                value = metrics.get('代码提交数') or metrics.get('opendigger_代码提交数') or metrics.get('commits') or metrics.get('commits_count')
            
            if value is not None:
                values.append(value)
        
        features = {}
        
        # 1. 计算增长率
        if len(values) >= 2 and values[0] > 0:
            growth = (values[-1] - values[0]) / values[0] * 100
            if growth > 50:
                features['growth_rate'] = "高"
            elif growth > 10:
                features['growth_rate'] = "中"
            elif growth > -10:
                features['growth_rate'] = "稳定"
            else:
                features['growth_rate'] = "低"
            features['growth_percent'] = round(growth, 1)
        else:
            features['growth_rate'] = "未知"
        
        # 2. 计算稳定性（变异系数）
        if len(values) >= 3:
            mean_val = sum(values) / len(values)
            if mean_val > 0:
                std_val = (sum((x - mean_val) ** 2 for x in values) / len(values)) ** 0.5
                cv = std_val / mean_val
                
                if cv < 0.2:
                    features['stability'] = "高"
                elif cv < 0.5:
                    features['stability'] = "中"
                else:
                    features['stability'] = "低"
                features['cv'] = round(cv, 3)
            else:
                features['stability'] = "未知"
        else:
            features['stability'] = "未知"
        
        # 3. 计算文本活跃度
        total_months = len(time_axis)
        months_with_issue = sum(1 for m in text_timeseries.values() if m.get('hottest_issue'))
        months_with_pr = sum(1 for m in text_timeseries.values() if m.get('hottest_pr'))
        
        text_coverage = (months_with_issue + months_with_pr) / (total_months * 2) if total_months > 0 else 0
        
        if text_coverage > 0.7:
            features['text_activity'] = "高"
        elif text_coverage > 0.4:
            features['text_activity'] = "中"
        else:
            features['text_activity'] = "低"
        features['text_coverage'] = round(text_coverage * 100, 1)
        
        # 4. 生成整体状态描述
        features['overall_status'] = self._generate_overall_status(features)
        
        return features
    
    def _generate_overall_status(self, features: Dict) -> str:
        """生成整体状态描述"""
        growth = features.get('growth_rate', '未知')
        stability = features.get('stability', '未知')
        text_activity = features.get('text_activity', '未知')
        
        if growth in ["高", "中"] and stability in ["高", "中"]:
            return "健康发展"
        elif growth == "高" and stability == "低":
            return "快速变化"
        elif growth in ["低", "稳定"] and stability == "高":
            return "平稳运行"
        elif growth == "低" and text_activity == "低":
            return "活跃度下降"
        else:
            return "正常运行"
    
    # ========== 5. 整体总结 ==========
    
    def generate_summary(self, timeseries_data: Dict[str, Dict],
                         text_timeseries: Dict[str, Dict],
                         trends: List[Dict],
                         key_points: List[Dict],
                         features: Dict) -> str:
        """
        生成整体趋势总结
        """
        time_axis = sorted(timeseries_data.keys())
        
        # 准备摘要信息
        growth_rate = features.get('growth_rate', '未知')
        stability = features.get('stability', '未知')
        overall_status = features.get('overall_status', '未知')
        
        # 关键点信息
        peak_info = ""
        valley_info = ""
        for kp in key_points:
            if kp['type'] == '峰值':
                peak_info = f"峰值出现在{kp['date']}（{kp['value']:.2f}）"
            elif kp['type'] == '谷值':
                valley_info = f"谷值出现在{kp['date']}（{kp['value']:.2f}）"
        
        prompt = f"""请为这个开源项目生成整体趋势总结（150字以内）：

时间范围：{time_axis[0]} 至 {time_axis[-1]}（共{len(time_axis)}个月）
增长率：{growth_rate}（{features.get('growth_percent', 0):.1f}%）
稳定性：{stability}
文本活跃度：{features.get('text_activity', '未知')}
整体状态：{overall_status}
{peak_info}
{valley_info}

要求：
1. 总结项目的发展趋势
2. 指出关键变化点
3. 给出简要展望
4. 语言自然流畅"""
        
        result = self.llm.generate(prompt, max_tokens=400)
        
        if result in ["[LLM不可用]", "[生成失败]"]:
            return f"项目从{time_axis[0]}至{time_axis[-1]}期间整体呈{overall_status}状态，增长率{growth_rate}，稳定性{stability}。"
        
        return result
    
    # ========== 完整增强流程 ==========
    
    def enhance_all(self, timeseries_data: Dict[str, Dict],
                    text_timeseries: Dict[str, Dict]) -> Dict:
        """
        完整增强流程
        
        参数:
            timeseries_data: 按月组织的指标数据
            text_timeseries: 按月组织的文本数据
        
        返回:
            {
                "time_axis": [...],
                "monthly_data": {...},
                "trends": [...],
                "key_points": [...],
                "semantic_features": {...},
                "summary": "..."
            }
        """
        print("\n开始数据增强...")
        
        time_axis = sorted(timeseries_data.keys())
        
        # 1. 单月增强
        print("  [1/5] 单月数据增强...")
        monthly_data = {}
        for i, month in enumerate(time_axis):
            metrics = timeseries_data[month]
            text_data = text_timeseries.get(month, {})
            
            enhanced_desc = self.enhance_month(month, metrics, text_data)
            
            monthly_data[month] = {
                "metrics": metrics,
                "text_data": text_data,
                "enhanced_description": enhanced_desc
            }
            
            if (i + 1) % 10 == 0:
                print(f"      已处理 {i+1}/{len(time_axis)} 个月")
        
        # 2. 趋势识别
        print("  [2/5] 趋势识别增强...")
        trends = self.detect_trends(timeseries_data, text_timeseries)
        print(f"      识别到 {len(trends)} 个趋势")
        
        # 3. 关键点增强
        print("  [3/5] 关键点增强...")
        key_points = self.enhance_key_points(timeseries_data, text_timeseries)
        print(f"      识别到 {len(key_points)} 个关键点")
        
        # 4. 语义特征提取
        print("  [4/5] 语义特征提取...")
        features = self.extract_semantic_features(timeseries_data, text_timeseries)
        print(f"      整体状态: {features.get('overall_status', '未知')}")
        
        # 5. 整体总结
        print("  [5/5] 生成整体总结...")
        summary = self.generate_summary(timeseries_data, text_timeseries, trends, key_points, features)
        
        result = {
            "time_axis": time_axis,
            "monthly_data": monthly_data,
            "trends": trends,
            "key_points": key_points,
            "semantic_features": features,
            "summary": summary
        }
        
        print("\n增强完成!")
        print(f"  - 月份数: {len(time_axis)}")
        print(f"  - 趋势数: {len(trends)}")
        print(f"  - 关键点数: {len(key_points)}")
        print(f"  - 整体状态: {features.get('overall_status', '未知')}")
        
        return result

