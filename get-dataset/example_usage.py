#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据集生成脚本使用示例

演示如何使用 generate_training_dataset.py 生成训练数据集
"""

import os
import sys

# 添加脚本路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from generate_training_dataset import DatasetGenerator, batch_generate_dataset

def test_single_repo():
    """测试单个仓库的数据生成"""
    print("="*80)
    print("测试单个仓库数据生成")
    print("="*80)
    
    generator = DatasetGenerator(
        max_commits_per_month=30,
        max_issues_per_month=50
    )
    
    # 测试一个知名仓库
    owner = "facebook"
    repo = "react"
    
    samples = generator.process_repo(owner, repo)
    
    if samples:
        print(f"\n✓ 成功生成 {len(samples)} 个训练样本")
        print(f"\n第一个样本预览:")
        print(f"  Repo: {samples[0]['Repo']}")
        print(f"  WindowStart: {samples[0]['WindowStart']}")
        print(f"  WindowEnd: {samples[0]['WindowEnd']}")
        print(f"  HistLen: {samples[0]['HistLen']}")
        print(f"  PredLen: {samples[0]['PredLen']}")
        print(f"  Hist shape: {len(samples[0]['Hist'])} months × {len(samples[0]['Hist'][0])} metrics")
        print(f"  TextData months: {len(samples[0]['TextData'])}")
    else:
        print("\n✗ 未能生成样本")


def test_batch_small():
    """测试小批量生成（用于验证功能）"""
    print("="*80)
    print("测试小批量数据生成（5个仓库）")
    print("="*80)
    
    batch_generate_dataset(
        count=5,
        max_commits_per_month=30,
        max_issues_per_month=50,
        resume=False,
        delay=2.0
    )


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='数据集生成示例')
    parser.add_argument(
        '--test-single',
        action='store_true',
        help='测试单个仓库'
    )
    parser.add_argument(
        '--test-batch',
        action='store_true',
        help='测试小批量生成（5个仓库）'
    )
    
    args = parser.parse_args()
    
    if args.test_single:
        test_single_repo()
    elif args.test_batch:
        test_batch_small()
    else:
        print("请指定测试模式:")
        print("  --test-single: 测试单个仓库")
        print("  --test-batch: 测试小批量生成")
        print("\n示例:")
        print("  python example_usage.py --test-single")
        print("  python example_usage.py --test-batch")

