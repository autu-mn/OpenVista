"""
OpenVista 后端 API
GitHub 仓库生态画像分析平台 - 时序数据可视化与归因分析
从真实数据文件读取，动态确定时间范围
"""
import logging
import sys
from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import os
from datetime import datetime
from collections import defaultdict
import re
from data_service import DataService
from Agent.qa_agent import QAAgent
from Agent.prediction_explainer import PredictionExplainer
from CHAOSSEvaluation import CHAOSSEvaluator

# ==================== 日志配置 ====================
def setup_logging():
    """配置详细的日志系统"""
    # 创建日志格式
    log_format = logging.Formatter(
        '[%(asctime)s] %(levelname)-8s | %(name)-20s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(log_format)
    root_logger.addHandler(console_handler)
    
    # 文件处理器（可选）
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    file_handler = logging.FileHandler(
        os.path.join(log_dir, 'openvista.log'),
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(log_format)
    root_logger.addHandler(file_handler)
    
    # 设置第三方库日志级别
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    return logging.getLogger('OpenVista')

logger = setup_logging()

# ==================== 初始化 GitPulse ====================
predictor = None
GITPULSE_AVAILABLE = False

try:
    from GitPulse.predictor import GitPulsePredictor
    predictor = GitPulsePredictor(enable_cache=True)
    GITPULSE_AVAILABLE = True
    logger.info("GitPulse 预测器初始化成功")
except (ImportError, FileNotFoundError) as e:
    logger.warning(f"GitPulse 初始化失败: {e}")
    logger.warning("预测功能将不可用，其他功能正常运行")
    logger.warning("如需预测功能，请确保:")
    logger.warning("  1. 已安装依赖: pip install -r GitPulse/requirements_predict.txt")
    logger.warning("  2. 模型文件存在: GitPulse/predict/models/best_model.pt")

app = Flask(__name__)
CORS(app)

# ==================== 请求日志中间件 ====================
@app.before_request
def log_request():
    """记录每个请求"""
    logger.info(f"REQUEST  | {request.method:6s} {request.path}")

@app.after_request
def log_response(response):
    """记录每个响应"""
    status = response.status_code
    level = logging.INFO if status < 400 else logging.WARNING if status < 500 else logging.ERROR
    logger.log(level, f"RESPONSE | {request.method:6s} {request.path} -> {status}")
    return response

# 数据服务实例
data_service = DataService()

# AI Agent实例
qa_agent = QAAgent()

# 预测解释器实例
prediction_explainer = PredictionExplainer()

# CHAOSS 评估器实例（使用增强版本）
chaoss_evaluator = CHAOSSEvaluator(data_service)


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})


@app.route('/api/reload', methods=['POST'])
def reload_data():
    """重新加载数据"""
    try:
        # 重新初始化数据服务以加载新数据
        data_service.__init__()
        repos = data_service.get_loaded_repos()
        return jsonify({
            'status': 'ok',
            'message': '数据重新加载成功',
            'repos': repos
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/repos', methods=['GET'])
def get_repos():
    """获取已加载的仓库列表"""
    repos = data_service.get_loaded_repos()
    summaries = [data_service.get_repo_summary(repo) for repo in repos]
    return jsonify({
        'repos': repos,
        'summaries': summaries
    })


@app.route('/api/repo/<path:repo_key>/summary', methods=['GET'])
def get_repo_summary(repo_key):
    """获取仓库摘要"""
    try:
        # 支持两种格式：owner/repo 或 owner_repo
        # 如果是 owner_repo 格式，转换为 owner/repo
        if '_' in repo_key and '/' not in repo_key:
            repo_key = repo_key.replace('_', '/')
        
        summary = data_service.get_repo_summary(repo_key)
        return jsonify(summary)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/load', methods=['POST'])
def load_data():
    """加载数据文件"""
    data = request.json
    file_path = data.get('file_path')
    
    if not file_path:
        return jsonify({'error': '请提供数据文件路径'}), 400
    
    try:
        result = data_service.load_data(file_path)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/timeseries/grouped/<path:repo_key>', methods=['GET'])
def get_grouped_timeseries(repo_key):
    """
    获取分组时序数据 - 所有 OpenDigger 指标按类型分组
    动态确定时间范围，标记缺失值
    """
    try:
        # 支持两种格式：owner/repo 或 owner_repo
        if '_' in repo_key and '/' not in repo_key:
            repo_key = repo_key.replace('_', '/')
        
        grouped = data_service.get_grouped_timeseries(repo_key)
        return jsonify(grouped)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/issues/<path:repo_key>', methods=['GET'])
def get_issues_by_month(repo_key):
    """
    获取按月对齐的 Issue 数据
    包含：标签分类、高频关键词、重大事件
    返回格式与前端期望一致：{ categories: [...], monthlyKeywords: {...} }
    """
    month = request.args.get('month')  # 可选参数，获取特定月份
    
    try:
        # 支持两种格式：owner/repo 或 owner_repo
        if '_' in repo_key and '/' not in repo_key:
            repo_key = repo_key.replace('_', '/')
        
        # 优先使用预计算的 Issue 分类数据
        actual_key = data_service._normalize_repo_key(repo_key)
        
        if actual_key in data_service.loaded_issue_classification:
            # 使用预计算的数据
            classification_data = data_service.loaded_issue_classification[actual_key]
            by_month = classification_data.get('by_month', {})
            labels = classification_data.get('labels', {
                'feature': '功能需求', 'bug': 'Bug修复', 
                'question': '社区咨询', 'other': '其他'
            })
            
            categories = [
                {
                    'month': m,
                    'total': data.get('total', 0),
                    'categories': {
                        labels.get('feature', '功能需求'): data.get('feature', 0),
                        labels.get('bug', 'Bug修复'): data.get('bug', 0),
                        labels.get('question', '社区咨询'): data.get('question', 0),
                        labels.get('other', '其他'): data.get('other', 0)
                    }
                }
                for m, data in sorted(by_month.items())
            ]
            
            return jsonify({
                'categories': categories,
                'monthlyKeywords': {}
            })
        
        # 回退到从文本数据计算
        issues_data = data_service.get_aligned_issues(repo_key, month)
        
        # 转换为前端期望的格式
        categories = [
            {
                'month': m,
                'total': data.get('total', 0),
                'categories': data.get('categories', {})
            }
            for m, data in issues_data.get('monthlyData', {}).items()
        ]
        
        monthly_keywords = {
            m: data.get('keywords', [])
            for m, data in issues_data.get('monthlyData', {}).items()
        }
        
        return jsonify({
            'categories': sorted(categories, key=lambda x: x['month']),
            'monthlyKeywords': monthly_keywords
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/analysis/<path:repo_key>', methods=['GET'])
def get_wave_analysis(repo_key):
    """
    波动归因分析
    识别指标的显著变化，并关联对应月份的 Issue 文本
    """
    try:
        # 支持两种格式：owner/repo 或 owner_repo
        if '_' in repo_key and '/' not in repo_key:
            repo_key = repo_key.replace('_', '/')
        
        analysis = data_service.analyze_waves(repo_key)
        return jsonify(analysis)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/keywords/<path:repo_key>/<month>', methods=['GET'])
def get_keywords(repo_key, month):
    """获取指定月份的关键词"""
    try:
        keywords = data_service.get_month_keywords(repo_key, month)
        return jsonify(keywords)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/events/<path:repo_key>', methods=['GET'])
def get_events(repo_key):
    """获取重大事件列表"""
    try:
        events = data_service.get_major_events(repo_key)
        return jsonify(events)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/demo', methods=['GET'])
def get_demo_data():
    """获取演示数据 - 优先使用真实数据"""
    return jsonify(data_service.get_demo_data())


@app.route('/api/metric-groups', methods=['GET'])
def get_metric_groups():
    """获取指标分组配置"""
    return jsonify(data_service.metric_groups)


@app.route('/api/projects', methods=['GET'])
def get_projects():
    """获取所有可用项目列表"""
    try:
        data_dir = os.path.join(os.path.dirname(__file__), 'DataProcessor', 'data')
        if not os.path.exists(data_dir):
            return jsonify({'projects': [], 'default': None})
        
        projects = []
        for item in os.listdir(data_dir):
            item_path = os.path.join(data_dir, item)
            if os.path.isdir(item_path):
                # 检查是否有processed文件夹或monthly_data文件夹
                has_processed = any(
                    ('_processed' in f or 'monthly_data_' in f) and os.path.isdir(os.path.join(item_path, f))
                    for f in os.listdir(item_path)
                )
                if has_processed:
                    summary = qa_agent.get_project_summary(item)
                    if summary and summary.get('exists'):
                        projects.append(summary)
        
        # 默认项目
        default_project = 'X-lab2017_open-digger'
        
        return jsonify({
            'projects': projects,
            'default': default_project
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/projects/search', methods=['GET'])
def search_projects():
    """搜索项目"""
    try:
        query = request.args.get('q', '').strip().lower()
        if not query:
            return jsonify({'projects': []})
        
        data_dir = os.path.join(os.path.dirname(__file__), 'DataProcessor', 'data')
        if not os.path.exists(data_dir):
            return jsonify({'projects': []})
        
        results = []
        for item in os.listdir(data_dir):
            item_path = os.path.join(data_dir, item)
            if os.path.isdir(item_path):
                # 检查是否有processed文件夹或monthly_data文件夹
                has_processed = any(
                    ('_processed' in f or 'monthly_data_' in f) and os.path.isdir(os.path.join(item_path, f))
                    for f in os.listdir(item_path)
                )
                if has_processed:
                    # 简单的名称匹配
                    if query in item.lower():
                        summary = qa_agent.get_project_summary(item)
                        if summary and summary.get('exists'):
                            results.append(summary)
        
        return jsonify({'projects': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/project/<path:project_name>/summary', methods=['GET'])
def get_project_summary(project_name):
    """获取项目摘要"""
    try:
        summary = qa_agent.get_project_summary(project_name)
        return jsonify(summary)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/qa', methods=['POST'])
def ask_question():
    """AI问答接口"""
    try:
        data = request.json
        question = data.get('question', '').strip()
        project_name = data.get('project', '')
        
        if not question:
            return jsonify({'error': '请提供问题'}), 400
        
        if not project_name:
            return jsonify({'error': '请指定项目'}), 400
        
        result = qa_agent.answer_question(question, project_name)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/check_project', methods=['GET'])
def check_project():
    """检查项目数据是否已存在"""
    try:
        owner = request.args.get('owner', '').strip()
        repo = request.args.get('repo', '').strip()
        
        if not owner or not repo:
            return jsonify({'exists': False})
        
        project_name = f"{owner}_{repo}"
        repo_key_variants = [project_name, f"{owner}/{repo}"]
        
        for repo_key in repo_key_variants:
            if repo_key in data_service.loaded_timeseries or repo_key in data_service.loaded_text:
                # 检查是否缺少文本数据（用于知识库）
                has_text = check_project_has_text(project_name)
                return jsonify({
                    'exists': True,
                    'projectName': project_name,
                    'repoKey': repo_key,
                    'hasText': has_text,
                    'needsTextCrawl': not has_text
                })
        
        return jsonify({'exists': False})
    except Exception as e:
        return jsonify({'exists': False, 'error': str(e)})


def check_project_has_text(project_name: str) -> bool:
    """检查项目是否有文本数据（用于知识库）"""
    import os
    data_dir = os.path.join(os.path.dirname(__file__), 'DataProcessor', 'data')
    project_dir = os.path.join(data_dir, project_name)
    
    if not os.path.exists(project_dir):
        return False
    
    # 查找处理后的文件夹
    for folder in os.listdir(project_dir):
        folder_path = os.path.join(project_dir, folder)
        if os.path.isdir(folder_path) and ('monthly_data_' in folder or '_processed' in folder):
            # 检查是否有 text_for_maxkb 文件夹且有内容
            text_dir = os.path.join(folder_path, 'text_for_maxkb')
            if os.path.exists(text_dir):
                # 检查是否有实际文件
                for root, dirs, files in os.walk(text_dir):
                    if files:
                        return True
            # 也检查 project_summary.json
            summary_file = os.path.join(folder_path, 'project_summary.json')
            if os.path.exists(summary_file):
                return True
    
    return False


@app.route('/api/project/<path:project_name>/crawl_text', methods=['POST'])
def crawl_project_text(project_name):
    """为已有项目补爬文本数据（用于知识库）"""
    try:
        # 将 project_name 转换为 owner/repo 格式
        if '_' in project_name and '/' not in project_name:
            parts = project_name.split('_', 1)
            owner, repo = parts[0], parts[1]
        elif '/' in project_name:
            owner, repo = project_name.split('/', 1)
        else:
            return jsonify({'error': '无效的项目名称格式'}), 400
        
        from DataProcessor.github_text_crawler import GitHubTextCrawler
        
        crawler = GitHubTextCrawler()
        
        # 只爬取文本数据
        logger.info(f"[补爬] 开始为 {owner}/{repo} 补爬文本数据...")
        
        text_data = {}
        
        # 获取 README
        readmes = crawler.get_readme(owner, repo)
        if readmes:
            # get_readme 可能返回单个字典或列表，统一转换为列表
            if isinstance(readmes, dict):
                text_data['readme'] = [readmes]
            elif isinstance(readmes, list):
                text_data['readme'] = readmes
            else:
                text_data['readme'] = []
        
        # 获取重要文档
        important_files = crawler.get_important_md_files(owner, repo, max_files=10)
        if important_files:
            # get_important_md_files 返回列表，但确保是列表格式
            if isinstance(important_files, list):
                text_data['docs'] = important_files
            else:
                text_data['docs'] = []
        
        # 保存到项目目录
        if text_data:
            import os
            import json
            from datetime import datetime
            
            data_dir = os.path.join(os.path.dirname(__file__), 'DataProcessor', 'data')
            project_dir = os.path.join(data_dir, project_name)
            
            # 找到或创建处理文件夹
            processed_folder = None
            if os.path.exists(project_dir):
                for folder in os.listdir(project_dir):
                    if 'monthly_data_' in folder or '_processed' in folder:
                        processed_folder = os.path.join(project_dir, folder)
                        break
            
            if not processed_folder:
                # 创建新的处理文件夹
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                processed_folder = os.path.join(project_dir, f'monthly_data_{timestamp}')
                os.makedirs(processed_folder, exist_ok=True)
            
            # 保存文本数据
            text_for_maxkb_dir = os.path.join(processed_folder, 'text_for_maxkb')
            os.makedirs(text_for_maxkb_dir, exist_ok=True)
            
            # 保存 README
            if 'readme' in text_data:
                for readme in text_data['readme']:
                    readme_path = os.path.join(text_for_maxkb_dir, readme.get('name', 'README.md'))
                    with open(readme_path, 'w', encoding='utf-8') as f:
                        f.write(readme.get('content', ''))
            
            # 保存文档
            if 'docs' in text_data:
                docs_dir = os.path.join(text_for_maxkb_dir, 'docs')
                os.makedirs(docs_dir, exist_ok=True)
                for doc in text_data['docs']:
                    doc_name = doc.get('name', 'doc.md')
                    doc_path = os.path.join(docs_dir, doc_name)
                    with open(doc_path, 'w', encoding='utf-8') as f:
                        f.write(doc.get('content', ''))
            
            logger.info(f"[补爬] 完成，保存到 {text_for_maxkb_dir}")
            
            return jsonify({
                'success': True,
                'message': f'成功补爬文本数据',
                'readme_count': len(text_data.get('readme', [])),
                'docs_count': len(text_data.get('docs', []))
            })
        else:
            return jsonify({
                'success': False,
                'message': '未能获取到文本数据'
            })
            
    except Exception as e:
        logger.error(f"[补爬] 失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/predict/<path:repo_key>', methods=['POST'])
def predict_metrics(repo_key):
    """预测指定仓库的时序指标"""
    try:
        # 检查 GitPulse 是否可用
        if not GITPULSE_AVAILABLE:
            return jsonify({
                'error': 'GitPulse 预测功能不可用，请检查后端配置',
                'details': '请安装 GitPulse 依赖: pip install -r GitPulse/requirements_predict.txt'
            }), 503
        
        # 支持两种格式：owner/repo 或 owner_repo
        if '_' in repo_key and '/' not in repo_key:
            repo_key = repo_key.replace('_', '/')
        
        # 检查数据是否存在
        if repo_key not in data_service.loaded_timeseries:
            return jsonify({'error': f'项目 {repo_key} 的时序数据不存在'}), 404
        
        # 获取请求参数
        data = request.json or {}
        metric_name = data.get('metric_name', '').strip()
        forecast_months = data.get('forecast_months', 6)
        include_reasoning = data.get('include_reasoning', True)
        
        # 验证参数
        if forecast_months < 1 or forecast_months > 12:
            return jsonify({'error': '预测月数必须在1-12之间'}), 400
        
        # 获取时序数据（已转换为按指标组织的格式）
        timeseries_data = data_service.loaded_timeseries[repo_key]
        
        # 如果没有指定指标，返回所有可预测的指标列表（只返回 GitPulse 支持的指标）
        if not metric_name:
            available_metrics = []
            if hasattr(predictor, 'supported_metrics'):
                # 只返回 GitPulse 支持的指标
                available_metrics = sorted(list(predictor.supported_metrics))
            elif timeseries_data:
                # 如果没有 supported_metrics，从数据中提取，但只返回支持的指标
                supported_set = {'OpenRank', '活跃度', 'Star数', 'Fork数', '关注度', '参与者数', 
                                '新增贡献者', '贡献者', '不活跃贡献者', '总线因子', '新增Issue', 
                                '关闭Issue', 'Issue评论', '变更请求', 'PR接受数', 'PR审查'}
                for metric_key in timeseries_data.keys():
                    metric_name_clean = metric_key.replace('opendigger_', '')
                    if metric_name_clean in supported_set:
                        available_metrics.append(metric_name_clean)
                available_metrics = sorted(list(set(available_metrics)))
            
            return jsonify({
                'available_metrics': available_metrics,
                'message': '请指定要预测的指标名称',
                'note': 'GitPulse 只支持16个指标，其他指标（如代码变更行数）暂不支持'
            })
        
        # 验证指标是否被 GitPulse 支持
        metric_name_clean = metric_name.replace('opendigger_', '')
        GITPULSE_SUPPORTED_METRICS = {
            'OpenRank', '活跃度', 'Star数', 'Fork数', '关注度', '参与者数',
            '新增贡献者', '贡献者', '不活跃贡献者', '总线因子', '新增Issue',
            '关闭Issue', 'Issue评论', '变更请求', 'PR接受数', 'PR审查'
        }
        if metric_name_clean not in GITPULSE_SUPPORTED_METRICS:
            return jsonify({
                'error': f'指标 "{metric_name}" 不被 GitPulse 模型支持',
                'supported_metrics': sorted(list(GITPULSE_SUPPORTED_METRICS)),
                'hint': f'GitPulse 只支持以下16个指标: {", ".join(sorted(GITPULSE_SUPPORTED_METRICS))}'
            }), 400
        
        # 使用清理后的指标名称
        metric_name = metric_name_clean
        
        # 提取指定指标的历史数据
        historical_data = {}
        
        # 构建指标键名（尝试多种格式）
        metric_keys_to_try = [
            f'opendigger_{metric_name}',  # opendigger_关注度
            metric_name,  # 关注度
            f'opendigger_{metric_name.replace(" ", "")}',  # 去除空格
        ]
        
        # 找到匹配的指标键
        matched_metric_key = None
        for key in metric_keys_to_try:
            if key in timeseries_data:
                matched_metric_key = key
                break
        
        # 如果还没找到，尝试模糊匹配
        if not matched_metric_key:
            for key in timeseries_data.keys():
                # 去掉前缀后比较
                clean_key = key.replace('opendigger_', '')
                if clean_key == metric_name or key.endswith(metric_name):
                    matched_metric_key = key
                    break
        
        if matched_metric_key:
            # 从转换后的格式中提取数据
            metric_data = timeseries_data[matched_metric_key]
            if isinstance(metric_data, dict) and 'raw' in metric_data:
                historical_data = metric_data['raw']
            elif isinstance(metric_data, dict):
                # 如果没有 raw 字段，直接使用
                historical_data = metric_data
        else:
            # 如果还是找不到，返回错误和可用指标列表
            available_metrics = []
            for metric_key in timeseries_data.keys():
                if metric_key.startswith('opendigger_'):
                    available_metrics.append(metric_key.replace('opendigger_', ''))
                else:
                    available_metrics.append(metric_key)
            
            return jsonify({
                'error': f'未找到指标 {metric_name} 的历史数据',
                'available_metrics': available_metrics,
                'hint': f'请使用以下指标名称之一: {", ".join(available_metrics[:10])}'
            }), 404
        
        if not historical_data:
            return jsonify({
                'error': f'未找到指标 {metric_name} 的历史数据',
                'available_metrics': list(timeseries_data.get(sorted(timeseries_data.keys())[0], {}).keys()) if timeseries_data else []
            }), 404
        
        # 获取完整的 16 维时序数据（用于 GitPulse）
        # 注意：timeseries_data 已经是按指标组织的格式，需要从 data_service 获取原始数据
        full_timeseries_data = None
        if hasattr(predictor, 'predict') and 'GitPulse' in str(type(predictor)):
            # 从 data_service 获取所有指标的原始数据（按月份组织）
            all_metrics_data = data_service.get_all_metrics_historical_data(repo_key)
            if all_metrics_data:
                # 构建按月份组织的数据格式
                full_timeseries_data = {}
                # 收集所有月份
                all_months = set()
                for metric_data in all_metrics_data.values():
                    if isinstance(metric_data, dict) and 'raw' in metric_data:
                        all_months.update(metric_data['raw'].keys())
                
                # 为每个月构建指标字典
                for month in sorted(all_months):
                    metrics_dict = {}
                    for metric_key, metric_data in all_metrics_data.items():
                        if isinstance(metric_data, dict) and 'raw' in metric_data:
                            # 注意：使用 clean_metric_name 避免覆盖外部的 metric_name 变量！
                            clean_metric_name = metric_key.replace('opendigger_', '')
                            value = metric_data['raw'].get(month)
                            if value is not None:
                                metrics_dict[clean_metric_name] = value
                    if metrics_dict:
                        full_timeseries_data[month] = metrics_dict
        
        # 获取文本数据（用于 GitPulse）
        text_timeseries = None
        repo_context = None
        if repo_key in data_service.loaded_text:
            text_data = data_service.loaded_text[repo_key]
            # 提取仓库描述
            repo_info_docs = [doc for doc in text_data if doc.get('type') == 'repo_info']
            if repo_info_docs:
                try:
                    repo_info = json.loads(repo_info_docs[0].get('content', '{}'))
                    repo_context = repo_info.get('description', '')
                except:
                    pass
        
        # 执行预测
        result = predictor.predict(
            metric_name=metric_name,
            historical_data=historical_data,
            forecast_months=forecast_months,
            include_reasoning=include_reasoning,
            text_timeseries=text_timeseries,
            repo_context=repo_context,
            full_timeseries_data=full_timeseries_data  # 传递完整数据
        )
        
        # 添加元数据
        result['metric_name'] = metric_name
        result['repo_key'] = repo_key
        result['historical_data_points'] = len(historical_data)
        result['forecast_months'] = forecast_months
        
        return jsonify(result)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/predict/<path:repo_key>/explain', methods=['POST'])
def predict_with_explanation(repo_key):
    """预测并生成归因解释"""
    try:
        if not GITPULSE_AVAILABLE:
            return jsonify({'error': 'GitPulse 预测功能不可用'}), 503
        
        if '_' in repo_key and '/' not in repo_key:
            repo_key = repo_key.replace('_', '/')
        
        if repo_key not in data_service.loaded_timeseries:
            return jsonify({'error': f'项目 {repo_key} 的时序数据不存在'}), 404
        
        data = request.json or {}
        metric_name = data.get('metric_name', '').strip()
        forecast_months = data.get('forecast_months', 6)
        
        if not metric_name:
            return jsonify({'error': '请指定预测指标'}), 400
        
        # 验证指标
        metric_name_clean = metric_name.replace('opendigger_', '')
        GITPULSE_SUPPORTED_METRICS = {
            'OpenRank', '活跃度', 'Star数', 'Fork数', '关注度', '参与者数',
            '新增贡献者', '贡献者', '不活跃贡献者', '总线因子', '新增Issue',
            '关闭Issue', 'Issue评论', '变更请求', 'PR接受数', 'PR审查'
        }
        if metric_name_clean not in GITPULSE_SUPPORTED_METRICS:
            return jsonify({'error': f'指标 "{metric_name}" 不被支持'}), 400
        
        # 获取时序数据
        timeseries_data = data_service.loaded_timeseries[repo_key]
        
        # 提取历史数据
        historical_data = {}
        metric_keys_to_try = [f'opendigger_{metric_name_clean}', metric_name_clean]
        matched_key = None
        for key in metric_keys_to_try:
            if key in timeseries_data:
                matched_key = key
                break
        
        if matched_key:
            metric_data = timeseries_data[matched_key]
            if isinstance(metric_data, dict) and 'raw' in metric_data:
                historical_data = metric_data['raw']
            elif isinstance(metric_data, dict):
                historical_data = metric_data
        
        if not historical_data:
            return jsonify({'error': f'未找到 {metric_name} 的历史数据'}), 404
        
        # 准备完整数据用于GitPulse
        full_timeseries_data = {}
        for month in sorted(historical_data.keys()):
            metrics_dict = {}
            for mk, mv in timeseries_data.items():
                clean_name = mk.replace('opendigger_', '')
                if isinstance(mv, dict) and 'raw' in mv:
                    if month in mv['raw']:
                        metrics_dict[clean_name] = mv['raw'][month]
                elif isinstance(mv, dict) and month in mv:
                    metrics_dict[clean_name] = mv[month]
            if metrics_dict:
                full_timeseries_data[month] = metrics_dict
        
        # 执行预测
        prediction_result = predictor.predict(
            metric_name=metric_name_clean,
            historical_data=historical_data,
            forecast_months=forecast_months,
            include_reasoning=True,
            full_timeseries_data=full_timeseries_data
        )
        
        # 获取仓库上下文
        repo_context = None
        if repo_key in data_service.loaded_text:
            text_data = data_service.loaded_text[repo_key]
            repo_info_docs = [doc for doc in text_data if doc.get('type') == 'repo_info']
            if repo_info_docs:
                try:
                    repo_context = json.loads(repo_info_docs[0].get('content', '{}'))
                except:
                    pass
        
        # 获取Issue统计
        issue_stats = None
        if repo_key in data_service.loaded_text:
            text_data = data_service.loaded_text[repo_key]
            issues = [doc for doc in text_data if doc.get('type') == 'issue']
            issue_stats = {
                'bug': len([i for i in issues if 'bug' in i.get('content', '').lower()]),
                'feature': len([i for i in issues if 'feature' in i.get('content', '').lower()]),
                'other': len(issues)
            }
        
        # 生成归因解释
        explanation = prediction_explainer.generate_explanation(
            metric_name=metric_name_clean,
            historical_data=historical_data,
            forecast_data=prediction_result.get('forecast', {}),
            confidence=prediction_result.get('confidence', 0.5),
            repo_context=repo_context,
            issue_stats=issue_stats
        )
        
        return jsonify({
            'prediction': prediction_result,
            'explanation': explanation,
            'metric_name': metric_name_clean,
            'repo_key': repo_key
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/predict/<path:repo_key>/scenario', methods=['POST'])
def predict_scenario(repo_key):
    """场景模拟预测 - 支持用户调整假设参数"""
    try:
        if not GITPULSE_AVAILABLE:
            return jsonify({'error': 'GitPulse 预测功能不可用'}), 503
        
        if '_' in repo_key and '/' not in repo_key:
            repo_key = repo_key.replace('_', '/')
        
        if repo_key not in data_service.loaded_timeseries:
            return jsonify({'error': f'项目 {repo_key} 的时序数据不存在'}), 404
        
        data = request.json or {}
        metric_name = data.get('metric_name', '').strip()
        forecast_months = data.get('forecast_months', 6)
        scenario_params = data.get('scenario_params', {})
        
        if not metric_name:
            return jsonify({'error': '请指定预测指标'}), 400
        
        # 验证指标
        metric_name_clean = metric_name.replace('opendigger_', '')
        GITPULSE_SUPPORTED_METRICS = {
            'OpenRank', '活跃度', 'Star数', 'Fork数', '关注度', '参与者数',
            '新增贡献者', '贡献者', '不活跃贡献者', '总线因子', '新增Issue',
            '关闭Issue', 'Issue评论', '变更请求', 'PR接受数', 'PR审查'
        }
        if metric_name_clean not in GITPULSE_SUPPORTED_METRICS:
            return jsonify({'error': f'指标 "{metric_name}" 不被支持'}), 400
        
        # 获取时序数据
        timeseries_data = data_service.loaded_timeseries[repo_key]
        
        # 提取历史数据
        historical_data = {}
        metric_keys_to_try = [f'opendigger_{metric_name_clean}', metric_name_clean]
        matched_key = None
        for key in metric_keys_to_try:
            if key in timeseries_data:
                matched_key = key
                break
        
        if matched_key:
            metric_data = timeseries_data[matched_key]
            if isinstance(metric_data, dict) and 'raw' in metric_data:
                historical_data = metric_data['raw']
            elif isinstance(metric_data, dict):
                historical_data = metric_data
        
        if not historical_data:
            return jsonify({'error': f'未找到 {metric_name} 的历史数据'}), 404
        
        # 准备完整数据
        full_timeseries_data = {}
        for month in sorted(historical_data.keys()):
            metrics_dict = {}
            for mk, mv in timeseries_data.items():
                clean_name = mk.replace('opendigger_', '')
                if isinstance(mv, dict) and 'raw' in mv:
                    if month in mv['raw']:
                        metrics_dict[clean_name] = mv['raw'][month]
                elif isinstance(mv, dict) and month in mv:
                    metrics_dict[clean_name] = mv[month]
            if metrics_dict:
                full_timeseries_data[month] = metrics_dict
        
        # 执行基线预测
        baseline_result = predictor.predict(
            metric_name=metric_name_clean,
            historical_data=historical_data,
            forecast_months=forecast_months,
            include_reasoning=True,
            full_timeseries_data=full_timeseries_data
        )
        
        # 获取仓库上下文
        repo_context = None
        if repo_key in data_service.loaded_text:
            text_data = data_service.loaded_text[repo_key]
            repo_info_docs = [doc for doc in text_data if doc.get('type') == 'repo_info']
            if repo_info_docs:
                try:
                    repo_context = json.loads(repo_info_docs[0].get('content', '{}'))
                except:
                    pass
        
        # 生成场景分析
        scenario_result = prediction_explainer.generate_scenario_analysis(
            metric_name=metric_name_clean,
            historical_data=historical_data,
            baseline_forecast=baseline_result.get('forecast', {}),
            scenario_params=scenario_params,
            repo_context=repo_context
        )
        
        return jsonify({
            'baseline': baseline_result,
            'scenario': scenario_result,
            'metric_name': metric_name_clean,
            'repo_key': repo_key,
            'scenario_params': scenario_params
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/predict/<path:repo_key>/multi-metric', methods=['POST'])
def predict_multi_metric(repo_key):
    """多指标联动预测 - 同时预测多个指标并返回对比数据"""
    try:
        if not GITPULSE_AVAILABLE:
            return jsonify({'error': 'GitPulse 预测功能不可用'}), 503
        
        if '_' in repo_key and '/' not in repo_key:
            repo_key = repo_key.replace('_', '/')
        
        if repo_key not in data_service.loaded_timeseries:
            return jsonify({'error': f'项目 {repo_key} 的时序数据不存在'}), 404
        
        data = request.json or {}
        metric_names = data.get('metric_names', [])
        forecast_months = data.get('forecast_months', 6)
        
        if not metric_names or len(metric_names) < 1:
            return jsonify({'error': '请至少选择一个预测指标'}), 400
        
        if len(metric_names) > 4:
            return jsonify({'error': '最多支持同时预测4个指标'}), 400
        
        GITPULSE_SUPPORTED_METRICS = {
            'OpenRank', '活跃度', 'Star数', 'Fork数', '关注度', '参与者数',
            '新增贡献者', '贡献者', '不活跃贡献者', '总线因子', '新增Issue',
            '关闭Issue', 'Issue评论', '变更请求', 'PR接受数', 'PR审查'
        }
        
        # 获取时序数据
        timeseries_data = data_service.loaded_timeseries[repo_key]
        
        # 准备完整数据
        full_timeseries_data = {}
        for mk, mv in timeseries_data.items():
            if isinstance(mv, dict) and 'raw' in mv:
                for month, value in mv['raw'].items():
                    if month not in full_timeseries_data:
                        full_timeseries_data[month] = {}
                    clean_name = mk.replace('opendigger_', '')
                    full_timeseries_data[month][clean_name] = value
        
        results = {}
        
        for metric_name in metric_names:
            metric_name_clean = metric_name.replace('opendigger_', '')
            
            if metric_name_clean not in GITPULSE_SUPPORTED_METRICS:
                results[metric_name_clean] = {'error': f'指标不被支持'}
                continue
            
            # 提取历史数据
            historical_data = {}
            metric_keys_to_try = [f'opendigger_{metric_name_clean}', metric_name_clean]
            for key in metric_keys_to_try:
                if key in timeseries_data:
                    metric_data = timeseries_data[key]
                    if isinstance(metric_data, dict) and 'raw' in metric_data:
                        historical_data = metric_data['raw']
                    elif isinstance(metric_data, dict):
                        historical_data = metric_data
                    break
            
            if not historical_data:
                results[metric_name_clean] = {'error': '未找到历史数据'}
                continue
            
            # 执行预测
            prediction = predictor.predict(
                metric_name=metric_name_clean,
                historical_data=historical_data,
                forecast_months=forecast_months,
                include_reasoning=False,
                full_timeseries_data=full_timeseries_data
            )
            
            results[metric_name_clean] = {
                'historical': historical_data,
                'forecast': prediction.get('forecast', {}),
                'confidence': prediction.get('confidence', 0),
                'trend': prediction.get('trend_analysis', {})
            }
        
        return jsonify({
            'results': results,
            'repo_key': repo_key,
            'forecast_months': forecast_months
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/analysis/trend/<path:repo_key>', methods=['GET'])
def get_trend_analysis(repo_key):
    """获取趋势分析"""
    try:
        if '_' in repo_key and '/' not in repo_key:
            repo_key = repo_key.replace('_', '/')
        
        if repo_key not in data_service.loaded_timeseries:
            return jsonify({'error': f'项目 {repo_key} 的时序数据不存在'}), 404
        
        timeseries_data = data_service.loaded_timeseries[repo_key]
        trends = {}
        
        for metric_key, metric_data in timeseries_data.items():
            if isinstance(metric_data, dict) and 'raw' in metric_data:
                raw_data = metric_data['raw']
                if not raw_data:
                    continue
                
                metric_name = metric_key.replace('opendigger_', '')
                sorted_months = sorted(raw_data.keys())
                if len(sorted_months) < 2:
                    continue
                
                values = [raw_data[month] for month in sorted_months if raw_data[month] is not None]
                if len(values) < 2:
                    continue
                
                first_half = values[:len(values)//2]
                second_half = values[len(values)//2:]
                first_avg = sum(first_half) / len(first_half) if first_half else 0
                second_avg = sum(second_half) / len(second_half) if second_half else 0
                
                growth_rate = ((second_avg - first_avg) / first_avg * 100) if first_avg > 0 else 0
                
                mean_val = sum(values) / len(values)
                variance = sum((v - mean_val) ** 2 for v in values) / len(values)
                std_dev = variance ** 0.5
                cv = std_dev / mean_val if mean_val > 0 else 0
                
                direction = '上升' if growth_rate > 10 else ('下降' if growth_rate < -10 else '稳定')
                
                trends[metric_name] = {
                    'direction': direction,
                    'growth_rate': round(growth_rate, 2),
                    'volatility': '高' if cv > 0.3 else ('中' if cv > 0.15 else '低'),
                    'coefficient_of_variation': round(cv, 3),
                    'first_half_avg': round(first_avg, 2),
                    'second_half_avg': round(second_avg, 2),
                    'current_value': values[-1] if values else 0,
                    'data_points': len(values)
                }
        
        return jsonify({'repo_key': repo_key, 'trends': trends, 'total_metrics': len(trends)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/analysis/comparison/<path:repo_key>', methods=['GET'])
def get_comparison_analysis(repo_key):
    """获取对比分析"""
    try:
        if '_' in repo_key and '/' not in repo_key:
            repo_key = repo_key.replace('_', '/')
        
        if repo_key not in data_service.loaded_timeseries:
            return jsonify({'error': f'项目 {repo_key} 的时序数据不存在'}), 404
        
        all_repos = data_service.get_loaded_repos()
        current_timeseries = data_service.loaded_timeseries[repo_key]
        
        current_metrics = {}
        for metric_key, metric_data in current_timeseries.items():
            if isinstance(metric_data, dict) and 'raw' in metric_data:
                raw_data = metric_data['raw']
                values = [v for v in raw_data.values() if v is not None]
                if values:
                    metric_name = metric_key.replace('opendigger_', '')
                    current_metrics[metric_name] = {
                        'avg': sum(values) / len(values),
                        'max': max(values),
                        'min': min(values),
                        'current': values[-1] if values else 0
                    }
        
        other_repos_metrics = {}
        for other_repo in all_repos:
            if other_repo == repo_key:
                continue
            if other_repo in data_service.loaded_timeseries:
                other_timeseries = data_service.loaded_timeseries[other_repo]
                for metric_key, metric_data in other_timeseries.items():
                    if isinstance(metric_data, dict) and 'raw' in metric_data:
                        raw_data = metric_data['raw']
                        values = [v for v in raw_data.values() if v is not None]
                        if values:
                            metric_name = metric_key.replace('opendigger_', '')
                            if metric_name not in other_repos_metrics:
                                other_repos_metrics[metric_name] = []
                            other_repos_metrics[metric_name].append(sum(values) / len(values))
        
        comparison = {}
        for metric_name, current_data in current_metrics.items():
            if metric_name in other_repos_metrics:
                other_avgs = other_repos_metrics[metric_name]
                if other_avgs:
                    benchmark_avg = sum(other_avgs) / len(other_avgs)
                    current_avg = current_data['avg']
                    relative_performance = ((current_avg - benchmark_avg) / benchmark_avg * 100) if benchmark_avg > 0 else 0
                    
                    comparison[metric_name] = {
                        'current_avg': round(current_avg, 2),
                        'benchmark_avg': round(benchmark_avg, 2),
                        'relative_performance': round(relative_performance, 2),
                        'performance_level': '高于平均' if relative_performance > 10 else ('低于平均' if relative_performance < -10 else '接近平均'),
                        'current_value': current_data['current'],
                        'max': current_data['max'],
                        'min': current_data['min']
                    }
        
        return jsonify({
            'repo_key': repo_key,
            'comparison': comparison,
            'compared_with': len(all_repos) - 1,
            'total_metrics': len(comparison)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/predict/<path:repo_key>/multiple', methods=['POST'])
def predict_multiple_metrics(repo_key):
    """批量预测多个指标"""
    try:
        # 检查 GitPulse 是否可用
        if not GITPULSE_AVAILABLE:
            return jsonify({'error': 'GitPulse 预测功能不可用'}), 503
        
        # 支持两种格式：owner/repo 或 owner_repo
        if '_' in repo_key and '/' not in repo_key:
            repo_key = repo_key.replace('_', '/')
        
        # 检查数据是否存在
        if repo_key not in data_service.loaded_timeseries:
            return jsonify({'error': f'项目 {repo_key} 的时序数据不存在'}), 404
        
        # 获取请求参数
        data = request.json or {}
        metric_names = data.get('metric_names', [])
        forecast_months = data.get('forecast_months', 6)
        
        if not metric_names:
            return jsonify({'error': '请提供要预测的指标列表'}), 400
        
        # GitPulse 支持的16个指标
        GITPULSE_SUPPORTED_METRICS = {
            'OpenRank', '活跃度', 'Star数', 'Fork数', '关注度', '参与者数',
            '新增贡献者', '贡献者', '不活跃贡献者', '总线因子', '新增Issue',
            '关闭Issue', 'Issue评论', '变更请求', 'PR接受数', 'PR审查'
        }
        
        # 过滤掉不支持的指标
        supported_metric_names = []
        unsupported_metric_names = []
        for metric_name in metric_names:
            metric_name_clean = metric_name.replace('opendigger_', '')
            if metric_name_clean in GITPULSE_SUPPORTED_METRICS:
                supported_metric_names.append(metric_name_clean)
            else:
                unsupported_metric_names.append(metric_name)
        
        if not supported_metric_names:
            return jsonify({
                'error': '没有支持的指标可以预测',
                'unsupported_metrics': unsupported_metric_names,
                'supported_metrics': sorted(list(GITPULSE_SUPPORTED_METRICS)),
                'hint': f'GitPulse 只支持以下16个指标: {", ".join(sorted(GITPULSE_SUPPORTED_METRICS))}'
            }), 400
        
        # 获取时序数据
        timeseries_data = data_service.loaded_timeseries[repo_key]
        
        # 提取所有指标的历史数据（只处理支持的指标）
        metrics_data = {}
        for metric_name in supported_metric_names:
            # 构建指标键名（尝试多种格式）
            metric_keys_to_try = [
                f'opendigger_{metric_name}',
                metric_name,
                f'opendigger_{metric_name.replace(" ", "")}',
            ]
            
            matched_metric_key = None
            for key in metric_keys_to_try:
                if key in timeseries_data:
                    matched_metric_key = key
                    break
            
            if not matched_metric_key:
                for key in timeseries_data.keys():
                    clean_key = key.replace('opendigger_', '')
                    if clean_key == metric_name or key.endswith(metric_name):
                        matched_metric_key = key
                        break
            
            if matched_metric_key:
                metric_data = timeseries_data[matched_metric_key]
                if isinstance(metric_data, dict) and 'raw' in metric_data:
                    historical_data = metric_data['raw']
                elif isinstance(metric_data, dict):
                    historical_data = metric_data
                else:
                    historical_data = {}
                
                if historical_data:
                    metrics_data[metric_name] = historical_data
        
        if not metrics_data:
            return jsonify({'error': '未找到任何指标的历史数据'}), 404
        
        # 批量预测
        results = predictor.predict_multiple(metrics_data, forecast_months)
        
        # 如果有不支持的指标，在响应中说明
        response_data = {
            'results': results,
            'repo_key': repo_key,
            'forecast_months': forecast_months
        }
        
        if unsupported_metric_names:
            response_data['warnings'] = {
                'unsupported_metrics': unsupported_metric_names,
                'message': f'以下指标不被 GitPulse 支持，已自动过滤: {", ".join(unsupported_metric_names)}'
            }
        
        return jsonify(response_data)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/chaoss/<path:repo_key>', methods=['GET'])
def get_chaoss_evaluation(repo_key):
    """获取 CHAOSS 社区评价"""
    try:
        # 支持两种格式：owner/repo 或 owner_repo
        if '_' in repo_key and '/' not in repo_key:
            repo_key = repo_key.replace('_', '/')
        
        result = chaoss_evaluator.evaluate_repo(repo_key)
        
        if 'error' in result:
            return jsonify(result), 404
        
        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"CHAOSS评估错误: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/chaoss/<path:repo_key>/dimensions', methods=['GET'])
def get_chaoss_dimensions(repo_key):
    """获取 CHAOSS 维度映射信息"""
    try:
        dimensions = chaoss_evaluator.get_dimension_mapping()
        return jsonify(dimensions)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/crawl', methods=['GET', 'POST'])
def crawl_repository():
    """爬取GitHub仓库并返回实时进度（SSE）- 使用新的月度爬取流程"""
    from flask import Response, stream_with_context
    
    try:
        if request.method == 'GET':
            owner = request.args.get('owner', '').strip()
            repo = request.args.get('repo', '').strip()
            max_per_month = int(request.args.get('max_per_month', '50'))
        else:
            data = request.json or {}
            owner = data.get('owner', '').strip()
            repo = data.get('repo', '').strip()
            max_per_month = data.get('max_per_month', 50)
        
        if not owner or not repo:
            return jsonify({'error': '请提供仓库所有者和仓库名'}), 400
        
        def generate():
            import sys
            import threading
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'DataProcessor'))
            from github_text_crawler import OpenDiggerMetrics
            from crawl_monthly_data import crawl_project_monthly
            
            try:
                yield f"data: {json.dumps({'type': 'start', 'message': '开始爬取仓库数据（渐进式加载）...'})}\n\n"
                
                # ========== 步骤1: 快速获取指标数据（立即返回给前端）==========
                yield f"data: {json.dumps({'type': 'progress', 'step': 1, 'stepName': '步骤1: 获取指标数据', 'message': '正在快速获取OpenDigger数字指标和仓库信息...', 'progress': 5})}\n\n"
                
                # 初始化爬虫（用于获取仓库信息和标签）
                import sys
                sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'DataProcessor'))
                from github_text_crawler import GitHubTextCrawler
                text_crawler = GitHubTextCrawler()
                
                # 获取仓库信息和标签（用于面板展示）
                repo_info = text_crawler.get_repo_info(owner, repo)
                labels = text_crawler.get_labels(owner, repo)
                
                # 获取OpenDigger指标数据
                opendigger = OpenDiggerMetrics()
                opendigger_data, missing_metrics = opendigger.get_metrics(owner, repo)
                
                # 临时保存指标数据到内存，供前端立即使用
                repo_key = f"{owner}/{repo}"
                project_name = f"{owner}_{repo}"
                
                # 保存仓库信息到 data_service（用于前端展示）
                if repo_info:
                    # 将仓库信息保存为文本数据格式，供前端获取
                    repo_info_doc = {
                        'type': 'repo_info',
                        'content': json.dumps({
                            'name': repo_info.get('name', ''),
                            'full_name': repo_info.get('full_name', ''),
                            'description': repo_info.get('description', ''),
                            'homepage': repo_info.get('homepage', ''),
                            'language': repo_info.get('language', ''),
                            'stars': repo_info.get('stars', 0),
                            'forks': repo_info.get('forks', 0),
                            'watchers': repo_info.get('watchers', 0),
                            'open_issues': repo_info.get('open_issues', 0),
                            'created_at': repo_info.get('created_at', ''),
                            'updated_at': repo_info.get('updated_at', ''),
                            'license': repo_info.get('license', ''),
                            'topics': repo_info.get('topics', []),
                            'labels': labels if labels else []
                        }, ensure_ascii=False)
                    }
                    
                    # 初始化文本数据字典（如果不存在）
                    if repo_key not in data_service.loaded_text:
                        data_service.loaded_text[repo_key] = []
                    if project_name not in data_service.loaded_text:
                        data_service.loaded_text[project_name] = []
                    
                    # 添加仓库信息（去重）
                    if not any(doc.get('type') == 'repo_info' for doc in data_service.loaded_text[repo_key]):
                        data_service.loaded_text[repo_key].append(repo_info_doc)
                        data_service.loaded_text[project_name].append(repo_info_doc)
                
                # 将OpenDigger数据转换为data_service期望的格式
                # 定义所有19个指标，确保即使缺失也用0填充（用于模型训练）
                all_metrics = {
                    'OpenRank': 'openrank',
                    '活跃度': 'activity',
                    'Star数': 'stars',
                    'Fork数': 'technical_fork',
                    '关注度': 'attention',
                    '参与者数': 'participants',
                    '新增贡献者': 'new_contributors',
                    '贡献者': 'contributors',
                    '不活跃贡献者': 'inactive_contributors',
                    '总线因子': 'bus_factor',
                    '新增Issue': 'issues_new',
                    '关闭Issue': 'issues_closed',
                    'Issue评论': 'issue_comments',
                    '变更请求': 'change_requests',
                    'PR接受数': 'change_requests_accepted',
                    'PR审查': 'change_requests_reviews',
                    '代码新增行数': 'code_change_lines_add',
                    '代码删除行数': 'code_change_lines_remove',
                    '代码变更总行数': 'code_change_lines_sum',
                }
                
                temp_timeseries = {}
                # 提取时间范围（从有数据的指标中提取）
                all_months = set()
                for metric_name, metric_data in opendigger_data.items():
                    if isinstance(metric_data, dict):
                        all_months.update(metric_data.keys())
                
                # 为所有指标创建数据，缺失的用0填充
                for metric_display_name, metric_key in all_metrics.items():
                    metric_key_full = f'opendigger_{metric_display_name}'
                    raw_data = {}
                    
                    # 如果OpenDigger有该指标的数据，使用实际数据
                    if metric_display_name in opendigger_data:
                        metric_data = opendigger_data[metric_display_name]
                        if isinstance(metric_data, dict):
                            for date_str, value in metric_data.items():
                                if len(date_str) >= 7:
                                    month_str = date_str[:7]
                                    raw_data[month_str] = value
                    
                    # 为所有月份填充数据（有数据的用实际值，没有的用0）
                    for month in sorted(all_months):
                        if len(month) >= 7:
                            month_str = month[:7]
                            if month_str not in raw_data:
                                raw_data[month_str] = 0.0
                    
                    # 保存指标数据（即使全部是0也保存，用于模型训练）
                    temp_timeseries[metric_key_full] = {
                        'raw': raw_data
                    }
                
                # 临时加载到数据服务中（仅指标数据）
                if temp_timeseries:
                    data_service.loaded_timeseries[repo_key] = temp_timeseries
                    data_service.loaded_timeseries[project_name] = temp_timeseries
                    
                    # 通知前端：指标数据已就绪，可以开始展示
                    yield f"data: {json.dumps({'type': 'metrics_ready', 'message': '指标数据已就绪，前端可以开始展示！', 'projectName': project_name, 'repoKey': repo_key, 'metricsCount': len(temp_timeseries), 'progress': 20})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'progress', 'step': 1, 'stepName': '步骤1: 获取指标数据', 'message': '未获取到指标数据，继续完整爬取...', 'progress': 10})}\n\n"
                
                # 在后台线程中继续爬取（但SSE需要在主线程中yield）
                # 由于SSE的限制，我们需要在主线程中顺序执行，但可以快速返回指标数据
                
                # ========== 步骤2-4: 后台继续爬取其他数据 ==========
                # 步骤2: 爬取描述文本并上传到MaxKB
                yield f"data: {json.dumps({'type': 'progress', 'step': 2, 'stepName': '步骤2: 爬取描述文本', 'message': '正在获取README、LICENSE、文档等并上传到MaxKB...', 'progress': 30})}\n\n"
                
                # 步骤3: 爬取时序文本
                yield f"data: {json.dumps({'type': 'progress', 'step': 3, 'stepName': '步骤3: 爬取时序文本', 'message': '正在爬取Issue/PR/Commit/Release...', 'progress': 50})}\n\n"
                
                # 步骤4: 时序对齐
                yield f"data: {json.dumps({'type': 'progress', 'step': 4, 'stepName': '步骤4: 时序对齐', 'message': '正在合并时序文本和时序指标...', 'progress': 80})}\n\n"
                
                # 使用新的月度爬取流程（在try-except中执行，确保错误能被捕获）
                try:
                    output_dir = crawl_project_monthly(
                        owner=owner,
                        repo=repo,
                        max_per_month=max_per_month,
                        enable_llm_summary=True
                    )
                except Exception as crawl_error:
                    import traceback
                    error_msg = str(crawl_error)
                    traceback.print_exc()
                    yield f"data: {json.dumps({'type': 'error', 'message': f'爬取过程出错: {error_msg}'})}\n\n"
                    return
                
                yield f"data: {json.dumps({'type': 'progress', 'step': 5, 'stepName': '加载完整数据', 'message': '正在加载完整数据到服务...', 'progress': 95})}\n\n"
                data_service._auto_load_data()
                
                yield f"data: {json.dumps({'type': 'complete', 'message': '所有数据爬取和处理完成！', 'projectName': project_name, 'outputDir': output_dir, 'progress': 100})}\n\n"
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                yield f"data: {json.dumps({'type': 'error', 'message': f'发生错误: {str(e)}'})}\n\n"
        
        response = Response(stream_with_context(generate()), mimetype='text/event-stream')
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['X-Accel-Buffering'] = 'no'
        response.headers['Connection'] = 'keep-alive'
        response.headers['X-Accel-Buffering'] = 'no'
        # 设置较长的超时时间（10分钟）
        response.timeout = 600
        return response
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("\n" + "="*60)
    print("  ___                   __     ___     _        ")
    print(" / _ \\ _ __   ___ _ __  \\ \\   / (_)___| |_ __ _ ")
    print("| | | | '_ \\ / _ \\ '_ \\  \\ \\ / /| / __| __/ _` |")
    print("| |_| | |_) |  __/ | | |  \\ V / | \\__ \\ || (_| |")
    print(" \\___/| .__/ \\___|_| |_|   \\_/  |_|___/\\__\\__,_|")
    print("      |_|   GitHub 仓库生态画像分析平台          ")
    print("="*60)
    
    logger.info("=" * 50)
    logger.info("OpenVista 后端服务启动中...")
    logger.info("=" * 50)
    
    # 显示环境配置
    logger.info("[环境配置]")
    logger.info(f"  Python 版本: {sys.version.split()[0]}")
    logger.info(f"  工作目录: {os.getcwd()}")
    logger.info(f"  数据目录: {os.path.join(os.path.dirname(__file__), 'DataProcessor', 'data')}")
    
    # 检查环境变量配置
    has_maxkb = bool(os.getenv('MAXKB_AI_API'))
    has_deepseek = bool(os.getenv('DEEPSEEK_API_KEY') or os.getenv('DEEPSEEK_KEY'))
    has_github = bool(os.getenv('GITHUB_TOKEN'))
    
    logger.info("[API 配置]")
    logger.info(f"  MAXKB_AI_API: {'已配置 ✓' if has_maxkb else '未配置'}")
    logger.info(f"  DEEPSEEK_API_KEY: {'已配置 ✓' if has_deepseek else '未配置'}")
    logger.info(f"  GITHUB_TOKEN: {'已配置 ✓' if has_github else '未配置'}")
    
    # 显示 GitPulse 状态
    logger.info("[GitPulse 预测器]")
    if GITPULSE_AVAILABLE and predictor:
        try:
            logger.info(f"  状态: 已初始化 ✓")
            logger.info(f"  设备: {predictor.device}")
            logger.info(f"  模型: {predictor.predictor.__class__.__name__}")
            logger.info(f"  支持指标: {len(predictor.supported_metrics)} 个")
        except Exception as e:
            logger.error(f"  状态检查失败: {e}")
    else:
        logger.warning(f"  状态: 不可用 ✗")
        logger.warning(f"  请安装依赖: pip install -r GitPulse/requirements_predict.txt")
    
    # 显示 AI Agent 状态
    logger.info("[AI Agent]")
    try:
        ai_type = qa_agent.ai_type or '规则匹配'
        ai_status = '已启用 ✓' if qa_agent.use_ai else '未启用'
        logger.info(f"  类型: {ai_type}")
        logger.info(f"  状态: {ai_status}")
    except Exception as e:
        logger.warning(f"  状态检查失败: {e}")
    
    # 显示已加载的数据
    repos = data_service.get_loaded_repos()
    logger.info("[数据加载]")
    if repos:
        logger.info(f"  已加载 {len(repos)} 个仓库:")
        for repo in repos[:10]:  # 最多显示10个
            summary = data_service.get_repo_summary(repo)
            time_range = summary.get('timeRange', {})
            logger.info(f"    - {repo}: {time_range.get('start', '?')} ~ {time_range.get('end', '?')} ({time_range.get('months', 0)} 个月)")
        if len(repos) > 10:
            logger.info(f"    ... 还有 {len(repos) - 10} 个仓库")
    else:
        logger.warning("  未找到已处理的数据")
        logger.warning("  请将处理后的数据放入 backend/DataProcessor/data 目录")
        logger.warning("  或使用前端爬取功能获取数据")
    
    logger.info("=" * 50)
    logger.info("服务启动完成!")
    logger.info("=" * 50)
    
    print("\n" + "="*60)
    print("服务地址: http://0.0.0.0:5000")
    print("日志文件: backend/logs/openvista.log")
    print("="*60 + "\n")
    
    app.run(debug=True, port=5000, host='0.0.0.0')
