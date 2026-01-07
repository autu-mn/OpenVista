"""
百分位分布对齐器（Percentile Distribution Aligner）

思想：评分不是看"你有多好"，而是看"你打败了多少项目"
- 保序（不改变项目排序）
- 把分数映射到 [min_score, max_score]
- 解决系统性压分问题，使分数分布符合真实开源生态
"""
from bisect import bisect_left
from typing import List


class PercentileDistributionAligner:
    """
    百分位分布对齐器
    
    将原始分数映射到目标分布范围，保持项目之间的相对排序不变。
    例如：如果某个项目的原始分数在所有项目中排名前20%，则映射到80分以上。
    """
    
    def __init__(self, reference_scores: List[float], 
                 min_score: float = 30.0, 
                 max_score: float = 100.0):
        """
        初始化分布对齐器
        
        Args:
            reference_scores: 参考分数列表（最近一批项目的原始overall_score）
            min_score: 映射后的最低分（默认30分）
            max_score: 映射后的最高分（默认100分）
        """
        self.min_score = min_score
        self.max_score = max_score
        
        # 只保留合法分数（0-100范围内）
        self.scores = sorted([
            s for s in reference_scores
            if isinstance(s, (int, float)) and 0 <= s <= 100
        ])
        
        self.n = len(self.scores)
    
    def align(self, score: float) -> float:
        """
        将原始分数映射到目标分布范围
        
        Args:
            score: 原始分数（0-100）
            
        Returns:
            映射后的分数（min_score - max_score）
        """
        if not self.scores:
            # 如果没有参考数据，直接返回原始分数
            return round(score, 1)
        
        # 使用 bisect 而不是 index（避免重复值bug）
        # bisect_left 返回插入位置，即该分数在所有分数中的排名
        rank = bisect_left(self.scores, score)
        
        # 计算百分位（0.0 - 1.0）
        # 使用 n-1 作为分母，确保最高分映射到100%
        percentile = rank / max(1, self.n - 1)
        
        # 映射到目标范围
        aligned = self.min_score + percentile * (self.max_score - self.min_score)
        
        return round(aligned, 1)
    
    def get_percentile(self, score: float) -> float:
        """
        获取分数对应的百分位排名（0-100）
        
        返回的是"排名前X%"，例如：
        - 如果返回68.5，表示这个项目排名前68.5%（比68.5%的项目好）
        - 如果返回100，表示这个项目排名前100%（最好的项目）
        
        Args:
            score: 原始分数
            
        Returns:
            百分位排名（0-100），表示排名前X%
        """
        if not self.scores:
            return 0.0
        
        rank = bisect_left(self.scores, score)
        
        # 计算百分位：rank / (n-1) * 100
        # rank=0 时，百分位=0%（排名前0%，即最差）
        # rank=n-1 时，百分位=100%（排名前100%，即最好）
        percentile = (rank / max(1, self.n - 1)) * 100
        
        # 转换为"排名前X%"：100 - percentile
        # 例如：如果 percentile=31.5，表示排名前68.5%
        top_percentile = 100 - percentile
        
        return round(top_percentile, 1)
    
    def is_ready(self) -> bool:
        """
        检查对齐器是否已准备好（是否有足够的参考数据）
        
        Returns:
            True if ready, False otherwise
        """
        return self.n >= 10  # 至少需要10个参考项目

