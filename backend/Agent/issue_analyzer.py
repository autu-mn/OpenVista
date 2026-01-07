"""
Issue 分析器 - 使用 DeepSeek 分析项目 Issue 文本
总结项目遇到的问题和解决办法
"""

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


class IssueAnalyzer:
    """Issue 分析器"""
    
    def __init__(self):
        self.use_ai = DEEPSEEK_AVAILABLE
        if self.use_ai:
            try:
                self.deepseek = DeepSeekClient()
                print("[OK] Issue 分析器已启用 DeepSeek AI")
            except Exception as e:
                print(f"[WARN] DeepSeek 初始化失败: {e}")
                self.use_ai = False
                self.deepseek = None
        else:
            self.deepseek = None
    
    def load_issues_from_raw_data(self, raw_data_path: str) -> List[Dict]:
        """
        从 raw_monthly_data.json 加载 Issue 数据
        
        Args:
            raw_data_path: raw_monthly_data.json 文件路径
        
        Returns:
            Issue 列表
        """
        all_issues = []
        
        try:
            with open(raw_data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            monthly_data = data.get('monthly_data', {})
            
            for month, month_data in monthly_data.items():
                issues = month_data.get('issues', [])
                for issue in issues:
                    issue['month'] = month
                    all_issues.append(issue)
            
            # 按时间倒序排序（最新的在前）
            all_issues.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            
            print(f"[OK] 加载了 {len(all_issues)} 个 Issue")
            return all_issues
            
        except Exception as e:
            print(f"[ERROR] 加载 Issue 数据失败: {e}")
            return []
    
    def preprocess_issues(self, issues: List[Dict], max_issues: int = 100) -> Dict:
        """
        预处理 Issue 数据，提取关键信息
        
        Args:
            issues: Issue 列表
            max_issues: 最多处理的 Issue 数量
        
        Returns:
            预处理后的数据
        """
        # 限制数量
        recent_issues = issues[:max_issues]
        
        # 分类统计
        categories = {
            'bug': [],
            'feature': [],
            'question': [],
            'enhancement': [],
            'other': []
        }
        
        # 状态统计
        open_count = 0
        closed_count = 0
        
        # 高热度 Issue
        hot_issues = []
        
        for issue in recent_issues:
            # 统计状态
            if issue.get('state') == 'open':
                open_count += 1
            else:
                closed_count += 1
            
            # 分类
            labels = [l.lower() if isinstance(l, str) else l.get('name', '').lower() for l in issue.get('labels', [])]
            title_lower = issue.get('title', '').lower()
            
            if any('bug' in l for l in labels) or 'bug' in title_lower or 'error' in title_lower or 'fix' in title_lower:
                categories['bug'].append(issue)
            elif any('feature' in l or 'enhancement' in l for l in labels) or 'feature' in title_lower:
                categories['feature'].append(issue)
            elif any('question' in l or 'help' in l for l in labels) or '?' in issue.get('title', ''):
                categories['question'].append(issue)
            else:
                categories['other'].append(issue)
            
            # 热度计算
            heat = issue.get('heat_score', 0) or (
                issue.get('comments_count', 0) * 2 + 
                issue.get('reactions', {}).get('total_count', 0)
            )
            if heat > 10:
                hot_issues.append({
                    'number': issue.get('number'),
                    'title': issue.get('title'),
                    'state': issue.get('state'),
                    'heat': heat,
                    'month': issue.get('month'),
                    'labels': labels
                })
        
        # 排序热门 Issue
        hot_issues.sort(key=lambda x: x['heat'], reverse=True)
        
        return {
            'total': len(recent_issues),
            'open': open_count,
            'closed': closed_count,
            'categories': {
                'bug': len(categories['bug']),
                'feature': len(categories['feature']),
                'question': len(categories['question']),
                'other': len(categories['other'])
            },
            'hot_issues': hot_issues[:10],
            'recent_issues': [
                {
                    'number': i.get('number'),
                    'title': i.get('title'),
                    'state': i.get('state'),
                    'month': i.get('month'),
                    'body': (i.get('body', '') or '')[:500]  # 截断正文
                }
                for i in recent_issues[:20]
            ]
        }
    
    def analyze_issues(self, issues: List[Dict], repo_name: str = '') -> Dict:
        """
        使用 AI 分析 Issue，生成摘要
        
        Args:
            issues: Issue 列表
            repo_name: 仓库名称
        
        Returns:
            分析结果
        """
        # 预处理数据
        processed = self.preprocess_issues(issues)
        
        # 如果没有 AI，返回基础统计
        if not self.use_ai or not self.deepseek:
            return {
                'summary': self._generate_rule_based_summary(processed, repo_name),
                'stats': processed,
                'ai_enabled': False
            }
        
        # 使用 AI 生成分析
        return self._generate_ai_analysis(processed, repo_name)
    
    def _generate_rule_based_summary(self, processed: Dict, repo_name: str) -> str:
        """基于规则生成摘要"""
        cats = processed['categories']
        
        summary = f"## {repo_name or '项目'} Issue 分析\n\n"
        summary += f"**统计数据**：共分析 {processed['total']} 个 Issue，"
        summary += f"其中 {processed['open']} 个未解决，{processed['closed']} 个已关闭。\n\n"
        
        summary += f"**分类分布**：\n"
        summary += f"- 🐛 Bug 报告: {cats['bug']} 个\n"
        summary += f"- ✨ 功能需求: {cats['feature']} 个\n"
        summary += f"- ❓ 问题咨询: {cats['question']} 个\n"
        summary += f"- 📝 其他: {cats['other']} 个\n\n"
        
        if processed['hot_issues']:
            summary += f"**热门讨论**：\n"
            for issue in processed['hot_issues'][:5]:
                state_emoji = '🟢' if issue['state'] == 'open' else '⚫'
                summary += f"- {state_emoji} #{issue['number']}: {issue['title']} (热度: {issue['heat']})\n"
        
        return summary
    
    def _generate_ai_analysis(self, processed: Dict, repo_name: str) -> Dict:
        """使用 AI 生成分析"""
        
        # 构建上下文
        context = f"""项目: {repo_name}
Issue 统计:
- 总数: {processed['total']}
- 未解决: {processed['open']}
- 已关闭: {processed['closed']}
- Bug: {processed['categories']['bug']}
- 功能需求: {processed['categories']['feature']}
- 问题咨询: {processed['categories']['question']}

热门 Issue:
"""
        for issue in processed['hot_issues'][:5]:
            context += f"- #{issue['number']}: {issue['title']} ({issue['state']}, 热度: {issue['heat']})\n"
        
        context += "\n最近的 Issue:\n"
        for issue in processed['recent_issues'][:10]:
            context += f"- #{issue['number']}: {issue['title']}\n"
            if issue['body']:
                context += f"  内容摘要: {issue['body'][:200]}...\n"
        
        prompt = f"""基于以下 GitHub 项目的 Issue 数据，请生成一份简洁的分析报告。

{context}

请包含以下内容（使用 Markdown 格式）：
1. **问题概览**：项目当前面临的主要问题类型
2. **热点话题**：社区讨论最活跃的几个话题
3. **改进建议**：基于 Issue 数据给项目维护者的建议

要求：
- 语言简洁，重点突出
- 使用数据支撑观点
- 不超过 300 字"""

        try:
            response = self.deepseek.ask(prompt)
            
            # 为热门 Issue 生成简要概述
            hot_issues_with_summary = self._add_hot_issue_summaries(processed['hot_issues'][:5])
            processed['hot_issues'] = hot_issues_with_summary
            
            return {
                'summary': response,
                'stats': processed,
                'ai_enabled': True
            }
        except Exception as e:
            print(f"[ERROR] AI 分析失败: {e}")
            return {
                'summary': self._generate_rule_based_summary(processed, repo_name),
                'stats': processed,
                'ai_enabled': False
            }
    
    def _add_hot_issue_summaries(self, hot_issues: List[Dict]) -> List[Dict]:
        """为热门 Issue 添加 AI 生成的简要概述"""
        if not hot_issues or not self.use_ai or not self.deepseek:
            return hot_issues
        
        try:
            # 批量为所有热门 Issue 生成概述
            issues_text = "\n".join([
                f"#{issue['number']}: {issue['title']}"
                for issue in hot_issues
            ])
            
            prompt = f"""请为以下热门 Issue 各生成一句话概述（不超过30字），说明这个 Issue 讨论的核心问题是什么。

{issues_text}

格式要求：
- 每行一个，格式为: #编号: 一句话概述
- 直接说明问题本质，不要废话
- 每个概述不超过30字"""

            response = self.deepseek.ask(prompt)
            
            # 解析响应，提取每个 Issue 的概述
            summaries = {}
            for line in response.strip().split('\n'):
                if '#' in line and ':' in line:
                    try:
                        # 解析 "#123: 概述内容"
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            num_part = parts[0].strip()
                            summary_part = parts[1].strip()
                            # 提取数字
                            import re
                            num_match = re.search(r'#?(\d+)', num_part)
                            if num_match:
                                issue_num = int(num_match.group(1))
                                summaries[issue_num] = summary_part
                    except:
                        continue
            
            # 添加概述到热门 Issue
            for issue in hot_issues:
                issue_num = issue.get('number')
                if issue_num in summaries:
                    issue['ai_summary'] = summaries[issue_num]
            
            return hot_issues
            
        except Exception as e:
            print(f"[WARN] 生成热门 Issue 概述失败: {e}")
            return hot_issues


def get_issue_analyzer() -> Optional[IssueAnalyzer]:
    """获取 Issue 分析器实例"""
    try:
        return IssueAnalyzer()
    except Exception as e:
        print(f"[WARN] Issue 分析器初始化失败: {e}")
        return None

