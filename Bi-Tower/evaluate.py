"""
评估脚本
"""
import torch
import numpy as np
import os
import sys
import json
import argparse
from tqdm import tqdm
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from config import config
from model import create_model
from dataset import create_dataloaders


def compute_metrics(predictions, targets):
    """计算评估指标"""
    mae = mean_absolute_error(targets, predictions)
    rmse = np.sqrt(mean_squared_error(targets, predictions))
    
    # MAPE
    mask = targets != 0
    if mask.sum() > 0:
        mape = np.mean(np.abs((targets[mask] - predictions[mask]) / targets[mask])) * 100
    else:
        mape = 0
    
    # R2
    r2 = r2_score(targets, predictions)
    
    return {
        'mae': mae,
        'rmse': rmse,
        'mape': mape,
        'r2': r2
    }


def evaluate_model(model, data_loader, device='cuda'):
    """评估模型"""
    model.eval()
    
    all_predictions = []
    all_targets = []
    all_projects = []
    all_months = []
    
    with torch.no_grad():
        for batch in tqdm(data_loader, desc='评估中'):
            # 移动到设备
            time_series = batch['time_series'].to(device)
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            target = batch['target'].cpu().numpy()
            
            # 前向传播
            predictions = model(time_series, input_ids, attention_mask)
            predictions = predictions.cpu().numpy()
            
            all_predictions.append(predictions)
            all_targets.append(target)
            all_projects.extend(batch['project'])
            all_months.extend(batch['month'])
    
    # 拼接
    all_predictions = np.concatenate(all_predictions, axis=0)
    all_targets = np.concatenate(all_targets, axis=0)
    
    return all_predictions, all_targets, all_projects, all_months


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
    
    # 加载数据
    print("加载数据...")
    data_file = os.path.join(config.PROCESSED_DATA_DIR, 'dataset.json')
    train_loader, val_loader, test_loader = create_dataloaders(data_file)
    
    # 创建模型
    print("\n加载模型...")
    model = create_model(config)
    
    # 加载检查点
    checkpoint = torch.load(args.checkpoint, map_location=device)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.to(device)
    
    print(f"  ✓ 从 epoch {checkpoint['epoch']+1} 加载")
    print(f"  ✓ 验证损失: {checkpoint['val_loss']:.4f}")
    
    # 评估测试集
    print(f"\n{'='*60}")
    print("评估测试集")
    print(f"{'='*60}\n")
    
    predictions, targets, projects, months = evaluate_model(model, test_loader, device)
    
    # 计算指标
    # 整体指标
    print("整体性能:")
    overall_metrics = compute_metrics(predictions.flatten(), targets.flatten())
    for metric_name, value in overall_metrics.items():
        print(f"  {metric_name.upper()}: {value:.4f}")
    
    # 每个horizon的指标
    print(f"\n分horizon性能:")
    for h in range(config.PREDICTION_HORIZON):
        horizon_metrics = compute_metrics(predictions[:, h], targets[:, h])
        print(f"  Horizon {h+1}:")
        for metric_name, value in horizon_metrics.items():
            print(f"    {metric_name.upper()}: {value:.4f}")
    
    # 保存结果
    results = {
        'overall': overall_metrics,
        'per_horizon': {
            f'horizon_{h+1}': compute_metrics(predictions[:, h], targets[:, h])
            for h in range(config.PREDICTION_HORIZON)
        },
        'checkpoint': args.checkpoint,
        'num_samples': len(predictions)
    }
    
    results_path = os.path.join(config.RESULTS_DIR, 'evaluation_results.json')
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"✓ 评估完成")
    print(f"  结果已保存: {results_path}")
    print(f"{'='*60}\n")
    
    # 保存预测详情（可选）
    if args.save_predictions:
        predictions_path = os.path.join(config.RESULTS_DIR, 'predictions.json')
        
        details = []
        for i in range(len(predictions)):
            details.append({
                'project': projects[i],
                'month': months[i],
                'prediction': predictions[i].tolist(),
                'target': targets[i].tolist()
            })
        
        with open(predictions_path, 'w') as f:
            json.dump(details, f, indent=2)
        
        print(f"  预测详情已保存: {predictions_path}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='评估双塔模型')
    parser.add_argument('--checkpoint', type=str,
                        default=os.path.join(config.CHECKPOINT_DIR, 'best_model.pt'),
                        help='检查点路径')
    parser.add_argument('--device', type=str, default='cuda',
                        choices=['cuda', 'cpu'],
                        help='评估设备')
    parser.add_argument('--save_predictions', action='store_true',
                        help='是否保存预测详情')
    
    args = parser.parse_args()
    
    main(args)

