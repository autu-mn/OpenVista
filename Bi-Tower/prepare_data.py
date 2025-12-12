"""
数据准备脚本
从 tsa-try 爬取的数据中构建双塔模型的训练集
"""
import os
import sys

# 设置输出编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
import numpy as np
import pandas as pd
from tqdm import tqdm
import argparse

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import config


def load_project_data(project_path):
    """加载单个项目的数据"""
    try:
        model_input_path = os.path.join(project_path, 'model_input.json')
        
        if not os.path.exists(model_input_path):
            return None
        
        with open(model_input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return data
    except Exception as e:
        print(f"  [ERROR] 加载数据失败 {project_path}: {e}")
        return None


def build_samples(project_data, project_name):
    """从单个项目构建训练样本"""
    samples = []
    
    time_axis = project_data['time_axis']
    timeseries_features = pd.DataFrame(project_data['timeseries_features'])
    text_features = project_data.get('text_semantic_features', [])
    
    # 确定目标指标
    target_candidates = ['community_engagement', 'activity', 'openrank']
    target_metric = None
    for candidate in target_candidates:
        if candidate in timeseries_features.columns:
            target_metric = candidate
            break
    
    if target_metric is None:
        print(f"    [WARN] {project_name}: 未找到目标指标")
        return samples
    
    # 获取特征列（排除目标列和月份列）
    feature_cols = [col for col in timeseries_features.columns 
                    if col != target_metric and col != 'month']
    
    # 打印实际特征维度（用于调试）
    actual_feature_dim = len(feature_cols)
    print(f"    实际特征维度: {actual_feature_dim}")
    
    # 滑动窗口构建样本
    min_train_size = config.TIME_WINDOW
    horizon = config.PREDICTION_HORIZON
    
    for i in range(min_train_size, len(time_axis) - horizon):
        # 时序数据 [time_window, features]
        start_idx = i - min_train_size
        end_idx = i
        
        time_series = timeseries_features[feature_cols].iloc[start_idx:end_idx].values.tolist()
        
        # 文本数据（最近3个月）
        text_months = time_axis[max(0, i-3):i]
        text_events = []
        
        for month in text_months:
            month_idx = time_axis.index(month)
            if month_idx < len(text_features):
                month_text = text_features[month_idx]
                
                # 增强描述
                if 'enhanced_description' in month_text:
                    text_events.append(f"{month}: {month_text['enhanced_description'][:100]}")
                
                # Top Issue
                if month_text.get('top_issues'):
                    issue = month_text['top_issues'][0]
                    text_events.append(f"{month}: Issue - {issue.get('title', '')[:50]}")
                
                # Release
                if month_text.get('releases'):
                    release = month_text['releases'][0]
                    text_events.append(f"{month}: Release - {release.get('tag', '')}")
        
        text = "\n".join(text_events) if text_events else "No significant events in recent months."
        
        # 目标值 [horizon]
        target = timeseries_features[target_metric].iloc[i:i+horizon].values.tolist()
        
        # 检查是否有效
        if len(time_series) == min_train_size and len(target) == horizon:
            # 检查NaN
            if not (np.isnan(time_series).any() or np.isnan(target).any()):
                samples.append({
                    'project': project_name,
                    'month': time_axis[i],
                    'time_series': time_series,
                    'text': text,
                    'target': target
                })
    
    return samples


def split_dataset(all_samples):
    """划分数据集"""
    np.random.seed(42)
    np.random.shuffle(all_samples)
    
    n_total = len(all_samples)
    n_train = int(n_total * config.TRAIN_RATIO)
    n_val = int(n_total * config.VAL_RATIO)
    
    train_samples = all_samples[:n_train]
    val_samples = all_samples[n_train:n_train+n_val]
    test_samples = all_samples[n_train+n_val:]
    
    return {
        'train': train_samples,
        'val': val_samples,
        'test': test_samples
    }


def prepare_data(num_projects=None, force_crawl=False):
    """准备训练数据"""
    print("\n" + "="*60)
    print("准备双塔模型训练数据")
    print("="*60)
    
    # 1. 查找已爬取的项目
    tsa_data_dir = os.path.join(os.path.dirname(config.BASE_DIR), 'tsa-try', 'data')
    
    if not os.path.exists(tsa_data_dir):
        print(f"\n[ERROR] 数据目录不存在: {tsa_data_dir}")
        print("请先运行 tsa-try/crawl_complete_data.py 爬取数据")
        return False
    
    # 查找所有项目文件夹
    project_dirs = [d for d in os.listdir(tsa_data_dir) 
                    if os.path.isdir(os.path.join(tsa_data_dir, d)) and '_' in d]
    
    if num_projects:
        project_dirs = project_dirs[:num_projects]
    
    print(f"\n[1] 找到 {len(project_dirs)} 个项目:")
    for proj in project_dirs:
        print(f"  - {proj}")
    
    # 2. 加载所有项目数据
    print(f"\n[2] 加载项目数据...")
    all_samples = []
    
    for proj_dir in tqdm(project_dirs, desc="加载项目"):
        proj_path = os.path.join(tsa_data_dir, proj_dir)
        proj_data = load_project_data(proj_path)
        
        if proj_data is None:
            continue
        
        # 构建样本
        samples = build_samples(proj_data, proj_dir)
        all_samples.extend(samples)
    
    if len(all_samples) == 0:
        print(f"\n[ERROR] 未能构建任何样本")
        return False
    
    print(f"\n  ✓ 共构建 {len(all_samples)} 个样本")
    
    # 3. 划分数据集
    print(f"\n[3] 划分数据集...")
    dataset = split_dataset(all_samples)
    
    print(f"  训练集: {len(dataset['train'])} 样本 ({len(dataset['train'])/len(all_samples)*100:.1f}%)")
    print(f"  验证集: {len(dataset['val'])} 样本 ({len(dataset['val'])/len(all_samples)*100:.1f}%)")
    print(f"  测试集: {len(dataset['test'])} 样本 ({len(dataset['test'])/len(all_samples)*100:.1f}%)")
    
    # 4. 保存数据
    output_file = os.path.join(config.PROCESSED_DATA_DIR, 'dataset.json')
    print(f"\n[4] 保存数据到: {output_file}")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)
    
    # 5. 统计信息
    # 检测实际特征维度
    if all_samples:
        actual_dim = len(all_samples[0]['time_series'][0])
        print(f"\n[5] 数据统计:")
        print(f"  项目数量: {len(project_dirs)}")
        print(f"  总样本数: {len(all_samples)}")
        print(f"  时序窗口: {config.TIME_WINDOW} 个月")
        print(f"  预测窗口: {config.PREDICTION_HORIZON} 个月")
        print(f"  配置特征维度: {config.TIME_FEATURES}")
        print(f"  实际特征维度: {actual_dim}")
        
        # 更新配置
        if actual_dim != config.TIME_FEATURES:
            print(f"\n  [WARN] 特征维度不匹配！")
            print(f"  将自动更新配置: {config.TIME_FEATURES} -> {actual_dim}")
            config.TIME_FEATURES = actual_dim
            
            # 保存实际维度到数据集
            dataset['feature_dim'] = actual_dim
    
    # 检查第一个样本
    sample = dataset['train'][0]
    print(f"\n  样本示例:")
    print(f"    项目: {sample['project']}")
    print(f"    月份: {sample['month']}")
    print(f"    时序形状: {np.array(sample['time_series']).shape}")
    print(f"    文本长度: {len(sample['text'])} 字符")
    print(f"    目标值: {sample['target']}")
    print(f"    文本预览: {sample['text'][:200]}...")
    
    print(f"\n{'='*60}")
    print("✓ 数据准备完成！")
    print(f"{'='*60}\n")
    
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='准备双塔模型训练数据')
    parser.add_argument('--num_projects', type=int, default=None,
                        help='使用的项目数量（默认使用所有）')
    parser.add_argument('--force_crawl', action='store_true',
                        help='是否强制重新爬取数据')
    
    args = parser.parse_args()
    
    success = prepare_data(
        num_projects=args.num_projects,
        force_crawl=args.force_crawl
    )
    
    if not success:
        sys.exit(1)

