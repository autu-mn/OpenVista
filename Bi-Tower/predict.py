"""
预测脚本 - 对单个项目进行预测
"""
import torch
import numpy as np
import os
import sys
import json
import argparse
from transformers import DistilBertTokenizer

from config import config
from model import create_model


def load_project_data(project_name):
    """加载项目数据"""
    # 查找项目数据
    tsa_data_dir = os.path.join(os.path.dirname(config.BASE_DIR), 'tsa-try', 'data')
    project_path = os.path.join(tsa_data_dir, project_name.replace('/', '_'))
    
    if not os.path.exists(project_path):
        print(f"[ERROR] 项目数据不存在: {project_path}")
        return None
    
    model_input_path = os.path.join(project_path, 'model_input.json')
    with open(model_input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return data


def prepare_input(project_data, tokenizer):
    """准备模型输入"""
    time_axis = project_data['time_axis']
    timeseries_features = project_data['timeseries_features']
    text_features = project_data.get('text_semantic_features', [])
    
    # 使用最近的数据
    if len(timeseries_features) < config.TIME_WINDOW:
        print(f"[ERROR] 数据不足，至少需要 {config.TIME_WINDOW} 个月")
        return None
    
    # 时序数据（最近12个月）
    recent_data = timeseries_features[-config.TIME_WINDOW:]
    
    # 提取特征
    feature_cols = [col for col in recent_data[0].keys() 
                    if col not in ['month', 'community_engagement', 'activity', 'openrank']]
    
    time_series = []
    for month_data in recent_data:
        features = [month_data.get(col, 0) for col in feature_cols]
        time_series.append(features)
    
    time_series = torch.tensor([time_series], dtype=torch.float32)
    
    # 文本数据（最近3个月）
    recent_months = time_axis[-3:]
    text_events = []
    
    for month in recent_months:
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
    
    # Tokenize
    encoding = tokenizer(
        text,
        add_special_tokens=True,
        max_length=config.TEXT_MAX_LENGTH,
        padding='max_length',
        truncation=True,
        return_tensors='pt'
    )
    
    input_ids = encoding['input_ids']
    attention_mask = encoding['attention_mask']
    
    return {
        'time_series': time_series,
        'input_ids': input_ids,
        'attention_mask': attention_mask,
        'text': text,
        'recent_months': recent_months
    }


def predict(model, inputs, device='cuda'):
    """执行预测"""
    model.eval()
    
    with torch.no_grad():
        time_series = inputs['time_series'].to(device)
        input_ids = inputs['input_ids'].to(device)
        attention_mask = inputs['attention_mask'].to(device)
        
        predictions = model(time_series, input_ids, attention_mask)
        predictions = predictions.cpu().numpy()[0]
    
    return predictions


def main(args):
    """主函数"""
    
    # 检查检查点
    if not os.path.exists(args.checkpoint):
        print(f"[ERROR] 检查点不存在: {args.checkpoint}")
        sys.exit(1)
    
    # 设置设备
    device = args.device
    if device == 'cuda' and not torch.cuda.is_available():
        print(f"[WARN] CUDA不可用，切换到CPU")
        device = 'cpu'
    
    print(f"\n{'='*60}")
    print(f"双塔模型预测 - {args.project}")
    print(f"{'='*60}\n")
    
    # 加载项目数据
    print("[1] 加载项目数据...")
    project_data = load_project_data(args.project)
    if project_data is None:
        sys.exit(1)
    
    print(f"  ✓ 项目: {project_data['repo_info']['full_name']}")
    print(f"  ✓ 数据范围: {project_data['time_axis'][0]} ~ {project_data['time_axis'][-1]}")
    
    # 准备输入
    print("\n[2] 准备模型输入...")
    tokenizer = DistilBertTokenizer.from_pretrained(config.TEXT_MODEL_NAME)
    inputs = prepare_input(project_data, tokenizer)
    
    if inputs is None:
        sys.exit(1)
    
    print(f"  ✓ 时序数据: {inputs['time_series'].shape}")
    print(f"  ✓ 文本长度: {len(inputs['text'])} 字符")
    print(f"  ✓ 最近月份: {inputs['recent_months']}")
    
    # 加载模型
    print("\n[3] 加载模型...")
    model = create_model(config)
    checkpoint = torch.load(args.checkpoint, map_location=device)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.to(device)
    
    print(f"  ✓ 从 epoch {checkpoint['epoch']+1} 加载")
    
    # 预测
    print("\n[4] 执行预测...")
    predictions = predict(model, inputs, device)
    
    # 显示结果
    print(f"\n{'='*60}")
    print("预测结果")
    print(f"{'='*60}")
    
    for i, pred in enumerate(predictions):
        print(f"  未来第 {i+1} 个月: {pred:.2f}")
    
    # 显示文本信息
    if args.show_text:
        print(f"\n{'='*60}")
        print("文本事件")
        print(f"{'='*60}")
        print(inputs['text'])
    
    print(f"\n{'='*60}\n")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='使用双塔模型预测')
    parser.add_argument('--project', type=str, required=True,
                        help='项目名称（如 X-lab2017/open-digger）')
    parser.add_argument('--checkpoint', type=str,
                        default=os.path.join(config.CHECKPOINT_DIR, 'best_model.pt'),
                        help='检查点路径')
    parser.add_argument('--device', type=str, default='cuda',
                        choices=['cuda', 'cpu'],
                        help='预测设备')
    parser.add_argument('--show_text', action='store_true',
                        help='是否显示文本事件')
    
    args = parser.parse_args()
    
    main(args)

