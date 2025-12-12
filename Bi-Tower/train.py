"""
训练脚本
"""
import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import ReduceLROnPlateau
import os
import sys
import json
import time
import argparse
from tqdm import tqdm

from config import config
from model import create_model
from dataset import create_dataloaders


class Trainer:
    """训练器"""
    
    def __init__(self, model, train_loader, val_loader, device='cuda'):
        self.model = model.to(device)
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.device = device
        
        # 优化器
        self.optimizer = optim.Adam(
            self.model.parameters(),
            lr=config.LEARNING_RATE,
            weight_decay=config.WEIGHT_DECAY
        )
        
        # 学习率调度器
        self.scheduler = ReduceLROnPlateau(
            self.optimizer,
            mode='min',
            factor=config.LR_FACTOR,
            patience=config.LR_PATIENCE,
            verbose=True
        )
        
        # 损失函数
        self.criterion = nn.MSELoss()
        
        # 记录
        self.train_losses = []
        self.val_losses = []
        self.best_val_loss = float('inf')
        self.patience_counter = 0
    
    def train_epoch(self, epoch):
        """训练一个epoch"""
        self.model.train()
        total_loss = 0
        n_batches = len(self.train_loader)
        
        pbar = tqdm(self.train_loader, desc=f'Epoch {epoch+1}/{config.NUM_EPOCHS}')
        
        for batch_idx, batch in enumerate(pbar):
            # 移动到设备
            time_series = batch['time_series'].to(self.device)
            input_ids = batch['input_ids'].to(self.device)
            attention_mask = batch['attention_mask'].to(self.device)
            target = batch['target'].to(self.device)
            
            # 前向传播
            predictions = self.model(time_series, input_ids, attention_mask)
            loss = self.criterion(predictions, target)
            
            # 反向传播
            self.optimizer.zero_grad()
            loss.backward()
            
            # 梯度裁剪
            torch.nn.utils.clip_grad_norm_(
                self.model.parameters(),
                config.GRADIENT_CLIP
            )
            
            self.optimizer.step()
            
            # 记录
            total_loss += loss.item()
            avg_loss = total_loss / (batch_idx + 1)
            
            pbar.set_postfix({'loss': f'{avg_loss:.4f}'})
        
        avg_loss = total_loss / n_batches
        return avg_loss
    
    def validate(self):
        """验证"""
        self.model.eval()
        total_loss = 0
        
        with torch.no_grad():
            for batch in self.val_loader:
                # 移动到设备
                time_series = batch['time_series'].to(self.device)
                input_ids = batch['input_ids'].to(self.device)
                attention_mask = batch['attention_mask'].to(self.device)
                target = batch['target'].to(self.device)
                
                # 前向传播
                predictions = self.model(time_series, input_ids, attention_mask)
                loss = self.criterion(predictions, target)
                
                total_loss += loss.item()
        
        avg_loss = total_loss / len(self.val_loader)
        return avg_loss
    
    def save_checkpoint(self, epoch, val_loss, is_best=False):
        """保存检查点"""
        checkpoint = {
            'epoch': epoch,
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'val_loss': val_loss,
            'train_losses': self.train_losses,
            'val_losses': self.val_losses,
            'config': config.__dict__
        }
        
        # 保存最新模型
        checkpoint_path = os.path.join(config.CHECKPOINT_DIR, 'last_model.pt')
        torch.save(checkpoint, checkpoint_path)
        
        # 保存最佳模型
        if is_best:
            best_path = os.path.join(config.CHECKPOINT_DIR, 'best_model.pt')
            torch.save(checkpoint, best_path)
            print(f"  ✓ 保存最佳模型 (val_loss={val_loss:.4f})")
    
    def train(self):
        """完整训练流程"""
        print(f"\n{'='*60}")
        print("开始训练")
        print(f"{'='*60}")
        print(f"  设备: {self.device}")
        print(f"  训练样本: {len(self.train_loader.dataset)}")
        print(f"  验证样本: {len(self.val_loader.dataset)}")
        print(f"  Batch大小: {config.BATCH_SIZE}")
        print(f"  学习率: {config.LEARNING_RATE}")
        print(f"  训练轮数: {config.NUM_EPOCHS}")
        print(f"{'='*60}\n")
        
        start_time = time.time()
        
        for epoch in range(config.NUM_EPOCHS):
            # 训练
            train_loss = self.train_epoch(epoch)
            self.train_losses.append(train_loss)
            
            # 验证
            val_loss = self.validate()
            self.val_losses.append(val_loss)
            
            # 学习率调度
            self.scheduler.step(val_loss)
            
            # 打印
            print(f"\n  Epoch {epoch+1}/{config.NUM_EPOCHS}")
            print(f"    训练损失: {train_loss:.4f}")
            print(f"    验证损失: {val_loss:.4f}")
            print(f"    学习率: {self.optimizer.param_groups[0]['lr']:.6f}")
            
            # 保存检查点
            is_best = val_loss < self.best_val_loss
            if is_best:
                self.best_val_loss = val_loss
                self.patience_counter = 0
            else:
                self.patience_counter += 1
            
            if (epoch + 1) % config.SAVE_INTERVAL == 0:
                self.save_checkpoint(epoch, val_loss, is_best)
            
            # 早停
            if self.patience_counter >= config.EARLY_STOPPING_PATIENCE:
                print(f"\n  早停: 验证损失连续{config.EARLY_STOPPING_PATIENCE}轮未改善")
                break
        
        # 训练结束
        elapsed_time = time.time() - start_time
        
        print(f"\n{'='*60}")
        print("训练完成")
        print(f"{'='*60}")
        print(f"  总耗时: {elapsed_time/60:.1f} 分钟")
        print(f"  最佳验证损失: {self.best_val_loss:.4f}")
        print(f"  最终训练损失: {train_loss:.4f}")
        print(f"  最终验证损失: {val_loss:.4f}")
        print(f"{'='*60}\n")
        
        # 保存训练历史
        history = {
            'train_losses': self.train_losses,
            'val_losses': self.val_losses,
            'best_val_loss': self.best_val_loss,
            'elapsed_time': elapsed_time,
            'num_epochs': len(self.train_losses)
        }
        
        history_path = os.path.join(config.RESULTS_DIR, 'training_history.json')
        with open(history_path, 'w') as f:
            json.dump(history, f, indent=2)
        
        print(f"  训练历史已保存: {history_path}")


def main(args):
    """主函数"""
    
    # 检查数据
    data_file = os.path.join(config.PROCESSED_DATA_DIR, 'dataset.json')
    if not os.path.exists(data_file):
        print(f"[ERROR] 数据文件不存在: {data_file}")
        print("请先运行 prepare_data.py 准备数据")
        sys.exit(1)
    
    # 设置设备
    device = args.device
    if device == 'cuda' and not torch.cuda.is_available():
        print(f"[WARN] CUDA不可用，切换到CPU")
        device = 'cpu'
    
    config.DEVICE = device
    
    # 创建数据加载器
    print("加载数据...")
    
    # 先检查数据集中的特征维度
    with open(data_file, 'r', encoding='utf-8') as f:
        import json
        data = json.load(f)
        if 'feature_dim' in data:
            actual_dim = data['feature_dim']
            print(f"  检测到实际特征维度: {actual_dim}")
            if actual_dim != config.TIME_FEATURES:
                print(f"  更新配置: {config.TIME_FEATURES} -> {actual_dim}")
                config.TIME_FEATURES = actual_dim
    
    train_loader, val_loader, test_loader = create_dataloaders(
        data_file,
        batch_size=args.batch_size
    )
    
    # 创建模型
    print("\n创建模型...")
    model = create_model(config)
    
    # 创建训练器
    trainer = Trainer(model, train_loader, val_loader, device=device)
    
    # 训练
    trainer.train()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='训练双塔模型')
    parser.add_argument('--config', type=str, default='balanced',
                        choices=['lightweight', 'balanced', 'high_performance', 'codebert'],
                        help='模型配置')
    parser.add_argument('--device', type=str, default='cuda',
                        choices=['cuda', 'cpu'],
                        help='训练设备')
    parser.add_argument('--batch_size', type=int, default=None,
                        help='Batch大小（覆盖配置）')
    parser.add_argument('--epochs', type=int, default=None,
                        help='训练轮数（覆盖配置）')
    parser.add_argument('--lr', type=float, default=None,
                        help='学习率（覆盖配置）')
    
    args = parser.parse_args()
    
    # 加载配置
    from config_variants import get_config
    config = get_config(args.config)
    
    # 覆盖配置
    if args.batch_size:
        config.BATCH_SIZE = args.batch_size
    if args.epochs:
        config.NUM_EPOCHS = args.epochs
    if args.lr:
        config.LEARNING_RATE = args.lr
    
    main(args)

