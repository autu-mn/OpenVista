"""
DataPulse 后端 API
GitHub 仓库生态画像分析平台 - 时序数据可视化与归因分析
从真实数据文件读取，动态确定时间范围
"""
from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import os
from datetime import datetime
from collections import defaultdict
import re
from data_service import DataService
from Agent.qa_agent import QAAgent
from LLM2TSA.predictor import LLMTimeSeriesPredictor

app = Flask(__name__)
CORS(app)

# 数据服务实例
data_service = DataService()

# AI Agent实例
qa_agent = QAAgent()

# 预测器实例
predictor = LLMTimeSeriesPredictor(enable_cache=True)

# OpenDigger MCP 客户端（可选）
try:
    from mcp_client import get_mcp_client
    mcp_client = get_mcp_client()
    MCP_AVAILABLE = True
except Exception as e:
    print(f"警告: OpenDigger MCP 客户端不可用: {e}")
    MCP_AVAILABLE = False
    mcp_client = None


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})


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
    """
    month = request.args.get('month')  # 可选参数，获取特定月份
    
    try:
        # 支持两种格式：owner/repo 或 owner_repo
        if '_' in repo_key and '/' not in repo_key:
            repo_key = repo_key.replace('_', '/')
        
        issues_data = data_service.get_aligned_issues(repo_key, month)
        return jsonify(issues_data)
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
                # 检查是否有processed文件夹
                has_processed = any(
                    '_processed' in f and os.path.isdir(os.path.join(item_path, f))
                    for f in os.listdir(item_path)
                )
                if has_processed:
                    summary = qa_agent.get_project_summary(item)
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
                # 检查是否有processed文件夹
                has_processed = any(
                    '_processed' in f and os.path.isdir(os.path.join(item_path, f))
                    for f in os.listdir(item_path)
                )
                if has_processed:
                    # 简单的名称匹配
                    if query in item.lower():
                        summary = qa_agent.get_project_summary(item)
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
                return jsonify({
                    'exists': True,
                    'projectName': project_name,
                    'repoKey': repo_key
                })
        
        return jsonify({'exists': False})
    except Exception as e:
        return jsonify({'exists': False, 'error': str(e)})


@app.route('/api/predict/<path:repo_key>', methods=['POST'])
def predict_metrics(repo_key):
    """预测指定仓库的时序指标"""
    try:
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
        
        # 获取时序数据
        timeseries_data = data_service.loaded_timeseries[repo_key]
        
        # 如果没有指定指标，返回所有可预测的指标列表
        if not metric_name:
            available_metrics = []
            if timeseries_data:
                # 获取第一个月份的数据，列出所有指标
                first_month = sorted(timeseries_data.keys())[0] if timeseries_data else None
                if first_month:
                    available_metrics = list(timeseries_data[first_month].keys())
            
            return jsonify({
                'available_metrics': available_metrics,
                'message': '请指定要预测的指标名称'
            })
        
        # 提取指定指标的历史数据
        historical_data = {}
        for month in sorted(timeseries_data.keys()):
            metrics = timeseries_data[month]
            # 支持多种指标名称格式
            value = None
            if metric_name in metrics:
                value = metrics[metric_name]
            elif f'opendigger_{metric_name}' in metrics:
                value = metrics[f'opendigger_{metric_name}']
            elif any(k.endswith(metric_name) for k in metrics.keys()):
                # 模糊匹配
                for k in metrics.keys():
                    if k.endswith(metric_name):
                        value = metrics[k]
                        break
            
            if value is not None:
                historical_data[month] = value
        
        if not historical_data:
            return jsonify({
                'error': f'未找到指标 {metric_name} 的历史数据',
                'available_metrics': list(timeseries_data.get(sorted(timeseries_data.keys())[0], {}).keys()) if timeseries_data else []
            }), 404
        
        # 执行预测
        result = predictor.predict(
            metric_name=metric_name,
            historical_data=historical_data,
            forecast_months=forecast_months,
            include_reasoning=include_reasoning
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


@app.route('/api/predict/<path:repo_key>/multiple', methods=['POST'])
def predict_multiple_metrics(repo_key):
    """批量预测多个指标"""
    try:
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
        
        # 获取时序数据
        timeseries_data = data_service.loaded_timeseries[repo_key]
        
        # 提取所有指标的历史数据
        metrics_data = {}
        for metric_name in metric_names:
            historical_data = {}
            for month in sorted(timeseries_data.keys()):
                metrics = timeseries_data[month]
                value = None
                if metric_name in metrics:
                    value = metrics[metric_name]
                elif f'opendigger_{metric_name}' in metrics:
                    value = metrics[f'opendigger_{metric_name}']
                elif any(k.endswith(metric_name) for k in metrics.keys()):
                    for k in metrics.keys():
                        if k.endswith(metric_name):
                            value = metrics[k]
                            break
                
                if value is not None:
                    historical_data[month] = value
            
            if historical_data:
                metrics_data[metric_name] = historical_data
        
        if not metrics_data:
            return jsonify({'error': '未找到任何指标的历史数据'}), 404
        
        # 批量预测
        results = predictor.predict_multiple(metrics_data, forecast_months)
        
        return jsonify({
            'results': results,
            'repo_key': repo_key,
            'forecast_months': forecast_months
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/crawl', methods=['GET', 'POST'])
def crawl_repository():
    """爬取GitHub仓库并返回实时进度（SSE）- 使用新的月度爬取流程"""
    from flask import Response, stream_with_context
    
    try:
        if request.method == 'GET':
            owner = request.args.get('owner', '').strip()
            repo = request.args.get('repo', '').strip()
            max_per_month = int(request.args.get('max_per_month', '3'))
        else:
            data = request.json or {}
            owner = data.get('owner', '').strip()
            repo = data.get('repo', '').strip()
            max_per_month = data.get('max_per_month', 3)
        
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
                # 定义所有25个指标，确保即使缺失也用0填充（用于模型训练）
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
                    'Issue响应时间': 'issue_response_time',
                    'Issue解决时长': 'issue_resolution_duration',
                    'Issue存活时间': 'issue_age',
                    '变更请求': 'change_requests',
                    'PR接受数': 'change_requests_accepted',
                    'PR审查': 'change_requests_reviews',
                    'PR响应时间': 'change_request_response_time',
                    'PR处理时长': 'change_request_resolution_duration',
                    'PR存活时间': 'change_request_age',
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


# ========== OpenDigger MCP API 端点 ==========

@app.route('/api/opendigger/metric', methods=['GET'])
def get_opendigger_metric():
    """获取单个 OpenDigger 指标"""
    if not MCP_AVAILABLE:
        return jsonify({'error': 'OpenDigger MCP 服务不可用'}), 503
    
    try:
        owner = request.args.get('owner', '').strip()
        repo = request.args.get('repo', '').strip()
        metric_name = request.args.get('metric', '').strip()
        platform = request.args.get('platform', 'GitHub').strip()
        
        if not owner or not repo or not metric_name:
            return jsonify({'error': '请提供 owner, repo 和 metric 参数'}), 400
        
        result = mcp_client.get_metric(owner, repo, metric_name, platform)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/opendigger/metrics/batch', methods=['POST'])
def get_opendigger_metrics_batch():
    """批量获取多个 OpenDigger 指标"""
    if not MCP_AVAILABLE:
        return jsonify({'error': 'OpenDigger MCP 服务不可用'}), 503
    
    try:
        data = request.json or {}
        owner = data.get('owner', '').strip()
        repo = data.get('repo', '').strip()
        metrics = data.get('metrics', [])
        platform = data.get('platform', 'GitHub').strip()
        
        if not owner or not repo or not metrics:
            return jsonify({'error': '请提供 owner, repo 和 metrics 参数'}), 400
        
        result = mcp_client.get_metrics_batch(owner, repo, metrics, platform)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/opendigger/compare', methods=['POST'])
def compare_repositories():
    """对比多个仓库"""
    if not MCP_AVAILABLE:
        return jsonify({'error': 'OpenDigger MCP 服务不可用'}), 503
    
    try:
        data = request.json or {}
        repos = data.get('repos', [])
        metrics = data.get('metrics', [])
        platform = data.get('platform', 'GitHub').strip()
        
        if not repos or not metrics:
            return jsonify({'error': '请提供 repos 和 metrics 参数'}), 400
        
        result = mcp_client.compare_repositories(repos, metrics, platform)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/opendigger/trends', methods=['GET'])
def analyze_trends():
    """分析趋势"""
    if not MCP_AVAILABLE:
        return jsonify({'error': 'OpenDigger MCP 服务不可用'}), 503
    
    try:
        owner = request.args.get('owner', '').strip()
        repo = request.args.get('repo', '').strip()
        metric_name = request.args.get('metric', '').strip()
        start_date = request.args.get('start_date', '').strip() or None
        end_date = request.args.get('end_date', '').strip() or None
        platform = request.args.get('platform', 'GitHub').strip()
        
        if not owner or not repo or not metric_name:
            return jsonify({'error': '请提供 owner, repo 和 metric 参数'}), 400
        
        result = mcp_client.analyze_trends(owner, repo, metric_name, start_date, end_date, platform)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/opendigger/ecosystem', methods=['GET'])
def get_ecosystem_insights():
    """获取生态系统洞察"""
    if not MCP_AVAILABLE:
        return jsonify({'error': 'OpenDigger MCP 服务不可用'}), 503
    
    try:
        owner = request.args.get('owner', '').strip()
        repo = request.args.get('repo', '').strip()
        platform = request.args.get('platform', 'GitHub').strip()
        
        if not owner or not repo:
            return jsonify({'error': '请提供 owner 和 repo 参数'}), 400
        
        result = mcp_client.get_ecosystem_insights(owner, repo, platform)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/opendigger/health', methods=['GET'])
def mcp_server_health():
    """获取 MCP 服务器健康状态"""
    if not MCP_AVAILABLE:
        return jsonify({'error': 'OpenDigger MCP 服务不可用'}), 503
    
    try:
        result = mcp_client.server_health()
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("\n" + "="*60)
    print("DataPulse 后端服务启动")
    print("="*60)
    
    repos = data_service.get_loaded_repos()
    if repos:
        print(f"\n已加载 {len(repos)} 个仓库的数据:")
        for repo in repos:
            summary = data_service.get_repo_summary(repo)
            time_range = summary.get('timeRange', {})
            print(f"  - {repo}: {time_range.get('start', '?')} ~ {time_range.get('end', '?')} ({time_range.get('months', 0)} 个月)")
    else:
        print("\n警告: 没有找到数据文件")
        print("请将处理后的数据放入 backend/Data 目录")
    
    print("\n" + "="*60)
    
    app.run(debug=True, port=5000, host='0.0.0.0')
