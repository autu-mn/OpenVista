"""
按月爬取GitHub仓库数据的主入口
整合所有数据源，按月组织，分离数据用于MaxKB和双塔模型

执行顺序：
1. 爬取指标数据（数字指标）
2. 爬取描述文本（预处理后，上传到知识库）
3. 爬取issue等时序文本
4. 时序文本+时序指标，按照月份时序对齐
"""

import os
import sys
import json
import argparse
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.DataProcessor.monthly_crawler import MonthlyCrawler
from backend.DataProcessor.monthly_data_processor import MonthlyDataProcessor
from backend.DataProcessor.github_text_crawler import OpenDiggerMetrics, GitHubTextCrawler
from backend.DataProcessor.data_completeness_checker import DataCompletenessChecker


def crawl_project_monthly(owner: str, repo: str, max_per_month: int = 50, enable_llm_summary: bool = True, skip_docs: bool = False, resume: bool = True):
    """
    爬取项目的月度数据
    
    Args:
        owner: 仓库所有者
        repo: 仓库名称
        max_per_month: 每月最多爬取的数量
        enable_llm_summary: 是否启用LLM摘要生成
        skip_docs: 是否跳过描述性文档爬取（README、LICENSE、docs等）
    
    Returns:
        输出目录路径（如果数据已存在，返回已存在的目录路径）
    """
    project_name = f"{owner}_{repo}"
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    project_dir = os.path.join(data_dir, project_name)
    
    # 检查数据完整性和是否需要续传
    existing_folder_path = None
    existing_months = []
    existing_monthly_data = {}
    resume_info = None
    
    if resume and os.path.exists(project_dir):
        checker = DataCompletenessChecker(data_dir)
        resume_info = checker.get_resume_info(owner, repo)
        
        if resume_info['needs_resume'] and resume_info['data_path']:
            existing_folder_path = resume_info['data_path']
            missing_months = resume_info.get('missing_months', [])
            
            # 获取已存在的月份（用于传递给爬虫，跳过这些月份）
            checker = DataCompletenessChecker(data_dir)
            completeness = checker.check_project_completeness(owner, repo)
            existing_months = completeness.get('existing_months', [])
            
            # 加载已有数据
            if resume_info['resume_type'] == 'months' and existing_months:
                # 只续传月份，需要加载已有数据
                timeseries_for_model_dir = os.path.join(existing_folder_path, 'timeseries_for_model')
                if os.path.exists(timeseries_for_model_dir):
                    try:
                        # 从 all_months.json 或单个文件加载已有数据
                        all_months_file = os.path.join(timeseries_for_model_dir, 'all_months.json')
                        if os.path.exists(all_months_file):
                            with open(all_months_file, 'r', encoding='utf-8') as f:
                                all_months_data = json.load(f)
                                if isinstance(all_months_data, dict):
                                    # 转换为 monthly_data 格式（只加载已存在的月份）
                                    for month, month_data in all_months_data.items():
                                        if month not in existing_months:
                                            continue  # 跳过缺失的月份，只保留已存在的
                                        # 提取 issues 和 commits
                                        existing_monthly_data[month] = {
                                            'month': month,
                                            'issues': month_data.get('issues', []),
                                            'commits': month_data.get('commits', []),
                                            'releases': month_data.get('releases', [])
                                        }
                    except Exception as e:
                        print(f"  ⚠ 加载已有数据失败: {e}")
            
            print(f"\n{'='*80}")
            print(f"检测到不完整的数据，准备续传")
            print(f"{'='*80}")
            print(f"续传类型: {resume_info['resume_type']}")
            if missing_months:
                print(f"缺失月份: {len(missing_months)} 个月 ({', '.join(missing_months[:5])}{'...' if len(missing_months) > 5 else ''})")
            if existing_months:
                print(f"已有月份: {len(existing_months)} 个月")
            print(f"数据路径: {existing_folder_path}\n")
        elif not resume_info['needs_resume']:
            # 数据完整，直接返回
            if resume_info['data_path']:
                print(f"\n{'='*80}")
                print(f"项目 {owner}/{repo} 的数据已完整")
                print(f"{'='*80}")
                print(f"已存在的数据目录: {resume_info['data_path']}")
                print(f"跳过爬取，直接使用已有数据\n")
                return resume_info['data_path']
    
    # 如果 resume=False 或没有找到不完整数据，检查是否数据已存在（完整检查）
    if not resume_info or (not resume_info['needs_resume'] and not existing_folder_path):
        if os.path.exists(project_dir):
            processed_folders = [
                f for f in os.listdir(project_dir)
                if os.path.isdir(os.path.join(project_dir, f)) and 
                ('monthly_data_' in f or '_processed' in f)
            ]
            
            if processed_folders:
                processed_folders.sort(reverse=True)
                latest_folder = processed_folders[0]
                folder_path = os.path.join(project_dir, latest_folder)
                timeseries_file = os.path.join(folder_path, 'timeseries_data.json')
                timeseries_for_model_dir = os.path.join(folder_path, 'timeseries_for_model')
                has_timeseries_data = False
                
                if os.path.exists(timeseries_file):
                    try:
                        if os.path.getsize(timeseries_file) > 0:
                            has_timeseries_data = True
                    except Exception:
                        pass
                
                if not has_timeseries_data and os.path.exists(timeseries_for_model_dir):
                    try:
                        json_files = [f for f in os.listdir(timeseries_for_model_dir) if f.endswith('.json') and f != 'all_months.json']
                        if len(json_files) > 0:
                            for json_file in json_files[:3]:
                                file_path = os.path.join(timeseries_for_model_dir, json_file)
                                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                                    has_timeseries_data = True
                                    break
                    except Exception as e:
                        print(f"  检查 timeseries_for_model 目录失败: {e}")
                
                if has_timeseries_data:
                    print(f"\n{'='*80}")
                    print(f"项目 {owner}/{repo} 的数据已存在")
                    print(f"{'='*80}")
                    print(f"已存在的数据目录: {folder_path}")
                    print(f"跳过爬取，直接使用已有数据\n")
                    return folder_path
    
    print(f"\n{'='*80}")
    print(f"开始爬取项目: {owner}/{repo}")
    print(f"{'='*80}\n")
    
    # 初始化爬虫和处理器
    monthly_crawler = MonthlyCrawler()
    text_crawler = GitHubTextCrawler()
    
    # ========== 步骤1: 爬取指标数据（数字指标）和仓库信息==========
    print("[1/4] 爬取指标数据和仓库信息...")
    
    # 获取仓库信息和标签（用于面板展示）
    print("  → 获取仓库信息和标签...")
    repo_info_basic = text_crawler.get_repo_info(owner, repo)
    labels = text_crawler.get_labels(owner, repo)
    if repo_info_basic:
        print(f"  ✓ 获取了仓库信息: {repo_info_basic.get('name', '')}")
        description = repo_info_basic.get('description') or '无'
        print(f"    - 描述: {description[:50]}...")
        topics = repo_info_basic.get('topics') or []
        print(f"    - 主题: {', '.join(topics[:5])}")
        print(f"    - 标签: {len(labels) if labels else 0} 个")
    else:
        print("  ⚠ 未能获取仓库信息")
    
    # 获取OpenDigger指标数据
    print("  → 获取OpenDigger数字指标...")
    opendigger = OpenDiggerMetrics()
    opendigger_data, missing_metrics = opendigger.get_metrics(owner, repo)
    print(f"  ✓ 获取了 {len(opendigger_data)} 个OpenDigger指标")
    if missing_metrics:
        print(f"  ⚠ 缺失指标: {', '.join(missing_metrics[:5])}{'...' if len(missing_metrics) > 5 else ''}")
    
    # 生成月份列表（用于后续处理）
    monthly_crawler = MonthlyCrawler()
    months = monthly_crawler.generate_month_list(owner, repo)
    
    # ========== 使用 GitHub API 补齐缺失的指标 ==========
    # 需要补齐的指标: 新增Issue, 关闭Issue, 贡献者, 新增贡献者
    metrics_to_fill = ['新增Issue', '关闭Issue', '贡献者', '新增贡献者']
    need_fill = [m for m in metrics_to_fill if m in missing_metrics]
    
    if need_fill:
        print(f"  → 使用 GitHub API 补齐缺失指标: {', '.join(need_fill)}")
        try:
            from DataProcessor.github_api_metrics import GitHubAPIMetrics
            github_api = GitHubAPIMetrics()
            
            # 补齐 Issue 相关指标
            if '新增Issue' in need_fill or '关闭Issue' in need_fill:
                issues_monthly = github_api.get_monthly_issues_count(owner, repo)
                if '新增Issue' in need_fill and issues_monthly.get('issues_new'):
                    opendigger_data['新增Issue'] = issues_monthly['issues_new']
                    print(f"    ✓ 已补齐 新增Issue ({len(issues_monthly['issues_new'])} 个月)")
                if '关闭Issue' in need_fill and issues_monthly.get('issues_closed'):
                    opendigger_data['关闭Issue'] = issues_monthly['issues_closed']
                    print(f"    ✓ 已补齐 关闭Issue ({len(issues_monthly['issues_closed'])} 个月)")
            
            # 补齐贡献者相关指标
            if '贡献者' in need_fill or '新增贡献者' in need_fill:
                contributors_monthly = github_api.get_monthly_contributors(owner, repo)
                if '贡献者' in need_fill and contributors_monthly.get('contributors'):
                    opendigger_data['贡献者'] = contributors_monthly['contributors']
                    print(f"    ✓ 已补齐 贡献者 ({len(contributors_monthly['contributors'])} 个月)")
                if '新增贡献者' in need_fill and contributors_monthly.get('new_contributors'):
                    opendigger_data['新增贡献者'] = contributors_monthly['new_contributors']
                    print(f"    ✓ 已补齐 新增贡献者 ({len(contributors_monthly['new_contributors'])} 个月)")
        except Exception as e:
            print(f"  ⚠ GitHub API 补齐失败: {str(e)}")
    
    print(f"  ✓ 指标数据准备完成（共 {len(opendigger_data)} 个指标）")
    
    # ========== 步骤2: 爬取描述文本（预处理后，上传到知识库）==========
    static_docs = {}
    static_texts = {}
    
    if skip_docs:
        print("\n[2/4] 跳过描述文本爬取（skip_docs=True）")
    else:
        print("\n[2/4] 爬取描述文本（README、LICENSE、文档等，优化：最多20个文档）...")
        # 使用并发请求提升速度
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        def fetch_static_docs():
            """并发获取静态文档"""
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {
                    'repo_info': executor.submit(text_crawler.get_repo_info, owner, repo),
                    'readme': executor.submit(text_crawler.get_readme, owner, repo),
                    'license': executor.submit(text_crawler.get_license_file, owner, repo),
                    'important_md_files': executor.submit(text_crawler.get_important_md_files, owner, repo, max_files=20),
                    'config_files': executor.submit(text_crawler.get_config_files, owner, repo)
                }
                
                results = {}
                for key, future in futures.items():
                    try:
                        results[key] = future.result(timeout=30)
                    except Exception as e:
                        print(f"  ⚠ 获取{key}失败: {str(e)}")
                        results[key] = None if key != 'important_md_files' else []
                
                # 获取文档文件（限制为35个，但保留重要文档，避免早停）
                # 先获取重要文档，再补充其他文档（搜索多个目录和根目录）
                important_docs = results.get('important_md_files', [])
                remaining_count = max(0, 35 - len(important_docs))
                
                if remaining_count > 0:
                    docs_files = text_crawler.get_docs_files(owner, repo, max_files=remaining_count, max_depth=3)
                    results['docs_files'] = docs_files
                    results['all_doc_files'] = important_docs + docs_files[:remaining_count]
                else:
                    results['docs_files'] = []
                    results['all_doc_files'] = important_docs[:35]
                
                print(f"  ✓ 文档爬取完成: 重要文档 {len(important_docs)} 个 + 其他文档 {len(results.get('docs_files', []))} 个 = 总计 {len(results.get('all_doc_files', []))} 个")
                
                return results
        
        static_docs = fetch_static_docs()
        print(f"  ✓ 获取了静态文档（共 {len(static_docs.get('all_doc_files', []))} 个文档文件）")
        print(f"    - README: {'✓' if static_docs.get('readme') else '✗'}")
        print(f"    - LICENSE: {'✓' if static_docs.get('license') else '✗'}")
        print(f"    - 重要文档: {len(static_docs.get('important_md_files', []))} 个")
        print(f"    - 配置文件: {len(static_docs.get('config_files', []))} 个")
    
    # 初始化LLM客户端（用于摘要生成）
    llm_client = None
    if enable_llm_summary:
        try:
            from backend.Agent.deepseek_client import DeepSeekClient
            llm_client = DeepSeekClient()
            print("  ✓ LLM客户端已初始化（用于摘要生成）")
        except ImportError:
            try:
                from Agent.deepseek_client import DeepSeekClient
                llm_client = DeepSeekClient()
                print("  ✓ LLM客户端已初始化（用于摘要生成）")
            except Exception as e:
                print(f"  ⚠ LLM客户端初始化失败: {str(e)}")
                print("  ℹ 将跳过LLM摘要生成")
        except Exception as e:
            print(f"  ⚠ LLM客户端初始化失败: {str(e)}")
            print("  ℹ 将跳过LLM摘要生成")
    
    processor = MonthlyDataProcessor(llm_client=llm_client, skip_llm_summary=not enable_llm_summary)
    
    # 创建输出目录（如果续传，使用已有目录；否则创建新目录）
    if existing_folder_path and resume_info and resume_info['resume_type'] == 'months':
        # 续传月份数据，使用已有目录
        output_dir = existing_folder_path
        print(f"  → 使用已有数据目录进行续传: {output_dir}")
    else:
        # 创建新目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(
            os.path.dirname(__file__),
            'data',
            f"{owner}_{repo}",
            f"monthly_data_{timestamp}"
        )
        os.makedirs(output_dir, exist_ok=True)
    
    # 提取静态文本并保存到MaxKB（如果不跳过文档）
    if not skip_docs and static_docs:
        static_texts = processor.extract_static_texts(static_docs)
        print("\n  → 保存描述文本并上传到MaxKB...")
        maxkb_dir = processor.save_for_maxkb(static_texts, output_dir)
        processor.upload_to_maxkb(maxkb_dir, owner, repo)
    else:
        static_texts = {}
    
    # ========== 步骤3: 爬取issue等时序文本 ==========
    print("\n[3/4] 爬取Issue/Commit/Release时序文本（已移除PR爬取，Issues只爬Top-3热度）...")
    if existing_months and resume_info and resume_info['resume_type'] == 'months':
        missing_months = resume_info.get('missing_months', [])
        print(f"  → 断点续传模式：已有 {len(existing_months)} 个月份，只爬取缺失的 {len(missing_months)} 个月份")
    print("  → 速率控制: 每次请求延迟0.2秒")
    
    # 准备已有数据（用于合并）
    existing_data_for_crawler = None
    if existing_monthly_data:
        existing_data_for_crawler = {
            'monthly_data': existing_monthly_data
        }
    
    monthly_data_result = monthly_crawler.crawl_all_months(
        owner, repo, 
        max_per_month=max_per_month,
        progress_callback=lambda idx, title, desc, progress: print(f"  [{idx+1}] {title}: {desc}"),
        existing_months=existing_months if existing_months else None,
        existing_data=existing_data_for_crawler
    )
    
    monthly_data = monthly_data_result['monthly_data']
    repo_info = monthly_data_result['repo_info']
    
    if existing_months:
        print(f"  ✓ 合并完成：已有 {len(existing_monthly_data)} 个月 + 新爬取 {len(monthly_data) - len(existing_monthly_data)} 个月 = 总计 {len(monthly_data)} 个月")
    else:
        print(f"  ✓ 爬取了 {len(monthly_data)} 个月的数据")
    
    # ========== 步骤4: 时序文本+时序指标，按照月份时序对齐 ==========
    print("\n[4/4] 时序对齐：合并时序文本和时序指标...")
    # 确保所有19个指标都被包含，缺失的用0填充（用于模型训练）
    complete_opendigger_metrics = processor._ensure_all_metrics(opendigger_data)
    processed_data = processor.process_monthly_data_for_model(monthly_data, complete_opendigger_metrics)
    print(f"  ✓ 已完成时序对齐，共 {len(processed_data)} 个月的数据")
    print(f"  ✓ 所有19个指标已保存（缺失的用0填充，用于模型训练）")
    
    # 保存所有数据
    print("\n  → 保存数据...")
    
    # 保存原始月度数据（确保所有19个指标都被保存，缺失的用0填充）
    # 定义所有19个指标
    all_metrics_config = {
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
    
    # 提取时间范围（从有数据的指标中提取）
    all_months = set()
    for metric_name, metric_data in opendigger_data.items():
        if isinstance(metric_data, dict):
            all_months.update(metric_data.keys())
    
    # 为所有指标创建完整数据，缺失的用0填充（用于模型训练）
    complete_opendigger_metrics = {}
    for metric_display_name, metric_key in all_metrics_config.items():
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
        if raw_data:
            complete_opendigger_metrics[metric_display_name] = raw_data
    
    raw_data_file = os.path.join(output_dir, 'raw_monthly_data.json')
    with open(raw_data_file, 'w', encoding='utf-8') as f:
        json.dump({
            'repo_info': repo_info,
            'monthly_data': monthly_data,
            'opendigger_metrics': complete_opendigger_metrics,  # 使用完整数据（包含0填充）
            'opendigger_metrics_raw': opendigger_data  # 保留原始数据（不含0填充）
        }, f, ensure_ascii=False, indent=2)
    
    # 保存用于双塔模型的数据（时序对齐后的数据）+ 生成总体 AI 摘要
    processor.save_for_model(processed_data, output_dir, repo_info=repo_info)
    
    # 保存元数据（包含仓库信息和标签）
    metadata = {
        'owner': owner,
        'repo': repo,
        'crawl_time': datetime.now().isoformat(),
        'months_count': len(monthly_data),
        'max_per_month': max_per_month,
        'llm_summary_enabled': enable_llm_summary,
        'opendigger_metrics_count': len(opendigger_data),
        'missing_opendigger_metrics': missing_metrics,
        'repo_info': repo_info_basic if 'repo_info_basic' in locals() else None,
        'labels': labels if 'labels' in locals() else []
    }
    
    metadata_file = os.path.join(output_dir, 'metadata.json')
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*80}")
    print("数据爬取和处理完成！")
    print(f"{'='*80}")
    print(f"\n输出目录: {output_dir}")
    print(f"  - 原始数据: raw_monthly_data.json")
    print(f"  - MaxKB文本: text_for_maxkb/")
    print(f"  - 双塔模型数据（时序对齐）: timeseries_for_model/")
    print(f"  - 元数据: metadata.json")
    print()
    
    return output_dir


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='按月爬取GitHub仓库数据')
    parser.add_argument('owner', help='仓库所有者')
    parser.add_argument('repo', help='仓库名称')
    parser.add_argument('--max-per-month', type=int, default=3, help='每月最多爬取的数量（默认3，即top 3）')
    parser.add_argument('--no-llm-summary', action='store_true', help='禁用LLM摘要生成')
    
    args = parser.parse_args()
    
    try:
        output_dir = crawl_project_monthly(
            args.owner,
            args.repo,
            max_per_month=args.max_per_month,
            enable_llm_summary=not args.no_llm_summary
        )
        print(f"\n✓ 成功完成！数据保存在: {output_dir}")
    except Exception as e:
        print(f"\n✗ 爬取失败: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

