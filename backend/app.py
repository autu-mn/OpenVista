"""DataPulse 后端 API - GitHub 仓库生态画像分析平台"""
from flask import Flask, jsonify, request, Response, stream_with_context
from flask_cors import CORS
import json
import os
from datetime import datetime
from data_service import DataService
from Agent.qa_agent import QAAgent

app = Flask(__name__)
CORS(app)

data_service = DataService()
qa_agent = QAAgent()


@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})


@app.route('/api/repos', methods=['GET'])
def get_repos():
    repos = data_service.get_loaded_repos()
    summaries = [data_service.get_repo_summary(repo) for repo in repos]
    return jsonify({'repos': repos, 'summaries': summaries})


@app.route('/api/repo/<path:repo_key>/summary', methods=['GET'])
def get_repo_summary(repo_key):
    try:
        if '_' in repo_key and '/' not in repo_key:
            repo_key = repo_key.replace('_', '/')
        summary = data_service.get_repo_summary(repo_key)
        return jsonify(summary)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/load', methods=['POST'])
def load_data():
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
    try:
        if '_' in repo_key and '/' not in repo_key:
            repo_key = repo_key.replace('_', '/')
        grouped = data_service.get_grouped_timeseries(repo_key)
        return jsonify(grouped)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/issues/<path:repo_key>', methods=['GET'])
def get_issues_by_month(repo_key):
    month = request.args.get('month')
    try:
        if '_' in repo_key and '/' not in repo_key:
            repo_key = repo_key.replace('_', '/')
        issues_data = data_service.get_aligned_issues(repo_key, month)
        return jsonify(issues_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/analysis/<path:repo_key>', methods=['GET'])
def get_wave_analysis(repo_key):
    try:
        if '_' in repo_key and '/' not in repo_key:
            repo_key = repo_key.replace('_', '/')
        analysis = data_service.analyze_waves(repo_key)
        return jsonify(analysis)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/keywords/<path:repo_key>/<month>', methods=['GET'])
def get_keywords(repo_key, month):
    try:
        keywords = data_service.get_month_keywords(repo_key, month)
        return jsonify(keywords)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/events/<path:repo_key>', methods=['GET'])
def get_events(repo_key):
    try:
        events = data_service.get_major_events(repo_key)
        return jsonify(events)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/demo', methods=['GET'])
def get_demo_data():
    return jsonify(data_service.get_demo_data())


@app.route('/api/metric-groups', methods=['GET'])
def get_metric_groups():
    return jsonify(data_service.metric_groups)


@app.route('/api/projects', methods=['GET'])
def get_projects():
    try:
        data_dir = os.path.join(os.path.dirname(__file__), 'DataProcessor', 'data')
        if not os.path.exists(data_dir):
            return jsonify({'projects': [], 'default': None})
        
        projects = []
        for item in os.listdir(data_dir):
            item_path = os.path.join(data_dir, item)
            if os.path.isdir(item_path):
                has_processed = any(
                    '_processed' in f and os.path.isdir(os.path.join(item_path, f))
                    for f in os.listdir(item_path)
                )
                if has_processed:
                    summary = qa_agent.get_project_summary(item)
                    projects.append(summary)
        
        return jsonify({'projects': projects, 'default': 'X-lab2017_open-digger'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/projects/search', methods=['GET'])
def search_projects():
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
                has_processed = any(
                    '_processed' in f and os.path.isdir(os.path.join(item_path, f))
                    for f in os.listdir(item_path)
                )
                if has_processed and query in item.lower():
                    summary = qa_agent.get_project_summary(item)
                    results.append(summary)
        
        return jsonify({'projects': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/project/<path:project_name>/summary', methods=['GET'])
def get_project_summary(project_name):
    try:
        summary = qa_agent.get_project_summary(project_name)
        return jsonify(summary)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/qa', methods=['POST'])
def ask_question():
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


@app.route('/api/crawl', methods=['GET', 'POST'])
def crawl_repository():
    """爬取GitHub仓库并返回实时进度（SSE）"""
    try:
        if request.method == 'GET':
            owner = request.args.get('owner', '').strip()
            repo = request.args.get('repo', '').strip()
            max_issues = int(request.args.get('max_issues', 100))
            max_prs = int(request.args.get('max_prs', 100))
            max_commits = int(request.args.get('max_commits', 100))
        else:
            data = request.json or {}
            owner = data.get('owner', '').strip()
            repo = data.get('repo', '').strip()
            max_issues = data.get('max_issues', 100)
            max_prs = data.get('max_prs', 100)
            max_commits = data.get('max_commits', 100)
        
        if not owner or not repo:
            return jsonify({'error': '请提供仓库所有者和仓库名'}), 400
        
        def generate():
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'DataProcessor'))
            from github_text_crawler import GitHubTextCrawler, OpenDiggerMetrics
            
            try:
                yield f"data: {json.dumps({'type': 'start', 'message': '开始爬取仓库数据...'})}\n\n"
                
                crawler = GitHubTextCrawler()
                all_data = {}
                missing_metrics = []
                
                progress_steps = [
                    ('获取 OpenDigger 基础指标', 5),
                    ('获取仓库核心信息', 15),
                    ('获取 README', 25),
                    ('获取 Issues', 35),
                    ('获取 Pull Requests', 45),
                    ('获取标签', 55),
                    ('获取提交历史', 65),
                    ('获取贡献者', 75),
                    ('获取发布版本', 80),
                ]
                
                crawler.check_rate_limit()
                
                for step, (step_name, progress) in enumerate(progress_steps):
                    yield f"data: {json.dumps({'type': 'progress', 'step': step, 'stepName': step_name, 'message': f'正在{step_name}...', 'progress': progress})}\n\n"
                    
                    if step == 0:
                        opendigger = OpenDiggerMetrics()
                        opendigger_data, missing_metrics = opendigger.get_metrics(owner, repo)
                        all_data['opendigger_metrics'] = opendigger_data
                    elif step == 1:
                        all_data['repo_info'] = crawler.get_repo_info(owner, repo)
                    elif step == 2:
                        all_data['readme'] = crawler.get_readme(owner, repo)
                    elif step == 3:
                        all_data['issues'] = crawler.get_issues(owner, repo, max_count=max_issues)
                    elif step == 4:
                        all_data['pulls'] = crawler.get_pulls(owner, repo, max_count=max_prs)
                    elif step == 5:
                        all_data['labels'] = crawler.get_labels(owner, repo)
                    elif step == 6:
                        all_data['commits'] = crawler.get_commits(owner, repo, max_count=max_commits)
                    elif step == 7:
                        all_data['contributors'] = crawler.get_contributors(owner, repo)
                    elif step == 8:
                        all_data['releases'] = crawler.get_releases(owner, repo)
                
                if missing_metrics:
                    yield f"data: {json.dumps({'type': 'progress', 'step': 9, 'stepName': '计算备用指标', 'message': '正在计算备用指标...', 'progress': 85})}\n\n"
                    fallback_metrics = crawler.calculate_fallback_metrics(
                        owner, repo, all_data.get('issues', []), all_data.get('pulls', []),
                        all_data.get('commits', []), all_data.get('repo_info')
                    )
                    all_data['fallback_metrics'] = fallback_metrics
                
                yield f"data: {json.dumps({'type': 'progress', 'step': 10, 'stepName': '保存数据', 'message': '正在保存数据...', 'progress': 90})}\n\n"
                json_file = crawler.save_to_json(all_data, owner, repo)
                
                yield f"data: {json.dumps({'type': 'progress', 'step': 11, 'stepName': '处理数据', 'message': '正在处理数据并上传到MaxKB...', 'progress': 95})}\n\n"
                crawler.process_data(json_file, enable_maxkb_upload=True)
                
                project_name = f"{owner}_{repo}"
                yield f"data: {json.dumps({'type': 'complete', 'message': '爬取和处理完成！', 'projectName': project_name, 'progress': 100})}\n\n"
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                yield f"data: {json.dumps({'type': 'error', 'message': f'发生错误: {str(e)}'})}\n\n"
        
        response = Response(stream_with_context(generate()), mimetype='text/event-stream')
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['X-Accel-Buffering'] = 'no'
        return response
        
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
            print(f"  - {repo}: {time_range.get('start', '?')} ~ {time_range.get('end', '?')}")
    else:
        print("\n警告: 没有找到数据文件")
        print("请将处理后的数据放入 backend/DataProcessor/data 目录")
    
    print("\n" + "="*60)
    app.run(debug=True, port=5000, host='0.0.0.0')
