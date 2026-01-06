"""
CHAOSS 指标映射器
将 OpenDigger 的 16 个指标映射到 CHAOSS 评价维度
"""
from typing import Dict, List


class CHAOSSMapper:
    """CHAOSS 指标映射器"""
    
    # CHAOSS 维度定义
    CHAOSS_DIMENSIONS = {
        'Activity': {
            'name': '活动度',
            'description': '项目整体活跃程度，包括提交、PR、Issue等活动',
            'metrics': {
                'opendigger_OpenRank': {'weight': 1.5},
                'opendigger_活跃度': {'weight': 1.5},
                'opendigger_变更请求': {'weight': 1.0},
                'opendigger_PR接受数': {'weight': 1.0},
                'opendigger_新增Issue': {'weight': 1.0},
            }
        },
        'Contributors': {
            'name': '贡献者',
            'description': '贡献者数量、增长和留存情况',
            'metrics': {
                'opendigger_参与者数': {'weight': 1.3},
                'opendigger_贡献者': {'weight': 1.3},
                'opendigger_新增贡献者': {'weight': 1.0},
            }
        },
        'Responsiveness': {
            'name': '响应性',
            'description': 'Issue和PR的响应速度和处理效率',
            'metrics': {
                'opendigger_关闭Issue': {'weight': 1.0},
                'opendigger_Issue评论': {'weight': 1.0},
            }
        },
        'Quality': {
            'name': '代码质量',
            'description': '代码审查、代码变更规模等质量指标',
            'metrics': {
                'opendigger_PR审查': {'weight': 1.0},
                'opendigger_代码新增行数': {'weight': 0.8},
                'opendigger_代码删除行数': {'weight': 0.8},
                'opendigger_代码变更总行数': {'weight': 1.0},
            }
        },
        'Risk': {
            'name': '风险',
            'description': '项目风险集中度，如Bus Factor',
            'metrics': {
                'opendigger_总线因子': {'weight': 1.0},
            }
        },
        'Community Interest': {
            'name': '社区兴趣',
            'description': 'Star、Fork等反映社区关注度的指标',
            'metrics': {
                'opendigger_Star数': {'weight': 1.0},
                'opendigger_Fork数': {'weight': 1.0},
            }
        },
    }
    
    def get_chaoss_dimensions(self) -> Dict:
        """获取所有 CHAOSS 维度定义"""
        return self.CHAOSS_DIMENSIONS
    
    def map_metrics_to_dimensions(self, timeseries_data: Dict) -> Dict:
        """
        将时序数据映射到 CHAOSS 维度
        
        Args:
            timeseries_data: 时序数据字典
            
        Returns:
            按维度组织的指标映射
        """
        mapped = {}
        for dimension, dimension_info in self.CHAOSS_DIMENSIONS.items():
            mapped[dimension] = {
                'name': dimension_info['name'],
                'description': dimension_info['description'],
                'metrics': {}
            }
            
            for metric_key, metric_info in dimension_info['metrics'].items():
                if metric_key in timeseries_data:
                    mapped[dimension]['metrics'][metric_key] = {
                        **metric_info,
                        'data': timeseries_data[metric_key]
                    }
        
        return mapped

