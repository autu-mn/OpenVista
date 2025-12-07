"""
数据服务层
处理时间对齐、关键词提取、波动分析
支持从真实数据文件读取，动态确定时间范围
"""
import json
import os
import re
import glob
from datetime import datetime
from collections import defaultdict, Counter
import jieba
import jieba.analyse

# 数据目录 - 优先使用DataProcessor/data，如果没有则使用Data
DATA_DIR_OLD = os.path.join(os.path.dirname(__file__), 'Data')
DATA_DIR_NEW = os.path.join(os.path.dirname(__file__), 'DataProcessor', 'data')

# 自动选择存在的数据目录
if os.path.exists(DATA_DIR_NEW):
    DATA_DIR = DATA_DIR_NEW
elif os.path.exists(DATA_DIR_OLD):
    DATA_DIR = DATA_DIR_OLD
else:
    DATA_DIR = DATA_DIR_NEW  # 默认使用新路径


class DataService:
    """数据处理服务"""
    
    def __init__(self):
        self.loaded_data = {}
        self.loaded_timeseries = {}
        self.loaded_text = {}
        
        # 指标分组配置 - 按类型和数量级分组
        self.metric_groups = {
            'popularity': {
                'name': '项目热度',
                'description': 'Star、Fork、活跃度等反映项目受欢迎程度的指标',
                'metrics': {
                    'opendigger_Star数': {'key': 'Star数', 'color': '#FFD700', 'unit': '个'},
                    'opendigger_Fork数': {'key': 'Fork数', 'color': '#00ff88', 'unit': '个'},
                    'opendigger_活跃度': {'key': '活跃度', 'color': '#7b61ff', 'unit': ''},
                    'opendigger_OpenRank': {'key': '影响力', 'color': '#ff6b9d', 'unit': ''},
                }
            },
            'development': {
                'name': '开发活动',
                'description': 'Commit、PR 等反映开发活跃度的指标',
                'metrics': {
                    'opendigger_代码提交数': {'key': '代码提交数', 'color': '#00f5d4', 'unit': '次'},
                    'opendigger_PR接受数': {'key': 'PR接受数', 'color': '#4CAF50', 'unit': '个'},
                    'opendigger_PR拒绝数': {'key': 'PR拒绝数', 'color': '#ff6b9d', 'unit': '个'},
                }
            },
            'issues': {
                'name': 'Issue 活动',
                'description': 'Issue 的创建和关闭数量',
                'metrics': {
                    'opendigger_新增Issue': {'key': '新增Issue', 'color': '#2196F3', 'unit': '个'},
                    'opendigger_关闭Issue': {'key': '关闭Issue', 'color': '#4CAF50', 'unit': '个'},
                }
            },
            'contributors': {
                'name': '贡献者',
                'description': '参与者、新增贡献者等人员相关指标',
                'metrics': {
                    'opendigger_参与者数': {'key': '参与者数', 'color': '#9C27B0', 'unit': '人'},
                    'opendigger_新增贡献者': {'key': '新增贡献者', 'color': '#00f5d4', 'unit': '人'},
                    'opendigger_总线因子': {'key': '总线因子', 'color': '#FFD700', 'unit': ''},
                    'opendigger_不活跃贡献者': {'key': '不活跃贡献者', 'color': '#ff6b9d', 'unit': '人'},
                }
            },
            'issue_response': {
                'name': 'Issue 响应效率',
                'description': 'Issue 响应时间、解决时长等效率指标（单位：小时）',
                'metrics': {
                    'opendigger_Issue响应时间': {'key': 'Issue响应时间', 'color': '#2196F3', 'unit': '小时'},
                    'opendigger_Issue解决时长': {'key': 'Issue解决时长', 'color': '#FF9800', 'unit': '小时'},
                    'opendigger_Issue存活时间': {'key': 'Issue存活时间', 'color': '#9C27B0', 'unit': '小时'},
                }
            },
            'pr_response': {
                'name': 'PR 响应效率',
                'description': 'PR 响应时间、处理时长等效率指标（单位：小时）',
                'metrics': {
                    'opendigger_PR响应时间': {'key': 'PR响应时间', 'color': '#00f5d4', 'unit': '小时'},
                    'opendigger_PR处理时长': {'key': 'PR处理时长', 'color': '#FFD700', 'unit': '小时'},
                    'opendigger_PR存活时间': {'key': 'PR存活时间', 'color': '#ff6b9d', 'unit': '小时'},
                }
            }
        }
        
        # Issue 分类关键词
        self.category_keywords = {
            '功能需求': ['feature', 'request', 'enhancement', 'add', 'support', 'implement', '功能', '需求', '新增', '支持'],
            'Bug修复': ['bug', 'fix', 'error', 'issue', 'crash', 'fail', 'broken', '错误', '修复', '问题', '崩溃'],
            '社区咨询': ['question', 'help', 'how', 'why', 'doc', 'documentation', '问题', '帮助', '文档', '如何']
        }
        
        # 自动加载 Data 目录下的数据
        self._auto_load_data()
    
    def _auto_load_data(self):
        """自动加载 Data 目录下的所有处理后的数据"""
        if not os.path.exists(DATA_DIR):
            print(f"数据目录不存在: {DATA_DIR}")
            return
        
        # 支持两种目录结构：
        # 1. 旧结构：Data/{project}_text_data_{timestamp}_processed/
        # 2. 新结构：DataProcessor/data/{owner}_{repo}/{project}_text_data_{timestamp}_processed/
        
        for item in os.listdir(DATA_DIR):
            item_path = os.path.join(DATA_DIR, item)
            
            if os.path.isdir(item_path):
                # 检查是否是项目文件夹（新结构）
                processed_folders = [
                    f for f in os.listdir(item_path)
                    if os.path.isdir(os.path.join(item_path, f)) and '_processed' in f
                ]
                
                if processed_folders:
                    # 新结构：项目文件夹下有processed文件夹
                    for processed_folder in processed_folders:
                        folder_path = os.path.join(item_path, processed_folder)
                        timeseries_file = os.path.join(folder_path, 'timeseries_data.json')
                        
                        if os.path.exists(timeseries_file):
                            # 使用项目文件夹名作为repo_key（格式：owner_repo -> owner/repo）
                            # 但保留原始格式用于查找
                            repo_key = item.replace('_', '/')
                            # 同时保存两种格式的映射
                            self._load_processed_data(repo_key, folder_path)
                            # 也保存原始格式（owner_repo）以便查找
                            self._load_processed_data(item, folder_path)
                elif item.endswith('_processed'):
                    # 旧结构：直接在Data目录下的processed文件夹
                    folder_path = item_path
                    timeseries_file = os.path.join(folder_path, 'timeseries_data.json')
                    
                    if os.path.exists(timeseries_file):
                        # 从文件夹名提取仓库名
                        parts = item.replace('_processed', '').split('_text_data_')
                        if len(parts) >= 1:
                            repo_parts = parts[0].split('_')
                            if len(repo_parts) >= 2:
                                repo_key = f"{repo_parts[0]}/{repo_parts[1]}"
                            else:
                                repo_key = parts[0].replace('_', '/')
                        else:
                            repo_key = item.replace('_processed', '').replace('_', '/')
                        
                        print(f"自动加载数据: {repo_key} from {item}")
                        self._load_processed_data(repo_key, folder_path)
    
    def _load_processed_data(self, repo_key, folder_path):
        """加载处理后的数据文件夹"""
        timeseries_file = os.path.join(folder_path, 'timeseries_data.json')
        text_file = os.path.join(folder_path, 'text_data_structured.json')
        
        # 加载时序数据
        if os.path.exists(timeseries_file):
            try:
            with open(timeseries_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.loaded_timeseries[repo_key] = data
                    elif isinstance(data, list):
                        timeseries_dict = {}
                        for item in data:
                            if isinstance(item, dict):
                                for key, value in item.items():
                                    if key != 'date' and key not in timeseries_dict:
                                        timeseries_dict[key] = {'raw': {}}
                        if timeseries_dict:
                            self.loaded_timeseries[repo_key] = timeseries_dict
            except Exception as e:
                print(f"加载时序数据失败 {repo_key}: {e}")
        
        # 加载文本数据
        if os.path.exists(text_file):
            try:
            with open(text_file, 'r', encoding='utf-8') as f:
                self.loaded_text[repo_key] = json.load(f)
            except Exception as e:
                print(f"加载文本数据失败 {repo_key}: {e}")
    
    def _generate_time_range(self, start, end):
        """生成时间范围列表 (YYYY-MM 格式)"""
        result = []
        start_year, start_month = map(int, start.split('-'))
        end_year, end_month = map(int, end.split('-'))
        
        year, month = start_year, start_month
        while (year, month) <= (end_year, end_month):
            result.append(f"{year:04d}-{month:02d}")
            month += 1
            if month > 12:
                month = 1
                year += 1
        return result
    
    def _extract_time_range_from_data(self, timeseries_data):
        """从时序数据中提取时间范围"""
        if not isinstance(timeseries_data, dict):
            return [], None, None
        
        all_months = set()
        
        for metric_name, metric_data in timeseries_data.items():
            if not isinstance(metric_data, dict):
                continue
            raw_data = metric_data.get('raw', {})
            if not isinstance(raw_data, dict):
                continue
            for key in raw_data.keys():
                # 只提取 YYYY-MM 格式的月份数据
                if re.match(r'^\d{4}-\d{2}$', key):
                    all_months.add(key)
        
        if not all_months:
            return [], None, None
        
        sorted_months = sorted(all_months)
        start_month = sorted_months[0]
        end_month = sorted_months[-1]
        
        # 生成完整的时间范围
        time_range = self._generate_time_range(start_month, end_month)
        
        return time_range, start_month, end_month
    
    def get_loaded_repos(self):
        """获取已加载的仓库列表"""
        repos = set(self.loaded_timeseries.keys()) | set(self.loaded_text.keys())
        return list(repos)
    
    def load_data(self, file_path):
        """加载数据文件（保持向后兼容）"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 提取仓库信息
        repo_info = data.get('repo_info', {})
        repo_key = repo_info.get('full_name', os.path.basename(file_path).replace('.json', ''))
        
        self.loaded_data[repo_key] = data
        
        return {
            'repo_key': repo_key,
            'repo_info': repo_info,
            'stats': {
                'issues_count': len(data.get('issues', [])),
                'pulls_count': len(data.get('pulls', [])),
                'commits_count': len(data.get('commits', [])),
                'releases_count': len(data.get('releases', [])),
                'contributors_count': len(data.get('contributors', []))
            }
        }
    
    def _normalize_repo_key(self, repo_key):
        """标准化仓库key格式，支持两种格式的查找"""
        # 先尝试原始格式
        if repo_key in self.loaded_timeseries or repo_key in self.loaded_text:
            return repo_key
        
        # 尝试转换格式
        if '/' in repo_key:
            alt_key = repo_key.replace('/', '_')
            if alt_key in self.loaded_timeseries or alt_key in self.loaded_text:
                return alt_key
        elif '_' in repo_key:
            alt_key = repo_key.replace('_', '/')
            if alt_key in self.loaded_timeseries or alt_key in self.loaded_text:
                return alt_key
        
        return repo_key  # 如果都不存在，返回原始key
    
    def get_grouped_timeseries(self, repo_key):
        """
        获取按类型分组的时序数据
        从真实数据文件读取，动态确定时间范围
        """
        repo_key = self._normalize_repo_key(repo_key)
        
        if repo_key not in self.loaded_timeseries:
            raise ValueError(f"仓库 {repo_key} 的时序数据未加载")
        
        timeseries_data = self.loaded_timeseries[repo_key]
        
        # 动态提取时间范围
        time_range, start_month, end_month = self._extract_time_range_from_data(timeseries_data)
        
        if not time_range:
            raise ValueError(f"无法从数据中提取时间范围")
        
        result = {
            'timeAxis': time_range,
            'startMonth': start_month,
            'endMonth': end_month,
            'groups': {}
        }
        
        for group_key, group_config in self.metric_groups.items():
            group_data = {
                'name': group_config['name'],
                'description': group_config['description'],
                'metrics': {}
            }
            
            has_data = False
            
            for metric_full_key, metric_config in group_config['metrics'].items():
                # 获取原始数据
                raw_metric_data = timeseries_data.get(metric_full_key, {})
                raw_data = raw_metric_data.get('raw', {})
                
                # 对齐到时间轴，标记缺失值
                aligned_data = []
                missing_indices = []
                
                for i, month in enumerate(time_range):
                    value = raw_data.get(month)
                    if value is not None:
                        aligned_data.append(float(value))
                    else:
                        # 缺失值标记为 None
                        aligned_data.append(None)
                        missing_indices.append(i)
                
                # 填充缺失值的插值位置（用于显示）
                interpolated_data = self._interpolate_missing(aligned_data)
                
                # 计算缺失值比例
                total_points = len(aligned_data)
                missing_count = len(missing_indices)
                missing_ratio = missing_count / total_points if total_points > 0 else 1.0
                
                # 重要指标（OpenRank）不跳过，即使缺失率高
                important_keywords = ['openrank', 'OpenRank', '影响力']
                is_important = any(keyword in metric_full_key for keyword in important_keywords)
                
                # 如果缺失值超过95%且不是重要指标，跳过该指标
                if missing_ratio > 0.95 and not is_important:
                    print(f"  跳过指标 {metric_config['key']}: 缺失率 {missing_ratio*100:.1f}% > 95%")
                    continue
                elif missing_ratio > 0.8:
                    # 缺失率在80%-95%之间，显示警告但仍保留
                    if is_important:
                        print(f"  ⭐ 保留重要指标 {metric_config['key']}: 缺失率 {missing_ratio*100:.1f}%")
                    else:
                        print(f"  ⚠ 保留指标 {metric_config['key']}: 缺失率 {missing_ratio*100:.1f}%")
                
                # 检查是否有有效数据
                if any(v is not None for v in aligned_data):
                    has_data = True
                
                group_data['metrics'][metric_full_key] = {
                    'name': metric_config['key'],
                    'data': aligned_data,
                    'interpolated': interpolated_data,
                    'missingIndices': missing_indices,
                    'missingRatio': round(missing_ratio * 100, 1),
                    'color': metric_config['color'],
                    'unit': metric_config['unit']
                }
            
            # 只添加有数据的分组
            if has_data:
                result['groups'][group_key] = group_data
        
        return result
    
    def _interpolate_missing(self, data):
        """对缺失值进行插值（用于显示缺失点的位置）"""
        result = data.copy()
        n = len(result)
        
        for i in range(n):
            if result[i] is None:
                # 找前一个有效值
                prev_val = None
                prev_idx = i - 1
                while prev_idx >= 0 and result[prev_idx] is None:
                    prev_idx -= 1
                if prev_idx >= 0:
                    prev_val = result[prev_idx]
                
                # 找后一个有效值
                next_val = None
                next_idx = i + 1
                while next_idx < n and result[next_idx] is None:
                    next_idx += 1
                if next_idx < n:
                    next_val = result[next_idx]
                
                # 计算插值
                if prev_val is not None and next_val is not None:
                    result[i] = (prev_val + next_val) / 2
                elif prev_val is not None:
                    result[i] = prev_val
                elif next_val is not None:
                    result[i] = next_val
                else:
                    result[i] = 0
        
        return result
    
    def _get_value(self, data_dict, month):
        """安全获取数值"""
        if not isinstance(data_dict, dict):
            return 0
        value = data_dict.get(month, 0)
        if value is None:
            return 0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0
    
    def get_aligned_issues(self, repo_key, target_month=None):
        """
        获取按月对齐的 Issue 数据
        从文本数据中提取
        """
        repo_key = self._normalize_repo_key(repo_key)
        
        if repo_key not in self.loaded_text:
            # 返回空数据
            return {
                'timeAxis': [],
                'monthlyData': {}
            }
        
        text_data = self.loaded_text[repo_key]
        
        # 从文本数据中提取 Issues
        issues = [doc for doc in text_data if doc.get('type') == 'issue']
        
        # 按月分组
        issues_by_month = defaultdict(list)
        for issue in issues:
            # 从 metadata 或 content 中提取创建时间
            metadata = issue.get('metadata', {})
            content = issue.get('content', '')
            
            # 尝试从内容中提取创建时间
            created_match = re.search(r'创建时间:\s*(\d{4}-\d{2})', content)
            if created_match:
                month = created_match.group(1)
                issues_by_month[month].append(issue)
        
        # 获取时间范围
        if repo_key in self.loaded_timeseries:
            time_range, _, _ = self._extract_time_range_from_data(self.loaded_timeseries[repo_key])
        else:
            time_range = sorted(issues_by_month.keys())
        
        # 如果指定了月份，只返回该月份的数据
        if target_month:
            month_issues = issues_by_month.get(target_month, [])
            return self._process_month_issues(target_month, month_issues)
        
        # 返回所有月份的汇总数据
        result = {
            'timeAxis': time_range,
            'monthlyData': {}
        }
        
        for month in time_range:
            month_issues = issues_by_month.get(month, [])
            result['monthlyData'][month] = self._process_month_issues(month, month_issues)
        
        return result
    
    def _process_month_issues(self, month, issues):
        """处理单月的 Issue 数据"""
        if not issues:
            return {
                'month': month,
                'total': 0,
                'categories': {'功能需求': 0, 'Bug修复': 0, '社区咨询': 0, '其他': 0},
                'categoryRatios': {'功能需求': 0, 'Bug修复': 0, '社区咨询': 0, '其他': 0},
                'keywords': [],
                'events': [],
                'issues': []
            }
        
        # 分类统计
        categories = {'功能需求': 0, 'Bug修复': 0, '社区咨询': 0, '其他': 0}
        all_text = []
        events = []
        
        for issue in issues:
            # 获取标题和内容
            title = issue.get('title', '').lower()
            content = issue.get('content', '').lower()
            
            all_text.append(f"{title} {content}")
            
            # 分类
            categorized = False
            for category, keywords in self.category_keywords.items():
                for keyword in keywords:
                    if keyword in title or keyword in content:
                        categories[category] += 1
                        categorized = True
                        break
                if categorized:
                    break
            
            if not categorized:
                categories['其他'] += 1
            
            # 检测重大事件
            comments_match = re.search(r'评论数:\s*(\d+)', content)
            comments_count = int(comments_match.group(1)) if comments_match else 0
            
            if comments_count >= 10:
                number_match = re.search(r'Issue #(\d+)', issue.get('title', ''))
                events.append({
                    'number': number_match.group(1) if number_match else '',
                    'title': issue.get('title', ''),
                    'comments': comments_count,
                    'labels': [],
                    'url': '',
                    'state': ''
                })
        
        # 计算比例
        total = len(issues)
        category_ratios = {k: round(v / total * 100, 1) if total > 0 else 0 for k, v in categories.items()}
        
        # 提取关键词
        keywords = self._extract_keywords(' '.join(all_text))
        
        return {
            'month': month,
            'total': total,
            'categories': categories,
            'categoryRatios': category_ratios,
            'keywords': keywords[:20],
            'events': sorted(events, key=lambda x: x['comments'], reverse=True)[:5],
            'issues': [{
                'title': i.get('title', ''),
                'type': i.get('type', '')
            } for i in issues[:50]]
        }
    
    def _extract_keywords(self, text):
        """提取关键词"""
        if not text.strip():
            return []
        
        try:
            keywords = jieba.analyse.extract_tags(text, topK=30, withWeight=True)
            return [{'word': word, 'weight': round(weight, 3)} for word, weight in keywords]
        except:
            words = re.findall(r'\b[a-zA-Z]{3,}\b|\w{2,}', text.lower())
            word_counts = Counter(words)
            stopwords = {'the', 'and', 'for', 'with', 'this', 'that', 'from', 'are', 'was', 'were', 'been', 'have', 'has', 'had', 'not', 'but', 'can', 'will', 'would', 'could', 'should'}
            filtered = [(w, c) for w, c in word_counts.most_common(30) if w not in stopwords]
            return [{'word': word, 'weight': count} for word, count in filtered]
    
    def analyze_waves(self, repo_key):
        """
        波动归因分析
        识别指标的显著变化，并关联对应月份的 Issue 文本
        """
        repo_key = self._normalize_repo_key(repo_key)
        grouped_data = self.get_grouped_timeseries(repo_key)
        issues_data = self.get_aligned_issues(repo_key)
        
        waves = []
        
        for group_key, group_info in grouped_data['groups'].items():
            for metric_key, metric_info in group_info['metrics'].items():
                data = metric_info['data']
                metric_name = metric_info['name']
                
                # 检测波动（跳过 None 值）
                for i in range(1, len(data)):
                    if data[i] is None or data[i-1] is None:
                        continue
                    
                    prev_val = data[i-1] or 0.001
                    curr_val = data[i] or 0
                    
                    if prev_val > 0:
                        change_rate = (curr_val - prev_val) / prev_val * 100
                    else:
                        change_rate = 100 if curr_val > 0 else 0
                    
                    if abs(change_rate) >= 25:
                        month = grouped_data['timeAxis'][i]
                        month_data = issues_data['monthlyData'].get(month, {})
                        
                        wave = {
                            'metric': metric_name,
                            'metricKey': metric_key,
                            'group': group_info['name'],
                            'groupKey': group_key,
                            'month': month,
                            'previousMonth': grouped_data['timeAxis'][i-1],
                            'previousValue': prev_val if prev_val != 0.001 else 0,
                            'currentValue': curr_val,
                            'changeRate': round(change_rate, 1),
                            'trend': '上升' if change_rate > 0 else '下降',
                            'keywords': month_data.get('keywords', [])[:10],
                            'events': month_data.get('events', [])[:3],
                            'categories': month_data.get('categories', {}),
                            'issueCount': month_data.get('total', 0)
                        }
                        
                        wave['explanation'] = self._generate_explanation(wave)
                        waves.append(wave)
        
        waves.sort(key=lambda x: abs(x['changeRate']), reverse=True)
        
        return {
            'repo': repo_key,
            'totalWaves': len(waves),
            'waves': waves[:50]
        }
    
    def _generate_explanation(self, wave):
        """生成波动解释"""
        metric = wave['metric']
        month = wave['month']
        trend = wave['trend']
        rate = abs(wave['changeRate'])
        keywords = wave['keywords']
        events = wave['events']
        
        explanation = f"{month} {metric} {trend} {rate:.1f}%"
        
        if keywords:
            top_keywords = ', '.join([k['word'] for k in keywords[:5]])
            explanation += f"。当月高频关键词：{top_keywords}"
        
        if events:
            event_titles = '; '.join([f"#{e.get('number', '')} {e.get('title', '')[:30]}" for e in events[:2]])
            explanation += f"。重要事件：{event_titles}"
        
        return explanation
    
    def get_month_keywords(self, repo_key, month):
        """获取指定月份的关键词"""
        issues_data = self.get_aligned_issues(repo_key, month)
        return {
            'month': month,
            'keywords': issues_data.get('keywords', [])
        }
    
    def get_major_events(self, repo_key):
        """获取所有重大事件"""
        repo_key = self._normalize_repo_key(repo_key)
        
        if repo_key not in self.loaded_text:
            return {
                'repo': repo_key,
                'totalEvents': 0,
                'events': []
            }
        
        text_data = self.loaded_text[repo_key]
        events = []
        
        # 从 Issues 中提取重大事件
        for doc in text_data:
            if doc.get('type') != 'issue':
                continue
            
            content = doc.get('content', '')
            comments_match = re.search(r'评论数:\s*(\d+)', content)
            comments_count = int(comments_match.group(1)) if comments_match else 0
            
            if comments_count >= 15:
                created_match = re.search(r'创建时间:\s*(\d{4}-\d{2}-\d{2})', content)
                date = created_match.group(1) if created_match else ''
                
                events.append({
                    'type': 'issue',
                    'date': date,
                    'month': date[:7] if date else '',
                    'title': doc.get('title', ''),
                    'impact': 'high' if comments_count >= 30 else 'medium',
                    'comments': comments_count
                })
        
        # 从 Releases 中提取
        for doc in text_data:
            if doc.get('type') != 'release':
                continue
            
            content = doc.get('content', '')
            created_match = re.search(r'发布时间:\s*(\d{4}-\d{2}-\d{2})', content)
            date = created_match.group(1) if created_match else ''
            
            events.append({
                'type': 'release',
                'date': date,
                'month': date[:7] if date else '',
                'title': doc.get('title', ''),
                'impact': 'high'
            })
        
        events.sort(key=lambda x: x['date'], reverse=True)
        
        return {
            'repo': repo_key,
            'totalEvents': len(events),
            'events': events[:100]
        }
    
    def get_repo_summary(self, repo_key):
        """获取仓库摘要信息"""
        # 支持两种格式：owner/repo 或 owner_repo
        actual_key = self._normalize_repo_key(repo_key)
        
        summary = {
            'repoKey': repo_key,
            'hasTimeseries': actual_key in self.loaded_timeseries,
            'hasText': actual_key in self.loaded_text
        }
        
        if actual_key in self.loaded_timeseries:
            time_range, start, end = self._extract_time_range_from_data(self.loaded_timeseries[actual_key])
            summary['timeRange'] = {
                'start': start,
                'end': end,
                'months': len(time_range)
            }
            summary['metrics'] = list(self.loaded_timeseries[actual_key].keys())
        
        if actual_key in self.loaded_text:
            text_data = self.loaded_text[actual_key]
            
            # 提取仓库基本信息
            for doc in text_data:
                if doc.get('type') == 'repo_info':
                    content = doc.get('content', '')
                    repo_info = {}
                    
                    # 解析仓库信息
                    lines = content.split('\n')
                    for line in lines:
                        if ':' in line:
                            key, value = line.split(':', 1)
                            key = key.strip()
                            value = value.strip()
                            
                            if key == '仓库名称':
                                repo_info['full_name'] = value
                            elif key == '描述':
                                repo_info['description'] = value
                            elif key == '主页':
                                repo_info['homepage'] = value
                            elif key == '编程语言':
                                repo_info['language'] = value
                            elif key == 'Star数':
                                repo_info['stars'] = int(value) if value.isdigit() else 0
                            elif key == 'Fork数':
                                repo_info['forks'] = int(value) if value.isdigit() else 0
                            elif key == 'Watcher数':
                                repo_info['watchers'] = int(value) if value.isdigit() else 0
                            elif key == '开放Issue数':
                                repo_info['open_issues'] = int(value) if value.isdigit() else 0
                            elif key == '创建时间':
                                repo_info['created_at'] = value
                            elif key == '更新时间':
                                repo_info['updated_at'] = value
                            elif key == '许可证':
                                repo_info['license'] = value
                            elif key == '标签':
                                repo_info['topics'] = [t.strip() for t in value.split(',') if t.strip()]
                    
                    if repo_info:
                        summary['repoInfo'] = repo_info
                    break
            summary['textStats'] = {
                'total': len(text_data),
                'issues': sum(1 for d in text_data if d.get('type') == 'issue'),
                'prs': sum(1 for d in text_data if d.get('type') == 'pull_request'),
                'commits': sum(1 for d in text_data if d.get('type') == 'commit'),
                'releases': sum(1 for d in text_data if d.get('type') == 'release')
            }
        
        return summary
    
    def get_demo_data(self):
        """获取演示数据 - 优先使用真实数据"""
        repos = self.get_loaded_repos()
        
        if repos:
            # 使用第一个已加载的真实仓库
            repo_key = repos[0]
            return self._get_real_repo_data(repo_key)
        else:
            # 没有真实数据，返回错误提示
            return {
                'error': '没有找到真实数据。请将处理后的数据放入 Data 目录。',
                'dataDir': DATA_DIR
            }
    
    def _get_real_repo_data(self, repo_key):
        """获取真实仓库的数据"""
        result = {
            'repoKey': repo_key,
            'repoInfo': {
                'name': repo_key.split('/')[-1] if '/' in repo_key else repo_key,
                'description': f'{repo_key} 的真实数据',
                'language': 'Unknown'
            }
        }
        
        # 获取分组时序数据
        try:
            result['groupedTimeseries'] = self.get_grouped_timeseries(repo_key)
        except Exception as e:
            result['groupedTimeseries'] = {'error': str(e)}
        
        # 获取 Issue 分析数据
        try:
            issues_data = self.get_aligned_issues(repo_key)
            result['issueCategories'] = [
                {
                    'month': month,
                    'total': data.get('total', 0),
                    'categories': data.get('categories', {})
                }
                for month, data in issues_data.get('monthlyData', {}).items()
            ]
            result['monthlyKeywords'] = {
                month: data.get('keywords', [])
                for month, data in issues_data.get('monthlyData', {}).items()
            }
        except Exception as e:
            result['issueCategories'] = []
            result['monthlyKeywords'] = {}
        
        # 获取波动分析
        try:
            waves_data = self.analyze_waves(repo_key)
            result['waves'] = waves_data.get('waves', [])
        except Exception as e:
            result['waves'] = []
        
        return result
