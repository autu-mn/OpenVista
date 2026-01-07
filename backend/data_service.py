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
        self.loaded_issue_classification = {}
        self.loaded_project_summary = {}
        
        # 指标分组配置 - 按类型和数量级分组
        self.metric_groups = {
            'popularity': {
                'name': '项目热度',
                'description': 'Star、Fork、活跃度等反映项目受欢迎程度的指标',
                'metrics': {
                    'opendigger_Star数': {'key': 'Star数', 'color': '#FFD700', 'unit': '个'},
                    'opendigger_Fork数': {'key': 'Fork数', 'color': '#00ff88', 'unit': '个'},
                    'opendigger_活跃度': {'key': '活跃度', 'color': '#7b61ff', 'unit': ''},
                    'opendigger_OpenRank': {'key': 'OpenRank', 'color': '#ff6b9d', 'unit': ''},
                }
            },
            'development': {
                'name': '开发活动',
                'description': 'PR、代码变更等反映开发活跃度的指标',
                'metrics': {
                    'opendigger_PR接受数': {'key': 'PR接受数', 'color': '#4CAF50', 'unit': '个'},
                    'opendigger_变更请求': {'key': '变更请求', 'color': '#2196F3', 'unit': '个'},
                    'opendigger_PR审查': {'key': 'PR审查', 'color': '#FF9800', 'unit': '次'},
                    # 以下指标仅用于可视化，不支持 GitPulse 预测
                    'opendigger_代码新增行数': {'key': '代码新增行数', 'color': '#00f5d4', 'unit': '行', 'predictable': False},
                    'opendigger_代码删除行数': {'key': '代码删除行数', 'color': '#ff6b9d', 'unit': '行', 'predictable': False},
                    'opendigger_代码变更总行数': {'key': '代码变更总行数', 'color': '#9C27B0', 'unit': '行', 'predictable': False}, 
                }
            },
            'issues': {
                'name': 'Issue 活动',
                'description': 'Issue 的创建和关闭数量',
                'metrics': {
                    'opendigger_新增Issue': {'key': '新增Issue', 'color': '#2196F3', 'unit': '个'},
                    'opendigger_关闭Issue': {'key': '关闭Issue', 'color': '#4CAF50', 'unit': '个'},
                    'opendigger_Issue评论': {'key': 'Issue评论', 'color': '#9E9E9E', 'unit': '条'},
                }
            },
            'contributors': {
                'name': '贡献者',
                'description': '参与者、新增贡献者等人员相关指标',
                'metrics': {
                    'opendigger_参与者数': {'key': '参与者数', 'color': '#9C27B0', 'unit': '人'},
                    'opendigger_贡献者': {'key': '贡献者', 'color': '#673AB7', 'unit': '人'},
                    'opendigger_新增贡献者': {'key': '新增贡献者', 'color': '#00f5d4', 'unit': '人'},
                    'opendigger_总线因子': {'key': '总线因子', 'color': '#FFD700', 'unit': ''},
                    'opendigger_不活跃贡献者': {'key': '不活跃贡献者', 'color': '#ff6b9d', 'unit': '人'},
                }
            },
            'statistics': {
                'name': '统计指标',
                'description': '关注度等统计指标',
                'metrics': {
                    'opendigger_关注度': {'key': '关注度', 'color': '#00BCD4', 'unit': ''},
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
        
        # 支持三种目录结构：
        # 1. 旧结构：Data/{project}_text_data_{timestamp}_processed/
        # 2. 中间结构：DataProcessor/data/{owner}_{repo}/{project}_text_data_{timestamp}_processed/
        # 3. 新结构：DataProcessor/data/{owner}_{repo}/monthly_data_{timestamp}/
        
        try:
            items = os.listdir(DATA_DIR)
        except Exception as e:
            print(f"无法读取数据目录 {DATA_DIR}: {e}")
            return
        
        for item in items:
            try:
                item_path = os.path.join(DATA_DIR, item)
                
                if not os.path.isdir(item_path):
                    continue
                # 检查是否是项目文件夹（新结构）
                # 支持 monthly_data_* 和 *_processed 两种格式
                try:
                    data_folders = [
                        f for f in os.listdir(item_path)
                        if os.path.isdir(os.path.join(item_path, f)) and 
                        ('monthly_data_' in f or '_processed' in f)
                    ]
                except Exception as e:
                    print(f"  无法读取项目目录 {item_path}: {e}")
                    continue
                
                if data_folders:
                    # 按时间戳排序，取最新的
                    data_folders.sort(reverse=True)
                    latest_folder = data_folders[0]
                    folder_path = os.path.join(item_path, latest_folder)
                    timeseries_file = os.path.join(folder_path, 'timeseries_data.json')
                    timeseries_for_model_dir = os.path.join(folder_path, 'timeseries_for_model')
                    
                    # 检查是否有时序数据文件或目录
                    has_timeseries_data = False
                    try:
                        if os.path.exists(timeseries_file):
                            has_timeseries_data = True
                        elif os.path.exists(timeseries_for_model_dir):
                            try:
                                json_files = [f for f in os.listdir(timeseries_for_model_dir) if f.endswith('.json')]
                                if len(json_files) > 0:
                                    has_timeseries_data = True
                            except Exception as e:
                                print(f"  检查 {timeseries_for_model_dir} 失败: {e}")
                    except Exception as e:
                        print(f"  检查数据文件失败 {item}: {e}")
                        continue
                        
                    if has_timeseries_data:
                        # 使用项目文件夹名作为repo_key（格式：owner_repo -> owner/repo）
                        # 只替换最后一个下划线，以正确处理 owner 或 repo 名称中包含下划线的情况
                        if '_' in item:
                            last_underscore_idx = item.rfind('_')
                            if last_underscore_idx > 0 and last_underscore_idx < len(item) - 1:
                                repo_key = f"{item[:last_underscore_idx]}/{item[last_underscore_idx + 1:]}"
                            else:
                                # 如果格式不对，使用原始名称
                                repo_key = item
                        else:
                            repo_key = item
                        
                        print(f"自动加载数据: {repo_key} (from folder: {item}) from {latest_folder}")
                        # 加载数据（只使用规范化后的repo_key，避免重复加载）
                        try:
                            self._load_processed_data(repo_key, folder_path)
                            # 如果repo_key和item不同，也保存原始格式的映射（但不重新加载数据）
                            if repo_key != item:
                                # 只创建映射，不重新加载数据
                                if repo_key in self.loaded_timeseries:
                                    self.loaded_timeseries[item] = self.loaded_timeseries[repo_key]
                                if repo_key in self.loaded_text:
                                    self.loaded_text[item] = self.loaded_text[repo_key]
                        except Exception as e:
                            print(f"  加载数据失败 {repo_key}: {e}")
                            import traceback
                            traceback.print_exc()
                            continue
                        
                elif item.endswith('_processed'):
                    # 旧结构：直接在Data目录下的processed文件夹
                    folder_path = item_path
                    timeseries_file = os.path.join(folder_path, 'timeseries_data.json')
                    
                    if os.path.exists(timeseries_file):
                        # 从文件夹名提取仓库名
                        try:
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
                            try:
                                self._load_processed_data(repo_key, folder_path)
                            except Exception as e:
                                print(f"  加载旧格式数据失败 {item}: {e}")
                                import traceback
                                traceback.print_exc()
                                continue
                        except Exception as e:
                            print(f"  解析旧格式数据失败 {item}: {e}")
                            import traceback
                            traceback.print_exc()
                            continue
            except Exception as e:
                print(f"处理项目 {item} 时出错: {e}")
                import traceback
                traceback.print_exc()
                continue
    
    def _load_processed_data(self, repo_key, folder_path):
        """加载处理后的数据文件夹"""
        # 检查是否已经加载过这个 repo_key 的数据
        # 如果已经存在数据，验证是否来自同一个文件夹
        if repo_key in self.loaded_timeseries:
            # 检查文件夹路径是否匹配（通过检查metadata.json中的repo_info来验证）
            metadata_file = os.path.join(folder_path, 'metadata.json')
            project_summary_file = os.path.join(folder_path, 'project_summary.json')
            
            # 尝试从metadata或project_summary中获取实际的repo信息
            actual_repo_info = None
            if os.path.exists(metadata_file):
                try:
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                        repo_info = metadata.get('repo_info', {})
                        if repo_info:
                            full_name = repo_info.get('full_name', '')
                            if full_name:
                                # 验证full_name是否匹配repo_key
                                expected_key_variants = [
                                    repo_key,
                                    repo_key.replace('_', '/') if '_' in repo_key else repo_key.replace('/', '_'),
                                    full_name,
                                    full_name.replace('/', '_')
                                ]
                                # 如果repo_key与full_name不匹配，说明可能是错误的数据
                                if repo_key not in expected_key_variants and full_name not in expected_key_variants:
                                    print(f"  [ERROR] 数据不匹配！repo_key={repo_key}, 但文件夹中的数据是 {full_name}")
                                    print(f"  跳过加载，避免数据混乱。请检查文件夹命名是否正确。")
                                    return
                except Exception as e:
                    print(f"  验证数据匹配性失败: {e}")
            
            # 如果数据已存在且验证通过，跳过加载
            timeseries_file = os.path.join(folder_path, 'timeseries_data.json')
            if os.path.exists(timeseries_file):
                print(f"  [INFO] {repo_key} 的数据已存在，跳过加载（避免重复）")
                return
        
        timeseries_file = os.path.join(folder_path, 'timeseries_data.json')
        timeseries_for_model_dir = os.path.join(folder_path, 'timeseries_for_model')
        text_file = os.path.join(folder_path, 'text_data_structured.json')
        issue_classification_file = os.path.join(folder_path, 'issue_classification.json')
        
        # 加载时序数据（优先从 timeseries_data.json，如果没有则从 timeseries_for_model 目录）
        if os.path.exists(timeseries_file):
            try:
                with open(timeseries_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        # 检查数据格式：如果是按月份组织的格式 {"2020-08": {"OpenRank": 4.76, ...}}
                        # 需要转换为按指标组织的格式 {"opendigger_OpenRank": {"raw": {"2020-08": 4.76, ...}}}
                        first_key = list(data.keys())[0] if data else None
                        if first_key and isinstance(first_key, str) and len(first_key) == 7 and first_key[4] == '-':
                            # 这是按月份组织的格式，需要转换
                            timeseries_dict = {}
                            for month, metrics in data.items():
                                if isinstance(metrics, dict):
                                    for metric_name, value in metrics.items():
                                        # 构建指标键名（添加 opendigger_ 前缀）
                                        metric_key = f'opendigger_{metric_name}'
                                        if metric_key not in timeseries_dict:
                                            timeseries_dict[metric_key] = {'raw': {}}
                                        timeseries_dict[metric_key]['raw'][month] = value
                            self.loaded_timeseries[repo_key] = timeseries_dict
                            print(f"  [OK] 已加载 {repo_key} 的时序数据: {len(timeseries_dict)} 个指标")
                        else:
                            # 已经是按指标组织的格式，直接使用
                            self.loaded_timeseries[repo_key] = data
                            print(f"  [OK] 已加载 {repo_key} 的时序数据: {len(data)} 个指标")
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
                import traceback
                traceback.print_exc()
                print(f"加载时序数据失败 {repo_key}: {e}")
        elif os.path.exists(timeseries_for_model_dir):
            # 从 timeseries_for_model 目录加载数据
            try:
                # 优先尝试加载 all_months.json（汇总文件）
                all_months_file = os.path.join(timeseries_for_model_dir, 'all_months.json')
                if os.path.exists(all_months_file):
                    with open(all_months_file, 'r', encoding='utf-8') as f:
                        monthly_data = json.load(f)
                    
                    # 转换为按指标组织的格式
                    timeseries_dict = {}
                    for month, data in monthly_data.items():
                        if isinstance(data, dict):
                            # 数据格式可能是两种：
                            # 1. 新格式：{"opendigger_metrics": {"OpenRank": 10.5, "活跃度": 20.3, ...}}
                            # 2. 旧格式：{"opendigger_OpenRank": 4.76, ...}
                            opendigger_metrics = data.get('opendigger_metrics', {})
                            if opendigger_metrics and isinstance(opendigger_metrics, dict):
                                # 新格式：从 opendigger_metrics 对象中提取指标
                                for metric_name, value in opendigger_metrics.items():
                                    metric_key = f"opendigger_{metric_name}"
                                    if metric_key not in timeseries_dict:
                                        timeseries_dict[metric_key] = {'raw': {}}
                                    timeseries_dict[metric_key]['raw'][month] = value
                            else:
                                # 旧格式：直接查找以 opendigger_ 开头的键
                                for metric_key, value in data.items():
                                    if metric_key.startswith('opendigger_'):
                                        if metric_key not in timeseries_dict:
                                            timeseries_dict[metric_key] = {'raw': {}}
                                        timeseries_dict[metric_key]['raw'][month] = value
                    
                    if timeseries_dict:
                        self.loaded_timeseries[repo_key] = timeseries_dict
                        # 统计每个指标的数据点数量
                        metric_info = []
                        for metric_key, metric_data in list(timeseries_dict.items())[:5]:  # 只显示前5个
                            data_points = len(metric_data.get('raw', {}))
                            metric_info.append(f"{metric_key}({data_points}个月)")
                        print(f"  [OK] 已从 timeseries_for_model 加载 {repo_key} 的时序数据: {len(timeseries_dict)} 个指标")
                        if metric_info:
                            print(f"    示例指标: {', '.join(metric_info)}")
                else:
                    # 如果没有 all_months.json，从各个月份的 JSON 文件加载
                    try:
                        month_files = [f for f in os.listdir(timeseries_for_model_dir) if f.endswith('.json') and f != 'all_months.json' and f != 'project_summary.json']
                    except Exception as e:
                        print(f"  无法读取 timeseries_for_model 目录 {timeseries_for_model_dir}: {e}")
                        month_files = []
                    
                    if month_files:
                        timeseries_dict = {}
                        for month_file in sorted(month_files):
                            month = month_file.replace('.json', '')
                            month_path = os.path.join(timeseries_for_model_dir, month_file)
                            try:
                                with open(month_path, 'r', encoding='utf-8') as f:
                                    data = json.load(f)
                                    if isinstance(data, dict):
                                        # 数据格式可能是两种：
                                        # 1. 新格式：{"opendigger_metrics": {"OpenRank": 10.5, "活跃度": 20.3, ...}}
                                        # 2. 旧格式：{"opendigger_OpenRank": 4.76, ...}
                                        opendigger_metrics = data.get('opendigger_metrics', {})
                                        if opendigger_metrics and isinstance(opendigger_metrics, dict):
                                            # 新格式：从 opendigger_metrics 对象中提取指标
                                            for metric_name, value in opendigger_metrics.items():
                                                metric_key = f"opendigger_{metric_name}"
                                                if metric_key not in timeseries_dict:
                                                    timeseries_dict[metric_key] = {'raw': {}}
                                                timeseries_dict[metric_key]['raw'][month] = value
                                        else:
                                            # 旧格式：直接查找以 opendigger_ 开头的键
                                            for metric_key, value in data.items():
                                                if metric_key.startswith('opendigger_'):
                                                    if metric_key not in timeseries_dict:
                                                        timeseries_dict[metric_key] = {'raw': {}}
                                                    timeseries_dict[metric_key]['raw'][month] = value
                            except Exception as e:
                                print(f"  加载月份文件 {month_file} 失败: {e}")
                        
                        if timeseries_dict:
                            self.loaded_timeseries[repo_key] = timeseries_dict
                            # 统计每个指标的数据点数量
                            metric_info = []
                            for metric_key, metric_data in list(timeseries_dict.items())[:5]:  # 只显示前5个
                                data_points = len(metric_data.get('raw', {}))
                                metric_info.append(f"{metric_key}({data_points}个月)")
                            print(f"  [OK] 已从 timeseries_for_model 加载 {repo_key} 的时序数据: {len(timeseries_dict)} 个指标，{len(month_files)} 个月")
                            if metric_info:
                                print(f"    示例指标: {', '.join(metric_info)}")
                        else:
                            print(f"  [WARN] 从 {len(month_files)} 个月份文件中未找到任何指标数据")
                            # 尝试打印第一个文件的内容结构以便调试
                            if month_files:
                                try:
                                    first_file = os.path.join(timeseries_for_model_dir, month_files[0])
                                    with open(first_file, 'r', encoding='utf-8') as f:
                                        sample_data = json.load(f)
                                        print(f"    示例文件结构: {list(sample_data.keys())[:10]}")
                                        if 'opendigger_metrics' in sample_data:
                                            print(f"    opendigger_metrics 中的指标: {list(sample_data['opendigger_metrics'].keys())[:10]}")
                                except Exception as e:
                                    print(f"    无法读取示例文件: {e}")
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"从 timeseries_for_model 加载时序数据失败 {repo_key}: {e}")
        
        # 加载文本数据
        if os.path.exists(text_file):
            try:
                with open(text_file, 'r', encoding='utf-8') as f:
                    self.loaded_text[repo_key] = json.load(f)
            except Exception as e:
                print(f"加载文本数据失败 {repo_key}: {e}")
        
        # 如果没有文本数据文件，尝试从 metadata.json 和 project_summary.json 构建
        if repo_key not in self.loaded_text:
            metadata_file = os.path.join(folder_path, 'metadata.json')
            project_summary_file = os.path.join(folder_path, 'project_summary.json')
            
            text_data = []
            
            # 从 metadata.json 提取 repo_info
            if os.path.exists(metadata_file):
                try:
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                        repo_info = metadata.get('repo_info', {})
                        if repo_info:
                            # 构建 repo_info 文档（格式与 text_data_structured.json 一致）
                            text_data.append({
                                'type': 'repo_info',
                                'content': json.dumps(repo_info, ensure_ascii=False),
                                'metadata': {
                                    'source': 'metadata.json',
                                    'crawl_time': metadata.get('crawl_time', '')
                                }
                            })
                except Exception as e:
                    print(f"加载 metadata.json 失败 {repo_key}: {e}")
            
            # 从 project_summary.json 提取 repo_info（如果 metadata.json 没有）
            if not text_data and os.path.exists(project_summary_file):
                try:
                    with open(project_summary_file, 'r', encoding='utf-8') as f:
                        project_summary = json.load(f)
                        repo_info = project_summary.get('repo_info', {})
                        if repo_info:
                            text_data.append({
                                'type': 'repo_info',
                                'content': json.dumps(repo_info, ensure_ascii=False),
                                'metadata': {
                                    'source': 'project_summary.json'
                                }
                            })
                except Exception as e:
                    print(f"加载 project_summary.json 失败 {repo_key}: {e}")
            
            if text_data:
                self.loaded_text[repo_key] = text_data
                print(f"  [OK] 已从 metadata.json 构建文本数据: {len(text_data)} 个文档")
        
        # 加载 Issue 分类数据
        if os.path.exists(issue_classification_file):
            try:
                with open(issue_classification_file, 'r', encoding='utf-8') as f:
                    self.loaded_issue_classification[repo_key] = json.load(f)
                    by_month = self.loaded_issue_classification[repo_key].get('by_month', {})
                    print(f"  [OK] 已加载Issue分类数据: {len(by_month)} 个月份")
            except Exception as e:
                print(f"加载Issue分类数据失败 {repo_key}: {e}")
        else:
            # 如果没有 issue_classification.json，尝试从月度数据生成
            print(f"  [INFO] Issue分类文件不存在，尝试从月度数据生成...")
            issue_classification = self._generate_issue_classification_from_monthly_data(repo_key, folder_path)
            if issue_classification:
                self.loaded_issue_classification[repo_key] = issue_classification
                by_month = issue_classification.get('by_month', {})
                print(f"  [OK] 已从月度数据生成Issue分类: {len(by_month)} 个月份")
        
        # 加载项目 AI 摘要（可能在 timeseries_for_model 目录下或根目录）
        project_summary_file = os.path.join(folder_path, 'timeseries_for_model', 'project_summary.json')
        if not os.path.exists(project_summary_file):
            project_summary_file = os.path.join(folder_path, 'project_summary.json')
        
        if os.path.exists(project_summary_file):
            try:
                with open(project_summary_file, 'r', encoding='utf-8') as f:
                    self.loaded_project_summary[repo_key] = json.load(f)
                    print(f"  [OK] 已加载项目 AI 摘要: {repo_key}")
            except Exception as e:
                print(f"加载项目摘要失败 {repo_key}: {e}")
    
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
        """从时序数据中提取时间范围
        
        注意：OpenDigger 数据通常有 2-3 个月的延迟，
        因此我们需要找到实际有有效数据的最后一个月，
        而不是简单地取时间轴的最后一个月。
        """
        if not isinstance(timeseries_data, dict):
            return [], None, None
        
        all_months = set()
        months_with_data = {}  # 记录每个月份有多少指标有非零数据
        
        for metric_name, metric_data in timeseries_data.items():
            if not isinstance(metric_data, dict):
                continue
            raw_data = metric_data.get('raw', {})
            if not isinstance(raw_data, dict):
                continue
            for key, value in raw_data.items():
                # 只提取 YYYY-MM 格式的月份数据
                if re.match(r'^\d{4}-\d{2}$', key):
                    all_months.add(key)
                    # 记录有非零数据的月份
                    if value is not None and value != 0:
                        months_with_data[key] = months_with_data.get(key, 0) + 1
        
        if not all_months:
            return [], None, None
        
        sorted_months = sorted(all_months)
        start_month = sorted_months[0]
        
        # 找到最后一个有至少3个指标有数据的月份（避免只有个别指标更新的情况）
        # 从后往前找，跳过没有足够数据的月份
        end_month = sorted_months[-1]
        for month in reversed(sorted_months):
            if months_with_data.get(month, 0) >= 3:  # 至少3个指标有数据
                end_month = month
                break
        
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
        if not repo_key:
            return repo_key
        
        # 先尝试原始格式
        if repo_key in self.loaded_timeseries or repo_key in self.loaded_text:
            return repo_key
        
        # 尝试转换格式（只替换最后一个下划线或第一个斜杠，以正确处理包含下划线的名称）
        if '/' in repo_key:
            # owner/repo -> owner_repo（只替换第一个斜杠）
            parts = repo_key.split('/', 1)
            if len(parts) == 2:
                alt_key = f"{parts[0]}_{parts[1]}"
                if alt_key in self.loaded_timeseries or alt_key in self.loaded_text:
                    # 验证数据是否真的匹配（通过检查数据特征）
                    if self._verify_repo_key_match(repo_key, alt_key):
                        return alt_key
        elif '_' in repo_key:
            # owner_repo -> owner/repo（只替换最后一个下划线）
            last_underscore_idx = repo_key.rfind('_')
            if last_underscore_idx > 0 and last_underscore_idx < len(repo_key) - 1:
                alt_key = f"{repo_key[:last_underscore_idx]}/{repo_key[last_underscore_idx + 1:]}"
                if alt_key in self.loaded_timeseries or alt_key in self.loaded_text:
                    # 验证数据是否真的匹配
                    if self._verify_repo_key_match(repo_key, alt_key):
                        return alt_key
        
        return repo_key  # 如果都不存在，返回原始key
    
    def _verify_repo_key_match(self, key1, key2):
        """验证两个repo_key是否指向同一个仓库的数据"""
        # 如果两个key都有数据，检查数据特征是否匹配
        data1 = self.loaded_timeseries.get(key1) or self.loaded_text.get(key1)
        data2 = self.loaded_timeseries.get(key2) or self.loaded_text.get(key2)
        
        if not data1 or not data2:
            return True  # 如果只有一个有数据，允许匹配
        
        # 检查时序数据的指标数量是否相同（简单验证）
        if key1 in self.loaded_timeseries and key2 in self.loaded_timeseries:
            metrics1 = set(self.loaded_timeseries[key1].keys())
            metrics2 = set(self.loaded_timeseries[key2].keys())
            if len(metrics1) > 0 and len(metrics2) > 0:
                # 如果指标数量差异很大，可能不是同一个项目
                if abs(len(metrics1) - len(metrics2)) > 5:
                    print(f"  [WARN] 数据不匹配：{key1} 有 {len(metrics1)} 个指标，{key2} 有 {len(metrics2)} 个指标")
                    return False
        
        return True
    
    def get_all_metrics_historical_data(self, repo_key):
        """
        获取所有指标的原始历史数据（用于 GitPulse 预测）
        
        Args:
            repo_key: 仓库标识（支持 owner/repo 或 owner_repo 格式）
        
        Returns:
            Dict[str, Dict[str, Dict[str, float]]]: {
                'opendigger_OpenRank': {'raw': {'2020-08': 4.76, ...}},
                'opendigger_活跃度': {'raw': {'2020-08': 0.5, ...}},
                ...
            }
            如果仓库不存在或没有数据，返回空字典
        """
        repo_key = self._normalize_repo_key(repo_key)
        
        if repo_key not in self.loaded_timeseries:
            return {}
        
        # 直接返回已加载的时序数据（已经是正确的格式）
        return self.loaded_timeseries[repo_key]
    
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
                important_keywords = ['openrank', 'OpenRank']
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
        """
        处理单月的 Issue 数据（基于抽样数据）
        
        注意：Issue 数据是抽样数据，不是全部 Issue。
        这里返回的是抽样统计结果，用于分析趋势和模式。
        """
        if not issues:
            return {
                'month': month,
                'total': 0,
                'total_sampled': 0,
                'is_sampled': True,
                'sampling_note': '数据为抽样数据，仅供参考',
                'categories': {'功能需求': 0, 'Bug修复': 0, '社区咨询': 0, '其他': 0},
                'categoryRatios': {'功能需求': 0, 'Bug修复': 0, '社区咨询': 0, '其他': 0},
                'keywords': [],
                'events': [],
                'issues': []
            }
        
        # 记录这是抽样数据
        total_sampled = len(issues)
        
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
        
        # 计算比例（基于抽样数据）
        total = len(issues)
        category_ratios = {k: round(v / total * 100, 1) if total > 0 else 0 for k, v in categories.items()}
        
        # 提取关键词
        keywords = self._extract_keywords(' '.join(all_text))
        
        return {
            'month': month,
            'total': total,  # 抽样总数
            'total_sampled': total_sampled,  # 明确标识为抽样数量
            'is_sampled': True,  # 标识这是抽样数据
            'sampling_note': f'基于 {total_sampled} 个抽样 Issue 的统计分析，不代表全部 Issue',
            'categories': categories,
            'categoryRatios': category_ratios,
            'keywords': keywords[:20],
            'events': sorted(events, key=lambda x: x['comments'], reverse=True)[:5],
            'issues': [{
                'title': i.get('title', ''),
                'type': i.get('type', '')
            } for i in issues[:50]]  # 只返回前50个作为示例
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
    
    def _generate_issue_classification_from_monthly_data(self, repo_key, folder_path):
        """
        从月度数据文件中提取 Issue 数据并生成分类
        
        Args:
            repo_key: 仓库键名
            folder_path: 数据文件夹路径
            
        Returns:
            Issue 分类数据字典，格式与 issue_classification.json 相同
        """
        try:
            timeseries_for_model_dir = os.path.join(folder_path, 'timeseries_for_model')
            if not os.path.exists(timeseries_for_model_dir):
                return None
            
            # 查找所有月份文件
            month_files = [f for f in os.listdir(timeseries_for_model_dir) 
                          if f.endswith('.json') and f != 'all_months.json' and f != 'project_summary.json']
            
            if not month_files:
                return None
            
            by_month = {}
            labels = {
                'feature': '功能需求',
                'bug': 'Bug修复',
                'question': '社区咨询',
                'other': '其他'
            }
            
            for month_file in sorted(month_files):
                month = month_file.replace('.json', '')
                month_path = os.path.join(timeseries_for_model_dir, month_file)
                
                try:
                    with open(month_path, 'r', encoding='utf-8') as f:
                        month_data = json.load(f)
                    
                    # 从月度数据中提取 Issue 文本
                    issues_text = ''
                    text_data = month_data.get('text_data', {})
                    if isinstance(text_data, dict):
                        breakdown = text_data.get('breakdown', {})
                        if isinstance(breakdown, dict):
                            issues_text = breakdown.get('issues_text', '')
                    
                    if not issues_text:
                        continue
                    
                    # 分类统计
                    categories = {'功能需求': 0, 'Bug修复': 0, '社区咨询': 0, '其他': 0}
                    issues_lower = issues_text.lower()
                    
                    # 使用关键词分类
                    for category, keywords in self.category_keywords.items():
                        for keyword in keywords:
                            if keyword.lower() in issues_lower:
                                # 计算该关键词出现的次数（简单计数）
                                count = issues_lower.count(keyword.lower())
                                categories[category] += count
                    
                    # 如果没有匹配到任何分类，尝试从 Issue 标题中提取
                    if sum(categories.values()) == 0:
                        # 从文本中提取 Issue 标题（格式：Issue #1234: Title）
                        issue_titles = re.findall(r'Issue #\d+:\s*([^\n]+)', issues_text, re.IGNORECASE)
                        for title in issue_titles:
                            title_lower = title.lower()
                            if any(kw in title_lower for kw in ['bug', 'error', 'fix', 'crash', 'broken', '错误', '修复', '问题', '崩溃']):
                                categories['Bug修复'] += 1
                            elif any(kw in title_lower for kw in ['feature', 'request', 'enhancement', 'add', '功能', '需求', '新增']):
                                categories['功能需求'] += 1
                            elif any(kw in title_lower for kw in ['question', 'help', 'how', 'why', '问题', '帮助', '如何']):
                                categories['社区咨询'] += 1
                            else:
                                categories['其他'] += 1
                    
                    total = sum(categories.values())
                    if total == 0:
                        total = 1  # 避免除零
                    
                    by_month[month] = {
                        'total': total,
                        'feature': categories['功能需求'],
                        'bug': categories['Bug修复'],
                        'question': categories['社区咨询'],
                        'other': categories['其他']
                    }
                except Exception as e:
                    print(f"  处理月份文件 {month_file} 失败: {e}")
                    continue
            
            if by_month:
                return {
                    'by_month': by_month,
                    'labels': labels
                }
        except Exception as e:
            print(f"  从月度数据生成Issue分类时出错: {e}")
            import traceback
            traceback.print_exc()
        
        return None
    
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
                    
                    # 尝试解析为JSON格式（新格式）
                    try:
                        repo_info = json.loads(content)
                        # 确保字段名匹配前端期望
                        if 'topics' in repo_info and isinstance(repo_info['topics'], list):
                            repo_info['topics'] = repo_info['topics']
                        if 'labels' in repo_info and isinstance(repo_info['labels'], list):
                            repo_info['labels'] = repo_info['labels']
                    except (json.JSONDecodeError, TypeError):
                        # 如果不是JSON，尝试解析为文本格式（旧格式兼容）
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
        
        # 加载项目摘要（包含 AI 摘要）
        if actual_key in self.loaded_project_summary:
            summary_data = self.loaded_project_summary[actual_key]
            summary['projectSummary'] = {
                'aiSummary': summary_data.get('ai_summary', ''),
                'issueStats': summary_data.get('issue_stats', {}),
                'dataRange': summary_data.get('date_range', summary_data.get('data_range', {})),
                'total_months': summary_data.get('total_months', 0)
            }
        else:
            summary['projectSummary'] = None
        
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
        
        # 获取 Issue 分析数据（优先使用预计算的分类数据）
        actual_key = self._normalize_repo_key(repo_key)
        try:
            if actual_key in self.loaded_issue_classification:
                # 使用预计算的 Issue 分类数据
                classification_data = self.loaded_issue_classification[actual_key]
                by_month = classification_data.get('by_month', {})
                labels = classification_data.get('labels', {
                    'feature': '功能需求', 'bug': 'Bug修复', 
                    'question': '社区咨询', 'other': '其他'
                })
                
                result['issueCategories'] = [
                    {
                        'month': month,
                        'total': data.get('total', 0),
                        'categories': {
                            labels.get('feature', '功能需求'): data.get('feature', 0),
                            labels.get('bug', 'Bug修复'): data.get('bug', 0),
                            labels.get('question', '社区咨询'): data.get('question', 0),
                            labels.get('other', '其他'): data.get('other', 0)
                        }
                    }
                    for month, data in sorted(by_month.items())
                ]
                result['monthlyKeywords'] = {}  # 预计算数据中没有关键词
            else:
                # 回退到从文本数据计算
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
        
        # 获取项目 AI 摘要
        if actual_key in self.loaded_project_summary:
            summary_data = self.loaded_project_summary[actual_key]
            result['projectSummary'] = {
                'aiSummary': summary_data.get('ai_summary', ''),
                'issueStats': summary_data.get('issue_stats', {}),
                'dataRange': summary_data.get('date_range', summary_data.get('data_range', {})),
                'total_months': summary_data.get('total_months', 0)
            }
        else:
            result['projectSummary'] = None
        
        return result
    
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
        
        # 获取 Issue 分析数据（优先使用预计算的分类数据）
        actual_key = self._normalize_repo_key(repo_key)
        try:
            if actual_key in self.loaded_issue_classification:
                # 使用预计算的 Issue 分类数据
                classification_data = self.loaded_issue_classification[actual_key]
                by_month = classification_data.get('by_month', {})
                labels = classification_data.get('labels', {
                    'feature': '功能需求', 'bug': 'Bug修复', 
                    'question': '社区咨询', 'other': '其他'
                })
                
                result['issueCategories'] = [
                    {
                        'month': month,
                        'total': data.get('total', 0),
                        'categories': {
                            labels.get('feature', '功能需求'): data.get('feature', 0),
                            labels.get('bug', 'Bug修复'): data.get('bug', 0),
                            labels.get('question', '社区咨询'): data.get('question', 0),
                            labels.get('other', '其他'): data.get('other', 0)
                        }
                    }
                    for month, data in sorted(by_month.items())
                ]
                result['monthlyKeywords'] = {}  # 预计算数据中没有关键词
            else:
                # 回退到从文本数据计算
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
        
        # 获取项目 AI 摘要
        if actual_key in self.loaded_project_summary:
            summary_data = self.loaded_project_summary[actual_key]
            result['projectSummary'] = {
                'aiSummary': summary_data.get('ai_summary', ''),
                'issueStats': summary_data.get('issue_stats', {}),
                'dataRange': summary_data.get('date_range', summary_data.get('data_range', {})),
                'total_months': summary_data.get('total_months', 0)
            }
        else:
            result['projectSummary'] = None
        
        return result
