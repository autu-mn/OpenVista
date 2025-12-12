"""
数据集加载器
"""
import torch
from torch.utils.data import Dataset, DataLoader
from transformers import DistilBertTokenizer
import pandas as pd
import numpy as np
import json
import os
from config import config


class TimeSeriesTextDataset(Dataset):
    """时序-文本联合数据集"""
    
    def __init__(self, data_file, tokenizer, split='train'):
        """
        Args:
            data_file: 处理后的数据文件路径
            tokenizer: 文本tokenizer
            split: 'train', 'val', or 'test'
        """
        self.tokenizer = tokenizer
        self.split = split
        
        # 加载数据
        with open(data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.samples = data[split]
        print(f"  [{split}] 加载 {len(self.samples)} 个样本")
    
    def __len__(self):
        return len(self.samples)
    
    def __getitem__(self, idx):
        sample = self.samples[idx]
        
        # 时序数据 [time_window, features]
        time_series = torch.tensor(sample['time_series'], dtype=torch.float32)
        
        # 文本数据
        text = sample['text']
        
        # Tokenize
        encoding = self.tokenizer(
            text,
            add_special_tokens=True,
            max_length=config.TEXT_MAX_LENGTH,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )
        
        input_ids = encoding['input_ids'].squeeze(0)
        attention_mask = encoding['attention_mask'].squeeze(0)
        
        # 目标值 [horizon]
        target = torch.tensor(sample['target'], dtype=torch.float32)
        
        return {
            'time_series': time_series,
            'input_ids': input_ids,
            'attention_mask': attention_mask,
            'target': target,
            'project': sample.get('project', 'unknown'),
            'month': sample.get('month', 'unknown')
        }


def create_dataloaders(data_file, batch_size=16, num_workers=0):
    """创建数据加载器"""
    
    # 加载tokenizer
    tokenizer = DistilBertTokenizer.from_pretrained(config.TEXT_MODEL_NAME)
    
    # 创建数据集
    train_dataset = TimeSeriesTextDataset(data_file, tokenizer, split='train')
    val_dataset = TimeSeriesTextDataset(data_file, tokenizer, split='val')
    test_dataset = TimeSeriesTextDataset(data_file, tokenizer, split='test')
    
    # 创建数据加载器
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=True if config.DEVICE == 'cuda' else False
    )
    
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=True if config.DEVICE == 'cuda' else False
    )
    
    test_loader = DataLoader(
        test_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=True if config.DEVICE == 'cuda' else False
    )
    
    return train_loader, val_loader, test_loader


if __name__ == '__main__':
    # 测试数据加载
    print("测试数据加载器...")
    
    # 假设数据已准备好
    data_file = os.path.join(config.PROCESSED_DATA_DIR, 'dataset.json')
    
    if not os.path.exists(data_file):
        print(f"  [WARN] 数据文件不存在: {data_file}")
        print(f"  请先运行 prepare_data.py 准备数据")
    else:
        train_loader, val_loader, test_loader = create_dataloaders(data_file, batch_size=4)
        
        print(f"\n数据集统计:")
        print(f"  训练集: {len(train_loader.dataset)} 样本, {len(train_loader)} 批次")
        print(f"  验证集: {len(val_loader.dataset)} 样本, {len(val_loader)} 批次")
        print(f"  测试集: {len(test_loader.dataset)} 样本, {len(test_loader)} 批次")
        
        # 测试一个batch
        print(f"\n测试一个batch:")
        batch = next(iter(train_loader))
        print(f"  time_series: {batch['time_series'].shape}")
        print(f"  input_ids: {batch['input_ids'].shape}")
        print(f"  attention_mask: {batch['attention_mask'].shape}")
        print(f"  target: {batch['target'].shape}")
        print(f"  projects: {batch['project'][:2]}")
        
        print("\n✓ 数据加载测试通过！")

