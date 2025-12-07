"""
模块1（LLM辅助增强器）完整功能测试
测试内容：
1. 文本数据爬取（按月对齐）
2. 单月数据增强
3. 趋势识别增强
4. 关键点增强
5. 语义特征提取
6. 整体总结生成
"""

import os
import sys
import json
from datetime import datetime

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from LLM2TSA.text_crawler import TextTimeSeriesCrawler
from LLM2TSA.enhancer import TimeSeriesEnhancer


def load_existing_timeseries(repo_key: str) -> dict:
    """加载已有的时序数据"""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                           'DataProcessor', 'data')
    
    # 查找项目目录
    repo_dir = repo_key.replace('/', '_')
    project_path = os.path.join(data_dir, repo_dir)
    
    if not os.path.exists(project_path):
        print(f"[ERROR] 未找到项目数据: {project_path}")
        return {}
    
    # 查找processed目录
    processed_dirs = [d for d in os.listdir(project_path) if '_processed' in d]
    if not processed_dirs:
        print(f"[ERROR] 未找到处理后的数据目录")
        return {}
    
    # 使用最新的processed目录
    processed_dir = sorted(processed_dirs)[-1]
    timeseries_path = os.path.join(project_path, processed_dir, 'timeseries_data.json')
    
    if not os.path.exists(timeseries_path):
        print(f"[ERROR] 未找到时序数据文件: {timeseries_path}")
        return {}
    
    with open(timeseries_path, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
    
    # 转换为按月组织的格式
    timeseries_data = {}
    
    # 提取所有日期
    all_dates = set()
    for metric_name, metric_data in raw_data.items():
        if isinstance(metric_data, dict) and 'raw' in metric_data:
            all_dates.update(metric_data['raw'].keys())
    
    # 按月组织
    for date in sorted(all_dates):
        timeseries_data[date] = {}
        for metric_name, metric_data in raw_data.items():
            if isinstance(metric_data, dict) and 'raw' in metric_data:
                value = metric_data['raw'].get(date)
                # 简化指标名称
                simple_name = metric_name.replace('opendigger_', '').replace('github_api_', '')
                timeseries_data[date][simple_name] = value
    
    print(f"[OK] 加载时序数据: {len(timeseries_data)} 个月")
    return timeseries_data


def test_module1_complete():
    """测试模块1完整功能"""
    print("=" * 60)
    print("模块1（LLM辅助增强器）完整功能测试")
    print("=" * 60)
    
    # 配置
    owner = "X-lab2017"
    repo = "open-digger"
    repo_key = f"{owner}/{repo}"
    
    # ========== 第一步：加载现有时序数据 ==========
    print("\n" + "=" * 60)
    print("第一步：加载现有时序数据")
    print("=" * 60)
    
    timeseries_data = load_existing_timeseries(repo_key)
    if not timeseries_data:
        print("[ERROR] 无法加载时序数据，测试终止")
        return
    
    time_axis = sorted(timeseries_data.keys())
    print(f"时间范围: {time_axis[0]} 至 {time_axis[-1]}")
    
    # 打印部分数据示例
    print("\n数据示例（前3个月）:")
    for month in time_axis[:3]:
        print(f"  {month}: {timeseries_data[month]}")
    
    # ========== 第二步：爬取文本时序数据（按月对齐） ==========
    print("\n" + "=" * 60)
    print("第二步：爬取文本时序数据（按月对齐）")
    print("=" * 60)
    
    # 爬取完整时间轴的所有数据
    test_time_axis = time_axis  # 使用完整时间轴
    print(f"爬取时间范围: {test_time_axis[0]} 至 {test_time_axis[-1]} (共{len(test_time_axis)}个月)")
    print(f"[注意] 这将进行 {len(test_time_axis)} 次API调用，可能需要较长时间...")
    
    crawler = TextTimeSeriesCrawler()
    text_timeseries = crawler.crawl_text_timeseries(owner, repo, test_time_axis)
    
    # 打印文本数据示例
    print("\n文本数据示例:")
    for month in test_time_axis[:2]:
        data = text_timeseries.get(month, {})
        print(f"\n  {month}:")
        if data.get('hottest_issue'):
            print(f"    Issue: {data['hottest_issue']['title'][:50]}...")
        else:
            print(f"    Issue: 无")
        if data.get('hottest_pr'):
            print(f"    PR: {data['hottest_pr']['title'][:50]}...")
        else:
            print(f"    PR: 无")
    
    # ========== 第三步：数据增强处理 ==========
    print("\n" + "=" * 60)
    print("第三步：数据增强处理")
    print("=" * 60)
    
    # 使用完整数据
    test_timeseries = {month: timeseries_data[month] for month in test_time_axis}
    
    enhancer = TimeSeriesEnhancer(use_cache=True)
    
    # 3.1 单月数据增强
    print("\n--- 3.1 单月数据增强 ---")
    test_month = test_time_axis[-1]
    month_desc = enhancer.enhance_month(
        test_month, 
        test_timeseries[test_month],
        text_timeseries.get(test_month, {})
    )
    print(f"  {test_month}月增强描述:")
    print(f"  {month_desc}")
    
    # 3.2 趋势识别增强
    print("\n--- 3.2 趋势识别增强 ---")
    trends = enhancer.detect_trends(test_timeseries, text_timeseries)
    print(f"  识别到 {len(trends)} 个趋势:")
    for trend in trends:
        print(f"    - {trend['period']}: {trend['type']}")
        print(f"      {trend['description'][:80]}...")
    
    # 3.3 关键点增强
    print("\n--- 3.3 关键点增强 ---")
    key_points = enhancer.enhance_key_points(test_timeseries, text_timeseries)
    print(f"  识别到 {len(key_points)} 个关键点:")
    for kp in key_points:
        print(f"    - {kp['date']} ({kp['type']}): {kp['value']:.2f}")
        print(f"      {kp['explanation'][:60]}...")
    
    # 3.4 语义特征提取
    print("\n--- 3.4 语义特征提取 ---")
    features = enhancer.extract_semantic_features(test_timeseries, text_timeseries)
    print(f"  语义特征:")
    print(f"    - 增长率: {features.get('growth_rate')} ({features.get('growth_percent', 0):.1f}%)")
    print(f"    - 稳定性: {features.get('stability')} (CV={features.get('cv', 0):.3f})")
    print(f"    - 文本活跃度: {features.get('text_activity')} ({features.get('text_coverage', 0):.1f}%)")
    print(f"    - 整体状态: {features.get('overall_status')}")
    
    # 3.5 整体总结
    print("\n--- 3.5 整体总结 ---")
    summary = enhancer.generate_summary(test_timeseries, text_timeseries, trends, key_points, features)
    print(f"  整体总结:")
    print(f"  {summary}")
    
    # ========== 第四步：完整增强流程 ==========
    print("\n" + "=" * 60)
    print("第四步：完整增强流程")
    print("=" * 60)
    
    full_result = enhancer.enhance_all(test_timeseries, text_timeseries)
    
    # ========== 第五步：保存结果 ==========
    print("\n" + "=" * 60)
    print("第五步：保存结果")
    print("=" * 60)
    
    output_dir = os.path.join(os.path.dirname(__file__), 'test_output')
    os.makedirs(output_dir, exist_ok=True)
    
    output_file = os.path.join(output_dir, f"{owner}_{repo}_enhanced.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(full_result, f, ensure_ascii=False, indent=2)
    
    print(f"[OK] 结果已保存: {output_file}")
    
    # ========== 测试结果汇总 ==========
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    print(f"[OK] 时序数据: {len(test_timeseries)} 个月")
    print(f"[OK] 文本数据: {len(text_timeseries)} 个月")
    print(f"[OK] 单月增强: {len(full_result['monthly_data'])} 个月")
    print(f"[OK] 趋势识别: {len(full_result['trends'])} 个")
    print(f"[OK] 关键点: {len(full_result['key_points'])} 个")
    print(f"[OK] 语义特征: {len(full_result['semantic_features'])} 项")
    print(f"[OK] 整体总结: {len(full_result['summary'])} 字符")
    print("\n" + "=" * 60)
    print("模块1测试完成!")
    print("=" * 60)


if __name__ == '__main__':
    test_module1_complete()

