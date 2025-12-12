"""
OpenDigger MCP Server 客户端包装器
直接调用 OpenDigger API，提供与 MCP Server 相同的接口
"""
import requests
import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict


class OpenDiggerMCPClient:
    """OpenDigger API 客户端（兼容 MCP Server 接口）"""
    
    def __init__(self):
        """初始化客户端"""
        self.base_url = "https://oss.open-digger.cn"
        self.cache = {}
        self.cache_ttl = int(os.getenv('CACHE_TTL_SECONDS', '300'))
    
    def _fetch_metric(self, owner: str, repo: str, metric_name: str, platform: str = 'GitHub') -> Dict[str, Any]:
        """获取单个指标数据"""
        cache_key = f"{platform}:{owner}:{repo}:{metric_name}"
        
        # 检查缓存
        if cache_key in self.cache:
            cached_data, cached_time = self.cache[cache_key]
            if (datetime.now() - cached_time).seconds < self.cache_ttl:
                return cached_data
        
        # 调用 API
        platform_lower = platform.lower()
        url = f"{self.base_url}/{platform_lower}/{owner}/{repo}/{metric_name}.json"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # 缓存数据
            self.cache[cache_key] = (data, datetime.now())
            
            return {
                'success': True,
                'data': data,
                'metric': metric_name,
                'repository': f"{owner}/{repo}"
            }
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': str(e),
                'metric': metric_name,
                'repository': f"{owner}/{repo}"
            }
    
    def get_metric(self, owner: str, repo: str, metric_name: str, platform: str = 'GitHub') -> Dict[str, Any]:
        """
        获取单个仓库指标
        
        Args:
            owner: 仓库所有者
            repo: 仓库名称
            metric_name: 指标名称
            platform: 平台 (GitHub/Gitee)
            
        Returns:
            指标数据
        """
        return self._fetch_metric(owner, repo, metric_name, platform)
    
    def get_metrics_batch(self, owner: str, repo: str, metric_names: List[str], platform: str = 'GitHub') -> Dict[str, Any]:
        """
        批量获取多个指标
        
        Args:
            owner: 仓库所有者
            repo: 仓库名称
            metric_names: 指标名称列表
            platform: 平台 (GitHub/Gitee)
            
        Returns:
            批量指标数据
        """
        results = {}
        for metric_name in metric_names:
            result = self._fetch_metric(owner, repo, metric_name, platform)
            results[metric_name] = result
        
        return {
            'success': True,
            'results': results,
            'repository': f"{owner}/{repo}",
            'metrics_count': len(metric_names)
        }
    
    def compare_repositories(self, repos: List[Dict[str, str]], metrics: List[str], platform: str = 'GitHub') -> Dict[str, Any]:
        """
        对比多个仓库
        
        Args:
            repos: 仓库列表，格式: [{'owner': 'owner1', 'repo': 'repo1'}, ...]
            metrics: 要对比的指标列表
            platform: 平台 (GitHub/Gitee)
            
        Returns:
            对比分析结果
        """
        comparison_data = {}
        
        for repo_info in repos:
            owner = repo_info.get('owner')
            repo = repo_info.get('repo')
            if not owner or not repo:
                continue
            
            repo_key = f"{owner}/{repo}"
            comparison_data[repo_key] = {}
            
            for metric_name in metrics:
                result = self._fetch_metric(owner, repo, metric_name, platform)
                if result.get('success'):
                    comparison_data[repo_key][metric_name] = result.get('data')
        
        return {
            'success': True,
            'comparison': comparison_data,
            'repositories': [f"{r.get('owner')}/{r.get('repo')}" for r in repos],
            'metrics': metrics
        }
    
    def analyze_trends(self, owner: str, repo: str, metric_name: str, 
                       start_date: Optional[str] = None, end_date: Optional[str] = None,
                       platform: str = 'GitHub') -> Dict[str, Any]:
        """
        分析趋势
        
        Args:
            owner: 仓库所有者
            repo: 仓库名称
            metric_name: 指标名称
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            platform: 平台 (GitHub/Gitee)
            
        Returns:
            趋势分析结果
        """
        result = self._fetch_metric(owner, repo, metric_name, platform)
        
        if not result.get('success'):
            return result
        
        data = result.get('data', {})
        
        # 简单的趋势分析
        if isinstance(data, dict) and 'data' in data:
            values = data['data']
            if values:
                # 计算增长率
                if len(values) >= 2:
                    first_half = values[:len(values)//2]
                    second_half = values[len(values)//2:]
                    first_avg = sum(first_half) / len(first_half) if first_half else 0
                    second_avg = sum(second_half) / len(second_half) if second_half else 0
                    growth_rate = ((second_avg - first_avg) / first_avg * 100) if first_avg > 0 else 0
                else:
                    growth_rate = 0
                
                return {
                    'success': True,
                    'trend': 'increasing' if growth_rate > 0 else 'decreasing' if growth_rate < 0 else 'stable',
                    'growth_rate': round(growth_rate, 2),
                    'data': data,
                    'metric': metric_name,
                    'repository': f"{owner}/{repo}"
                }
        
        return result
    
    def get_ecosystem_insights(self, owner: str, repo: str, platform: str = 'GitHub') -> Dict[str, Any]:
        """
        获取生态系统洞察
        
        Args:
            owner: 仓库所有者
            repo: 仓库名称
            platform: 平台 (GitHub/Gitee)
            
        Returns:
            生态系统洞察
        """
        # 获取多个关键指标
        key_metrics = ['openrank', 'stars', 'forks', 'contributors', 'activity']
        results = {}
        
        for metric_name in key_metrics:
            result = self._fetch_metric(owner, repo, metric_name, platform)
            if result.get('success'):
                results[metric_name] = result.get('data')
        
        return {
            'success': True,
            'insights': results,
            'repository': f"{owner}/{repo}",
            'metrics_analyzed': len(results)
        }
    
    def server_health(self) -> Dict[str, Any]:
        """
        获取服务器健康状态
        
        Returns:
            服务器健康信息
        """
        return {
            'status': 'healthy',
            'cache_size': len(self.cache),
            'cache_ttl': self.cache_ttl,
            'timestamp': datetime.now().isoformat()
        }


# 全局客户端实例
_mcp_client: Optional[OpenDiggerMCPClient] = None


def get_mcp_client() -> OpenDiggerMCPClient:
    """获取 MCP 客户端单例"""
    global _mcp_client
    if _mcp_client is None:
        try:
            _mcp_client = OpenDiggerMCPClient()
        except Exception as e:
            print(f"警告: 无法初始化 MCP 客户端: {e}")
            raise
    return _mcp_client

