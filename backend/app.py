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
# 预测服务将在首次调用时延迟初始化
GITPULSE_AVAILABLE = False
_gitpulse_service = None

def get_gitpulse_service():
    """获取 GitPulse 预测服务（延迟初始化）"""
    global _gitpulse_service, GITPULSE_AVAILABLE
    if _gitpulse_service is None:
        try:
            from GitPulse.prediction_service import get_prediction_service
            _gitpulse_service = get_prediction_service()
            GITPULSE_AVAILABLE = _gitpulse_service.is_available()
            if GITPULSE_AVAILABLE:
                logger.info("GitPulse 预测服务初始化成功")
            else:
                logger.warning(f"GitPulse 预测服务不可用: {_gitpulse_service.get_error()}")
        except Exception as e:
            logger.warning(f"GitPulse 初始化失败: {e}")
            GITPULSE_AVAILABLE = False
    return _gitpulse_service

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

# CHAOSS 评估器实例
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


@app.route('/api/repo/<path:repo_key>/live-stats', methods=['GET'])
def get_live_stats(repo_key):
    """
    使用 GitHub Token 获取仓库的实时统计数据
    当 OpenDigger 数据延迟时，作为补充数据源
    返回: stars, commits, prs, contributors (当月)
    """
    try:
        # 标准化 repo_key
        if '_' in repo_key and '/' not in repo_key:
            parts = repo_key.split('_', 1)
            owner, repo = parts[0], parts[1]
        else:
            parts = repo_key.split('/')
            owner, repo = parts[0], parts[1]
        
        from DataProcessor.github_api_metrics import GitHubAPIMetrics
        from datetime import datetime
        import requests
        import os
        
        # 获取 Token
        token = os.getenv('GITHUB_TOKEN')
        if not token:
            return jsonify({'error': 'GitHub Token 未配置', 'stats': None}), 400
        
        headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        base_url = 'https://api.github.com'
        current_month = datetime.now().strftime('%Y-%m')
        
        stats = {
            'month': current_month,
            'stars': 0,
            'commits': 0,
            'prs': 0,
            'contributors': 0,
            'source': 'github_api'
        }
        
        # 1. 获取仓库基本信息 (stars, forks)
        try:
            repo_response = requests.get(
                f'{base_url}/repos/{owner}/{repo}',
                headers=headers, timeout=10
            )
            if repo_response.status_code == 200:
                repo_data = repo_response.json()
                stats['stars'] = repo_data.get('stargazers_count', 0)
                stats['forks'] = repo_data.get('forks_count', 0)
        except Exception as e:
            logger.warning(f"获取仓库信息失败: {e}")
        
        # 2. 获取当月提交数
        try:
            since_date = f"{current_month}-01T00:00:00Z"
            commits_response = requests.get(
                f'{base_url}/repos/{owner}/{repo}/commits',
                headers=headers,
                params={'since': since_date, 'per_page': 100},
                timeout=15
            )
            if commits_response.status_code == 200:
                commits = commits_response.json()
                stats['commits'] = len(commits)
                
                # 统计当月贡献者
                contributors_set = set()
                for commit in commits:
                    author = commit.get('author')
                    if author and author.get('login'):
                        contributors_set.add(author['login'])
                stats['contributors'] = len(contributors_set)
        except Exception as e:
            logger.warning(f"获取提交信息失败: {e}")
        
        # 3. 获取当月合并的 PR 数
        try:
            prs_response = requests.get(
                f'{base_url}/repos/{owner}/{repo}/pulls',
                headers=headers,
                params={'state': 'closed', 'sort': 'updated', 'direction': 'desc', 'per_page': 100},
                timeout=15
            )
            if prs_response.status_code == 200:
                prs = prs_response.json()
                merged_count = 0
                for pr in prs:
                    merged_at = pr.get('merged_at')
                    if merged_at and merged_at.startswith(current_month):
                        merged_count += 1
                stats['prs'] = merged_count
        except Exception as e:
            logger.warning(f"获取 PR 信息失败: {e}")
        
        logger.info(f"[Live Stats] {owner}/{repo} - Stars: {stats['stars']}, Commits: {stats['commits']}, PRs: {stats['prs']}, Contributors: {stats['contributors']}")
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'stats': None}), 500


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


# 预测服务缓存
_prediction_cache = {}

@app.route('/api/forecast/<path:repo_key>', methods=['GET'])
def get_forecast(repo_key):
    """
    获取预测数据
    使用 GitPulse 模型从 timeseries_for_model 目录预测
    """
    global _prediction_cache
    
    try:
        from GitPulse.prediction_service import get_prediction_service
        
        # 支持两种格式
        if '_' in repo_key and '/' not in repo_key:
            repo_key = repo_key.replace('_', '/')
        
        project_key = repo_key.replace('/', '_')
        forecast_months = int(request.args.get('months', 12))
        
        # 检查缓存
        cache_key = f"{project_key}_{forecast_months}"
        if cache_key in _prediction_cache:
            print(f"[CACHE] 使用缓存的预测结果: {cache_key}")
            return jsonify(_prediction_cache[cache_key])
        
        # 查找 timeseries_for_model 目录
        data_dir = os.path.join(os.path.dirname(__file__), 'DataProcessor', 'data', project_key)
        if not os.path.exists(data_dir):
            return jsonify({'error': f'项目 {repo_key} 不存在', 'available': False}), 404
        
        # 查找最新的 monthly_data 目录
        monthly_dirs = [d for d in os.listdir(data_dir) if d.startswith('monthly_data_')]
        if not monthly_dirs:
            return jsonify({'error': '未找到月度数据', 'available': False}), 404
        
        latest_dir = sorted(monthly_dirs)[-1]
        timeseries_dir = os.path.join(data_dir, latest_dir, 'timeseries_for_model')
        
        if not os.path.exists(timeseries_dir):
            return jsonify({'error': '未找到时序数据', 'available': False}), 404
        
        # 获取预测服务
        prediction_service = get_prediction_service()
        
        if not prediction_service.is_available():
            return jsonify({
                'error': prediction_service.get_error() or 'GitPulse 预测服务不可用',
                'available': False,
                'hint': '请安装依赖: pip install -r GitPulse/requirements.txt'
            }), 503
        
        # 获取仓库信息
        repo_info = None
        if repo_key in data_service.loaded_text:
            for doc in data_service.loaded_text[repo_key]:
                if doc.get('type') == 'repo_info':
                    try:
                        repo_info = json.loads(doc.get('content', '{}'))
                    except:
                        pass
                    break
        
        # 执行预测
        result = prediction_service.predict(
            timeseries_dir,
            forecast_months=forecast_months,
            repo_info=repo_info
        )
        
        # 缓存结果
        _prediction_cache[cache_key] = result
        
        return jsonify(result)
        
    except ImportError as e:
        return jsonify({
            'error': f'GitPulse 模块导入失败: {str(e)}',
            'available': False,
            'hint': '请安装依赖: pip install torch numpy transformers'
        }), 503
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'available': False}), 500


@app.route('/api/forecast/status', methods=['GET'])
def get_forecast_status():
    """检查预测服务状态"""
    try:
        from GitPulse.prediction_service import get_prediction_service
        service = get_prediction_service()
        
        return jsonify({
            'available': service.is_available(),
            'error': service.get_error(),
            'model': 'GitPulse (Transformer+Text)' if service.is_available() else None
        })
    except ImportError as e:
        return jsonify({
            'available': False,
            'error': f'模块导入失败: {str(e)}',
            'hint': '请安装依赖: pip install torch numpy transformers'
        })
    except Exception as e:
        return jsonify({
            'available': False,
            'error': str(e)
        })


@app.route('/api/forecast/<path:repo_key>/explain', methods=['POST'])
def get_forecast_explanation(repo_key):
    """
    获取预测的 AI 可解释性分析
    输入: metric_name, historical_data, forecast_data, confidence
    输出: 预测依据、关键事件、风险提示、驱动因素、建议
    """
    try:
        data = request.json or {}
        metric_name = data.get('metric_name', 'OpenRank')
        historical_data = data.get('historical_data', {})
        forecast_data = data.get('forecast_data', {})
        confidence = data.get('confidence', 0.75)
        
        if not historical_data or not forecast_data:
            return jsonify({
                'error': '缺少历史数据或预测数据',
                'explanation': None
            }), 400
        
        # 标准化 repo_key
        if '_' in repo_key and '/' not in repo_key:
            repo_key = repo_key.replace('_', '/')
        
        # 获取仓库上下文
        repo_context = None
        issue_stats = None
        
        try:
            actual_key = data_service._normalize_repo_key(repo_key)
            summary = data_service.get_repo_summary(actual_key)
            repo_info = summary.get('repoInfo', {})
            if repo_info:
                repo_context = {
                    'name': repo_info.get('full_name', repo_key),
                    'description': repo_info.get('description', ''),
                    'language': repo_info.get('language', ''),
                    'stars': repo_info.get('stars', 0)
                }
            
            # 获取 Issue 统计
            project_summary = summary.get('projectSummary', {})
            if project_summary:
                issue_stats = project_summary.get('issueStats', {})
        except Exception as e:
            logger.warning(f"获取仓库上下文失败: {e}")
        
        # 生成解释
        explanation = prediction_explainer.generate_explanation(
            metric_name=metric_name,
            historical_data=historical_data,
            forecast_data=forecast_data,
            confidence=confidence,
            repo_context=repo_context,
            issue_stats=issue_stats
        )
        
        return jsonify({
            'metric_name': metric_name,
            'explanation': explanation
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': str(e),
            'explanation': None
        }), 500


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


# Issue 分析缓存 - 避免重复调用 AI
_issue_analysis_cache = {}

@app.route('/api/issues/analyze/<path:repo_key>', methods=['GET'])
def analyze_issues(repo_key):
    """
    使用 AI 分析项目 Issue，生成智能摘要
    总结项目遇到的问题和解决办法
    支持缓存，避免每次进入页面都重新分析
    """
    global _issue_analysis_cache
    
    try:
        from Agent.issue_analyzer import IssueAnalyzer
        
        # 支持两种格式
        if '_' in repo_key and '/' not in repo_key:
            repo_key = repo_key.replace('_', '/')
        
        # 查找 raw_monthly_data.json 文件
        actual_key = data_service._normalize_repo_key(repo_key)
        project_key = actual_key.replace('/', '_')
        
        # 检查缓存 - 同一个项目不重复分析
        if project_key in _issue_analysis_cache:
            print(f"[CACHE] 使用缓存的 Issue 分析结果: {project_key}")
            return jsonify(_issue_analysis_cache[project_key])
        
        data_dir = os.path.join(os.path.dirname(__file__), 'DataProcessor', 'data', project_key)
        
        raw_data_path = None
        if os.path.exists(data_dir):
            # 查找最新的 monthly_data 目录
            monthly_dirs = [d for d in os.listdir(data_dir) if d.startswith('monthly_data_')]
            if monthly_dirs:
                latest_dir = sorted(monthly_dirs)[-1]
                raw_data_path = os.path.join(data_dir, latest_dir, 'raw_monthly_data.json')
        
        if not raw_data_path or not os.path.exists(raw_data_path):
            return jsonify({
                'error': '未找到 Issue 数据文件',
                'summary': '暂无数据',
                'stats': {},
                'ai_enabled': False
            })
        
        # 创建分析器并分析
        analyzer = IssueAnalyzer()
        issues = analyzer.load_issues_from_raw_data(raw_data_path)
        
        if not issues:
            return jsonify({
                'summary': '暂无 Issue 数据',
                'stats': {'total': 0},
                'ai_enabled': False
            })
        
        result = analyzer.analyze_issues(issues, actual_key)
        
        # 缓存结果
        _issue_analysis_cache[project_key] = result
        print(f"[CACHE] 已缓存 Issue 分析结果: {project_key}")
        
        return jsonify(result)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': str(e),
            'summary': f'分析失败: {str(e)}',
            'stats': {},
            'ai_enabled': False
        }), 500


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


def _search_github_similar_enhanced(topics, language, stars, exclude_keys, description='', max_results=5, ai_summary=''):
    """
    增强版 GitHub API 搜索相似仓库
    优先级：1. 主题/功能相似 > 2. 描述关键词相似 > 3. 技术栈相似
    
    核心原则：
    - 不同项目应该推荐不同的相似仓库
    - 主题和功能相似是最重要的匹配维度
    - 技术栈相似只是辅助因素
    """
    import requests
    import os
    import re
    
    github_token = os.getenv('GITHUB_TOKEN')
    if not github_token:
        logger.warning("GITHUB_TOKEN 未配置，无法搜索相似仓库")
        return []
    
    headers = {
        'Authorization': f'token {github_token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    results = []
    seen_repos = set(exclude_keys)
    
    # ========== 提取功能关键词 ==========
    # 从 AI 摘要和描述中提取真正描述功能的关键词
    functional_keywords = set()
    
    # 从描述中提取
    if description:
        # 过滤掉通用词，保留功能性描述词
        stop_words = {'the', 'a', 'an', 'and', 'or', 'for', 'with', 'your', 'in', 'of', 'to', 
                      'is', 'it', 'this', 'that', 'are', 'be', 'as', 'at', 'by', 'from',
                      'state', 'art', 'based', 'using', 'new', 'best', 'most', 'all', 'any'}
        desc_words = re.findall(r'\b[a-zA-Z]{4,}\b', description.lower())
        functional_keywords.update([w for w in desc_words if w not in stop_words][:10])
    
    # 从 AI 摘要提取功能关键词
    if ai_summary:
        # 提取可能描述功能的短语
        func_patterns = [
            r'用于([^，。,\.]+)',
            r'提供([^，。,\.]+)',
            r'支持([^，。,\.]+)',
            r'实现([^，。,\.]+)',
            r'专注于([^，。,\.]+)',
        ]
        for pattern in func_patterns:
            matches = re.findall(pattern, ai_summary)
            for match in matches[:3]:
                words = re.findall(r'[a-zA-Z]{3,}', match.lower())
                functional_keywords.update(words[:3])
    
    logger.info(f"[Similar] Topics: {list(topics)[:5]}, Keywords: {list(functional_keywords)[:5]}")
    
    # ========== 策略1：按核心主题搜索（最高优先级）==========
    # 选择最具特征性的主题进行搜索
    if topics:
        # 排除过于通用的主题
        generic_topics = {'python', 'javascript', 'typescript', 'java', 'go', 'rust', 'c', 
                          'hacktoberfest', 'awesome', 'list', 'tool', 'library', 'framework'}
        specific_topics = [t for t in topics if t.lower() not in generic_topics and len(t) > 2]
        
        # 如果没有特定主题，使用所有主题
        if not specific_topics:
            specific_topics = [t for t in topics if len(t) > 2][:5]
        
        for topic in specific_topics[:3]:
            if len(results) >= max_results:
                break
            try:
                # 搜索同主题的项目，不限制语言（功能相似更重要）
                query = f'topic:{topic}'
                if stars > 100:
                    query += f' stars:>{max(50, stars//10)}'
                
                response = requests.get(
                    'https://api.github.com/search/repositories',
                    headers=headers,
                    params={'q': query, 'sort': 'stars', 'order': 'desc', 'per_page': 15},
                    timeout=10
                )
                
                if response.status_code == 200:
                    items = response.json().get('items', [])
                    for item in items:
                        full_name = item.get('full_name', '')
                        if full_name in seen_repos or full_name.replace('/', '_') in seen_repos:
                            continue
                        if len(results) >= max_results:
                            break
                        
                        repo_topics = set(item.get('topics', []))
                        common_topics = topics & repo_topics
                        
                        # 计算主题相似度分数
                        topic_similarity = len(common_topics) / max(len(topics), 1) * 100
                        
                        reasons = []
                        if common_topics:
                            reasons.append(f"功能相似: {', '.join(list(common_topics)[:3])}")
                        
                        # 检查描述相似性
                        item_desc = (item.get('description', '') or '').lower()
                        desc_match = sum(1 for kw in functional_keywords if kw in item_desc)
                        if desc_match > 0:
                            reasons.append(f"描述匹配 {desc_match} 个关键词")
                            topic_similarity += desc_match * 5
                        
                        # 同语言加分但不是主要因素
                        if item.get('language', '') == language:
                            reasons.append(f"同为 {language}")
                            topic_similarity += 5
                        
                        if not reasons:
                            reasons.append(f"相关 {topic} 项目")
                        
                        results.append({
                            'repo': full_name,
                            'full_name': full_name,
                            'description': (item.get('description', '') or '')[:150],
                            'language': item.get('language', ''),
                            'topics': list(repo_topics)[:5],
                            'stars': item.get('stargazers_count', 0),
                            'openrank': 0,
                            'similarity': min(95, topic_similarity),
                            'reasons': reasons,
                            'primary_reason': reasons[0] if reasons else f'{topic} 相关',
                            'source': 'github'
                        })
                        seen_repos.add(full_name)
                        
            except Exception as e:
                logger.warning(f"主题搜索失败 ({topic}): {e}")
    
    # ========== 策略2：按功能描述关键词搜索 ==========
    if len(results) < max_results and functional_keywords:
        try:
            # 使用功能关键词搜索
            search_keywords = list(functional_keywords)[:4]
            query = ' '.join(search_keywords)
            if language:
                query += f' language:{language}'
            if stars > 500:
                query += ' stars:>100'
            
            response = requests.get(
                'https://api.github.com/search/repositories',
                headers=headers,
                params={'q': query, 'sort': 'stars', 'order': 'desc', 'per_page': 10},
                timeout=10
            )
            
            if response.status_code == 200:
                items = response.json().get('items', [])
                for item in items:
                    full_name = item.get('full_name', '')
                    if full_name in seen_repos:
                        continue
                    if len(results) >= max_results:
                        break
                    
                    item_desc = (item.get('description', '') or '').lower()
                    desc_match = sum(1 for kw in functional_keywords if kw in item_desc)
                    
                    reasons = [f'功能相似: 描述匹配 {desc_match} 个关键词']
                    if item.get('language', '') == language:
                        reasons.append(f'技术栈: {language}')
                    
                    results.append({
                        'repo': full_name,
                        'full_name': full_name,
                        'description': (item.get('description', '') or '')[:150],
                        'language': item.get('language', ''),
                        'topics': item.get('topics', [])[:5],
                        'stars': item.get('stargazers_count', 0),
                        'openrank': 0,
                        'similarity': 40 + desc_match * 10,
                        'reasons': reasons,
                        'primary_reason': reasons[0],
                        'source': 'github'
                    })
                    seen_repos.add(full_name)
                    
        except Exception as e:
            logger.warning(f"关键词搜索失败: {e}")
    
    # ========== 策略3：按语言+规模搜索（最低优先级）==========
    # 只有在前两种策略结果不足时才使用
    if len(results) < 3 and language:
        try:
            query = f'language:{language}'
            if stars > 5000:
                query += f' stars:{stars//10}..{stars*2}'
            elif stars > 500:
                query += f' stars:{max(100, stars//5)}..{stars*5}'
            else:
                query += ' stars:>50'
            
            response = requests.get(
                'https://api.github.com/search/repositories',
                headers=headers,
                params={'q': query, 'sort': 'updated', 'order': 'desc', 'per_page': 10},
                timeout=10
            )
            
            if response.status_code == 200:
                items = response.json().get('items', [])
                for item in items:
                    full_name = item.get('full_name', '')
                    if full_name in seen_repos:
                        continue
                    if len(results) >= max_results:
                        break
                    
                    results.append({
                        'repo': full_name,
                        'full_name': full_name,
                        'description': (item.get('description', '') or '')[:150],
                        'language': item.get('language', ''),
                        'topics': item.get('topics', [])[:5],
                        'stars': item.get('stargazers_count', 0),
                        'openrank': 0,
                        'similarity': 30,
                        'reasons': [f'同为 {language} 项目', f'相近规模 ({item.get("stargazers_count", 0):,} stars)'],
                        'primary_reason': f'{language} 生态项目',
                        'source': 'github'
                    })
                    seen_repos.add(full_name)
                    
        except Exception as e:
            logger.warning(f"语言搜索失败: {e}")
    
    # 按相似度排序，相似度相同时按 stars 排序
    results.sort(key=lambda x: (x['similarity'], x['stars']), reverse=True)
    return results[:max_results]


def _search_github_similar(topics, language, stars, exclude_keys, existing_repos, max_results=5):
    """
    通过 GitHub API 搜索相似仓库（旧版本，保留兼容）
    """
    import requests
    import os
    
    github_token = os.getenv('GITHUB_TOKEN')
    if not github_token:
        return []
    
    headers = {
        'Authorization': f'token {github_token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    # 构建搜索查询
    query_parts = []
    
    # 添加主题搜索
    if topics:
        topic_list = list(topics)[:3]  # 最多使用3个主题
        for topic in topic_list:
            query_parts.append(f'topic:{topic}')
    
    # 添加语言过滤
    if language:
        query_parts.append(f'language:{language}')
    
    # 添加星数范围（相似规模）
    if stars > 1000:
        query_parts.append(f'stars:>{stars//10}')
    elif stars > 100:
        query_parts.append(f'stars:>50')
    
    if not query_parts:
        return []
    
    query = ' '.join(query_parts)
    
    try:
        url = 'https://api.github.com/search/repositories'
        params = {
            'q': query,
            'sort': 'stars',
            'order': 'desc',
            'per_page': 10
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code != 200:
            logger.warning(f"GitHub API 返回状态码: {response.status_code}")
            return []
        
        data = response.json()
        items = data.get('items', [])
        
        results = []
        for item in items:
            full_name = item.get('full_name', '')
            
            # 排除已存在的和自己
            if full_name in exclude_keys or full_name.replace('/', '_') in exclude_keys:
                continue
            if full_name in existing_repos or full_name.replace('/', '_') in existing_repos:
                continue
            
            repo_topics = item.get('topics', [])
            repo_language = item.get('language', '')
            repo_stars = item.get('stargazers_count', 0)
            
            # 计算相似度
            reasons = []
            similarity = 0
            
            if topics and repo_topics:
                common = set(topics) & set(repo_topics)
                if common:
                    similarity += min(len(common) * 10, 30)
                    reasons.append(f"主题相似: {', '.join(list(common)[:2])}")
            
            if language and repo_language and language.lower() == repo_language.lower():
                similarity += 25
                reasons.append(f"技术栈相同: {repo_language}")
            
            if not reasons:
                continue
            
            results.append({
                'repo': full_name,
                'full_name': full_name,
                'description': (item.get('description', '') or '')[:120],
                'language': repo_language,
                'topics': repo_topics[:5],
                'stars': repo_stars,
                'openrank': 0,  # GitHub API 没有 OpenRank
                'similarity': similarity,
                'reasons': reasons,
                'primary_reason': '来自 GitHub 推荐',
                'breakdown': {},
                'source': 'github'  # 标记来源
            })
            
            if len(results) >= max_results:
                break
        
        return results
        
    except Exception as e:
        logger.warning(f"GitHub 搜索失败: {e}")
        return []


@app.route('/api/similar/<path:repo_key>', methods=['GET'])
def get_similar_repos(repo_key):
    """
    获取相似仓库推荐
    多维度相似性评估：主题相似、技术栈相似、规模相似、活跃度相似
    返回 3-5 个最相似的仓库，每个都有充分的理由
    """
    try:
        # 标准化 repo_key
        if '_' in repo_key and '/' not in repo_key:
            repo_key = repo_key.replace('_', '/')
        
        actual_key = data_service._normalize_repo_key(repo_key)
        # 获取所有可能的 key 变体用于排除自己
        self_keys = {
            repo_key, 
            actual_key, 
            repo_key.replace('/', '_'), 
            actual_key.replace('/', '_'),
            repo_key.replace('_', '/'),
            actual_key.replace('_', '/')
        }
        
        # 获取当前仓库的信息
        current_summary = data_service.get_repo_summary(actual_key)
        current_repo_info = current_summary.get('repoInfo', {})
        current_topics = set(current_repo_info.get('topics', []))
        current_language = current_repo_info.get('language', '')
        current_stars = current_repo_info.get('stars', 0)
        
        # 获取当前仓库的 OpenRank
        current_openrank = 0
        for key_variant in [actual_key, actual_key.replace('/', '_')]:
            if key_variant in data_service.loaded_timeseries:
                ts_data = data_service.loaded_timeseries[key_variant]
                for metric_name, metric_data in ts_data.items():
                    if 'openrank' in metric_name.lower():
                        if isinstance(metric_data, dict):
                            values = [v for v in metric_data.values() if isinstance(v, (int, float)) and v > 0]
                            if values:
                                current_openrank = values[-1]
                        break
                break
        
        # 从 AI 摘要中提取关键词（即使没有 topics 也能匹配）
        current_keywords = set()
        project_summary = current_summary.get('projectSummary') or {}
        ai_summary = project_summary.get('aiSummary', '') or ''
        
        # 提取技术关键词
        tech_keywords = [
            'python', 'javascript', 'typescript', 'java', 'c++', 'rust', 'go', 'swift',
            'react', 'vue', 'angular', 'node', 'django', 'flask', 'spring', 'rails',
            'machine learning', 'deep learning', 'ai', 'ml', 'nlp', 'computer vision',
            'database', 'api', 'web', 'mobile', 'cloud', 'docker', 'kubernetes',
            'tensorflow', 'pytorch', 'transformer', 'neural', 'backend', 'frontend',
            '框架', '库', '工具', '平台', '系统', '引擎', '服务'
        ]
        
        ai_summary_lower = ai_summary.lower()
        for kw in tech_keywords:
            if kw in ai_summary_lower:
                current_keywords.add(kw)
        
        # 合并 topics 和关键词
        current_topics = current_topics | current_keywords
        
        # 获取仓库名称关键词
        repo_name = current_repo_info.get('name', '') or repo_key.split('/')[-1]
        name_parts = repo_name.lower().replace('-', ' ').replace('_', ' ').split()
        current_keywords.update(name_parts)
        
        # ====== 完全使用 GitHub API 搜索，忽略本地数据 ======
        search_terms = current_topics | current_keywords
        
        # 直接从 GitHub 搜索相似仓库
        try:
            similar_repos = _search_github_similar_enhanced(
                topics=search_terms,
                language=current_language,
                stars=current_stars,
                exclude_keys=self_keys,
                description=current_repo_info.get('description', ''),
                max_results=5,
                ai_summary=ai_summary
            )
            
            if not similar_repos:
                return jsonify({
                    'current': {
                        'repo': repo_key,
                        'topics': list(current_topics),
                        'language': current_language,
                        'stars': current_stars,
                        'openrank': round(current_openrank, 2)
                    },
                    'similar': [],
                    'message': '未找到相似仓库，请检查 GITHUB_TOKEN 配置或网络连接',
                    'source': 'github'
                })
            
            return jsonify({
                'current': {
                    'repo': repo_key,
                    'topics': list(current_topics),
                    'language': current_language,
                    'stars': current_stars,
                    'openrank': round(current_openrank, 2)
                },
                'similar': similar_repos,
                'message': None,
                'source': 'github'
            })
            
        except Exception as e:
            logger.error(f"GitHub 搜索失败: {e}")
            return jsonify({
                'current': {
                    'repo': repo_key,
                    'topics': list(current_topics),
                    'language': current_language,
                    'stars': current_stars,
                    'openrank': round(current_openrank, 2)
                },
                'similar': [],
                'message': f'GitHub 搜索失败: {str(e)}',
                'source': 'github'
            })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'similar': []}), 500


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
                    # 构建简化的项目信息
                    full_name = item.replace('_', '/', 1)
                    
                    # 检查 data_service 是否有加载该项目的数据
                    has_timeseries = item in data_service.loaded_timeseries or full_name in data_service.loaded_timeseries
                    has_text = item in data_service.loaded_text or full_name in data_service.loaded_text
                    
                    # 获取时间范围
                    time_range = None
                    key = full_name if full_name in data_service.loaded_timeseries else item
                    if key in data_service.loaded_timeseries:
                        try:
                            ts_data = data_service.loaded_timeseries[key]
                            if ts_data:
                                first_metric = list(ts_data.values())[0]
                                # 处理嵌套结构 {'raw': {month: value}} 或直接 {month: value}
                                if isinstance(first_metric, dict):
                                    if 'raw' in first_metric:
                                        months = list(first_metric['raw'].keys())
                                    else:
                                        months = list(first_metric.keys())
                                    # 过滤出有效的月份格式 YYYY-MM
                                    valid_months = [m for m in months if isinstance(m, str) and len(m) == 7 and '-' in m]
                                    if valid_months:
                                        valid_months.sort()
                                        time_range = {
                                            'start': valid_months[0],
                                            'end': valid_months[-1],
                                            'months': len(valid_months)
                                        }
                        except Exception as e:
                            print(f"获取时间范围失败 {item}: {e}")
                    
                    projects.append({
                        'name': item,
                        'full_name': full_name,
                        'folder': item,
                        'has_timeseries': has_timeseries,
                        'has_text': has_text,
                        'time_range': time_range
                    })
        
        # 默认项目
        default_project = 'X-lab2017_open-digger'
        
        return jsonify({
            'projects': projects,
            'default': default_project
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
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


@app.route('/api/project/<path:project_name>/regenerate-summary', methods=['POST'])
def regenerate_project_summary(project_name):
    """重新生成项目 AI 摘要（当原摘要生成失败时使用）"""
    try:
        # 检查 DeepSeek 客户端是否可用
        try:
            from Agent.deepseek_client import DeepSeekClient, get_deepseek_client
            client = get_deepseek_client()
            if not client:
                return jsonify({
                    'error': 'DeepSeek API 不可用。请检查：\n1. 是否已安装 openai 库 (pip install openai)\n2. 是否已配置 DEEPSEEK_API_KEY 环境变量',
                    'success': False
                }), 400
        except ImportError as e:
            return jsonify({
                'error': f'无法导入 DeepSeek 客户端: {str(e)}',
                'success': False
            }), 400
        
        # 找到项目数据目录
        project_dir_name = project_name.replace('/', '_')
        data_dir = os.path.join(os.path.dirname(__file__), 'DataProcessor', 'data', project_dir_name)
        
        if not os.path.exists(data_dir):
            return jsonify({'error': f'项目数据目录不存在: {project_dir_name}', 'success': False}), 404
        
        # 找到最新的 monthly_data 文件夹
        monthly_folders = [f for f in os.listdir(data_dir) if f.startswith('monthly_data_')]
        if not monthly_folders:
            return jsonify({'error': '未找到项目月度数据', 'success': False}), 404
        
        latest_folder = sorted(monthly_folders)[-1]
        monthly_path = os.path.join(data_dir, latest_folder)
        
        # project_summary.json 在 timeseries_for_model 子目录下
        model_path = os.path.join(monthly_path, 'timeseries_for_model')
        
        # 加载 project_summary.json
        summary_path = os.path.join(model_path, 'project_summary.json')
        if not os.path.exists(summary_path):
            # 备用：直接在 monthly_path 下查找
            summary_path = os.path.join(monthly_path, 'project_summary.json')
            if not os.path.exists(summary_path):
                return jsonify({'error': '未找到 project_summary.json', 'success': False}), 404
        
        with open(summary_path, 'r', encoding='utf-8') as f:
            project_summary = json.load(f)
        
        # 加载 timeseries_data.json 获取指标数据（也在 timeseries_for_model 下）
        timeseries_path = os.path.join(model_path, 'timeseries_data.json')
        timeseries_data = {}
        if os.path.exists(timeseries_path):
            with open(timeseries_path, 'r', encoding='utf-8') as f:
                timeseries_data = json.load(f)
        else:
            # 备用：直接在 monthly_path 下查找
            timeseries_path = os.path.join(monthly_path, 'timeseries_data.json')
            if os.path.exists(timeseries_path):
                with open(timeseries_path, 'r', encoding='utf-8') as f:
                    timeseries_data = json.load(f)
        
        # 提取关键信息
        repo_info = project_summary.get('repo_info', {})
        data_range = project_summary.get('data_range', {})
        issue_stats = project_summary.get('issue_stats', {})
        
        repo_name = repo_info.get('full_name', project_name.replace('_', '/'))
        repo_description = repo_info.get('description', '')
        repo_language = repo_info.get('language', '')
        repo_stars = repo_info.get('stargazers_count', repo_info.get('stars', 0))
        
        date_range = f"{data_range.get('start', '?')} 至 {data_range.get('end', '?')}"
        total_months = data_range.get('months', 0)
        
        # 计算平均指标
        avg_openrank = 0
        avg_activity = 0
        metrics = timeseries_data.get('metrics', {})
        openrank_data = metrics.get('OpenRank', {})
        activity_data = metrics.get('活跃度', {})
        
        if openrank_data:
            values = [v for v in openrank_data.values() if isinstance(v, (int, float))]
            avg_openrank = sum(values) / len(values) if values else 0
        
        if activity_data:
            values = [v for v in activity_data.values() if isinstance(v, (int, float))]
            avg_activity = sum(values) / len(values) if values else 0
        
        # 构建提示词
        prompt = f"""你是开源项目分析专家。请为以下项目生成一个全面的项目摘要（3-5段话，突出项目特点、发展趋势和主要活动）。

【项目基本信息】
- 项目名称: {repo_name}
- 项目描述: {repo_description}
- 主要语言: {repo_language}
- Star数: {repo_stars}

【数据统计】
- 数据时间范围: {date_range}（共 {total_months} 个月）
- 平均OpenRank: {avg_openrank:.2f}
- 平均活跃度: {avg_activity:.2f}

【Issue分类统计】
{json.dumps(issue_stats, ensure_ascii=False, indent=2) if issue_stats else '暂无分类数据'}

请生成一个全面的项目摘要，包括：
1. 项目定位和核心功能
2. 项目的发展趋势和活跃度
3. 主要的技术活动和社区参与情况
4. 项目的整体健康状况和未来展望

摘要应该简洁、专业，突出项目的核心价值和特点。"""
        
        # 调用 DeepSeek API
        try:
            new_summary = client.ask(prompt, context="")
            if not new_summary or new_summary.startswith('抱歉'):
                return jsonify({'error': f'AI 生成失败: {new_summary}', 'success': False}), 500
        except Exception as e:
            return jsonify({'error': f'AI API 调用失败: {str(e)}', 'success': False}), 500
        
        # 更新 project_summary.json
        project_summary['ai_summary'] = new_summary
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(project_summary, f, ensure_ascii=False, indent=2)
        
        # 清除缓存，强制重新加载
        data_service.clear_cache(project_name.replace('/', '_'))
        
        logger.info(f"[摘要重生成] {project_name} 摘要已更新")
        
        return jsonify({
            'success': True,
            'message': '摘要已成功重新生成',
            'summary': new_summary
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'success': False}), 500


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
            text_data['readme'] = readmes
        
        # 获取重要文档
        important_files = crawler.get_important_md_files(owner, repo, max_files=10)
        if important_files:
            text_data['docs'] = important_files
        
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


# 注意: /api/predict/* 路由已弃用，请使用 /api/forecast/* 路由
# 旧的预测路由已删除以避免 predictor 未定义错误




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


def ensure_maxkb_running():
    """确保 MaxKB Docker 容器正在运行"""
    import subprocess
    import time
    
    container_name = "openvista-maxkb"
    
    try:
        # 检查 Docker 是否可用
        result = subprocess.run(
            ["docker", "version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            print("[WARN] Docker 未安装或未运行，跳过 MaxKB 自动启动")
            return False
    except FileNotFoundError:
        print("[WARN] Docker 命令不可用，跳过 MaxKB 自动启动")
        return False
    except subprocess.TimeoutExpired:
        print("[WARN] Docker 响应超时，跳过 MaxKB 自动启动")
        return False
    except Exception as e:
        print(f"[WARN] Docker 检查失败: {e}")
        return False
    
    try:
        # 检查容器是否存在
        result = subprocess.run(
            ["docker", "inspect", container_name],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            # 容器不存在，尝试使用 docker-compose 创建
            print(f"[INFO] MaxKB 容器不存在，尝试创建...")
            compose_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docker-compose.maxkb.yml")
            
            if os.path.exists(compose_file):
                result = subprocess.run(
                    ["docker", "compose", "-f", compose_file, "up", "-d"],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                if result.returncode == 0:
                    print(f"[OK] MaxKB 容器已创建并启动")
                    print("[INFO] 等待 MaxKB 服务就绪（首次启动可能需要 30-60 秒）...")
                    time.sleep(15)  # 等待服务初始化
                    return True
                else:
                    print(f"[WARN] MaxKB 容器创建失败: {result.stderr}")
                    return False
            else:
                print(f"[WARN] 未找到 docker-compose.maxkb.yml，请手动启动 MaxKB")
                return False
        
        # 容器存在，检查是否正在运行
        import json
        container_info = json.loads(result.stdout)
        if container_info and len(container_info) > 0:
            state = container_info[0].get("State", {})
            is_running = state.get("Running", False)
            
            if is_running:
                print(f"[OK] MaxKB 容器已在运行")
                return True
            else:
                # 容器存在但未运行，启动它
                print(f"[INFO] 正在启动 MaxKB 容器...")
                result = subprocess.run(
                    ["docker", "start", container_name],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode == 0:
                    print(f"[OK] MaxKB 容器已启动")
                    print("[INFO] 等待 MaxKB 服务就绪...")
                    time.sleep(10)  # 等待服务启动
                    return True
                else:
                    print(f"[WARN] MaxKB 容器启动失败: {result.stderr}")
                    return False
        
    except subprocess.TimeoutExpired:
        print("[WARN] Docker 操作超时")
        return False
    except Exception as e:
        print(f"[WARN] MaxKB 容器检查失败: {e}")
        return False
    
    return False


if __name__ == '__main__':
    print("\n" + "="*60)
    print("  ___                   __     ___     _        ")
    print(" / _ \\ _ __   ___ _ __  \\ \\   / (_)___| |_ __ _ ")
    print("| | | | '_ \\ / _ \\ '_ \\  \\ \\ / /| / __| __/ _` |")
    print("| |_| | |_) |  __/ | | |  \\ V / | \\__ \\ || (_| |")
    print(" \\___/| .__/ \\___|_| |_|   \\_/  |_|___/\\__\\__,_|")
    print("      |_|   GitHub 仓库生态画像分析平台          ")
    print("="*60)
    
    # 自动启动 MaxKB Docker 容器
    print("\n[Docker] 检查 MaxKB 服务状态...")
    ensure_maxkb_running()
    
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
    try:
        service = get_gitpulse_service()
        if service and service.is_available():
            logger.info(f"  状态: 已初始化 (OK)")
            logger.info(f"  模型: GitPulse Transformer+Text")
        else:
            err = service.get_error() if service else "服务未初始化"
            logger.warning(f"  状态: 不可用")
            logger.warning(f"  原因: {err}")
    except Exception as e:
        logger.warning(f"  状态: 初始化失败")
        logger.warning(f"  错误: {e}")
    
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
