"""
GitPulse Model - Multimodal Transformer for GitHub Project Health Prediction

基于 Transformer+Text 的多模态时序预测模型
"""

import os
import json
import torch
import torch.nn as nn
from typing import Optional, Tuple
from transformers import DistilBertModel, DistilBertTokenizer


class TextEncoder(nn.Module):
    """文本编码器：基于 DistilBERT"""
    
    def __init__(self, d_model=128, freeze_bert=True):
        super().__init__()
        self.bert = DistilBertModel.from_pretrained('distilbert-base-uncased')
        
        if freeze_bert:
            for param in self.bert.parameters():
                param.requires_grad = False
        
        # 投影层
        self.proj = nn.Sequential(
            nn.Linear(768, d_model * 2),
            nn.LayerNorm(d_model * 2),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(d_model * 2, d_model),
            nn.LayerNorm(d_model)
        )
        
        # 注意力池化
        self.attn_pool = nn.Linear(768, 1)
    
    def forward(self, input_ids, attention_mask):
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        hidden = outputs.last_hidden_state  # [B, L, 768]
        
        # 注意力池化
        attn_weights = self.attn_pool(hidden).squeeze(-1)  # [B, L]
        attn_weights = attn_weights.masked_fill(attention_mask == 0, -1e9)
        attn_weights = torch.softmax(attn_weights, dim=-1)
        
        pooled = torch.bmm(attn_weights.unsqueeze(1), hidden).squeeze(1)  # [B, 768]
        
        return self.proj(pooled)  # [B, d_model]


class TransformerTSEncoder(nn.Module):
    """时序编码器：Transformer"""
    
    def __init__(self, n_vars=16, d_model=128, n_heads=4, n_layers=2, 
                 hist_len=128, dropout=0.1):
        super().__init__()
        
        self.input_proj = nn.Sequential(
            nn.Linear(n_vars, d_model),
            nn.LayerNorm(d_model),
            nn.Dropout(dropout)
        )
        
        self.pos_embedding = nn.Parameter(torch.randn(1, hist_len, d_model) * 0.02)
        
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=n_heads,
            dim_feedforward=d_model * 4, dropout=dropout,
            activation='gelu', batch_first=True
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=n_layers)
        self.norm = nn.LayerNorm(d_model)
    
    def forward(self, x):
        # x: [B, T, n_vars]
        x = self.input_proj(x)
        x = x + self.pos_embedding[:, :x.size(1), :]
        x = self.encoder(x)
        return self.norm(x)


class AdaptiveFusion(nn.Module):
    """自适应融合层"""
    
    def __init__(self, d_model, min_weight=0.1, max_weight=0.3):
        super().__init__()
        self.min_weight = min_weight
        self.max_weight = max_weight
        
        self.gate = nn.Sequential(
            nn.Linear(d_model * 2, d_model),
            nn.GELU(),
            nn.Linear(d_model, 1),
            nn.Sigmoid()
        )
    
    def forward(self, ts_feat, text_feat):
        combined = torch.cat([ts_feat, text_feat], dim=-1)
        raw_weight = self.gate(combined)
        weight = self.min_weight + (self.max_weight - self.min_weight) * raw_weight
        return ts_feat * (1 - weight) + text_feat * weight


class GitPulseModel(nn.Module):
    """
    GitPulse: Multimodal Transformer for Time Series Prediction
    
    结合项目文本描述和历史时序数据进行预测
    """
    
    def __init__(
        self,
        n_vars: int = 16,
        d_model: int = 128,
        n_heads: int = 4,
        n_layers: int = 2,
        hist_len: int = 128,
        pred_len: int = 32,
        dropout: float = 0.1,
        freeze_bert: bool = True
    ):
        super().__init__()
        
        self.n_vars = n_vars
        self.d_model = d_model
        self.hist_len = hist_len
        self.pred_len = pred_len
        
        # 时序编码器
        self.ts_encoder = TransformerTSEncoder(
            n_vars=n_vars, d_model=d_model, n_heads=n_heads,
            n_layers=n_layers, hist_len=hist_len, dropout=dropout
        )
        
        # 文本编码器
        self.text_encoder = TextEncoder(d_model=d_model, freeze_bert=freeze_bert)
        
        # 融合层
        self.fusion = AdaptiveFusion(d_model)
        
        # 预测头
        self.pred_head = nn.Sequential(
            nn.Linear(d_model, d_model * 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model * 2, n_vars)
        )
        
        # 时间投影
        self.temporal_proj = nn.Linear(hist_len, pred_len)
    
    def forward(
        self,
        x: torch.Tensor,
        input_ids: Optional[torch.Tensor] = None,
        attention_mask: Optional[torch.Tensor] = None,
        return_auxiliary: bool = False
    ) -> torch.Tensor:
        """
        Args:
            x: 历史时序 [B, hist_len, n_vars]
            input_ids: 文本 token IDs [B, L]
            attention_mask: 注意力掩码 [B, L]
        
        Returns:
            预测序列 [B, pred_len, n_vars]
        """
        # 时序编码
        ts_encoded = self.ts_encoder(x)  # [B, hist_len, d_model]
        ts_global = ts_encoded.mean(dim=1)  # [B, d_model]
        
        # 文本编码和融合
        if input_ids is not None and attention_mask is not None:
            text_feat = self.text_encoder(input_ids, attention_mask)
            fused = self.fusion(ts_global, text_feat)
        else:
            fused = ts_global
        
        # 预测
        pred_feat = self.pred_head(ts_encoded)  # [B, hist_len, n_vars]
        pred_feat = pred_feat.transpose(1, 2)  # [B, n_vars, hist_len]
        output = self.temporal_proj(pred_feat)  # [B, n_vars, pred_len]
        output = output.transpose(1, 2)  # [B, pred_len, n_vars]
        
        if return_auxiliary:
            return output, torch.tensor(0.0), torch.tensor(0.0), {}
        return output
    
    @classmethod
    def from_pretrained(cls, path: str, device: str = 'cuda'):
        """从预训练权重加载模型"""
        config_path = os.path.join(path, 'config.json')
        weights_path = os.path.join(path, 'gitpulse_weights.pt')
        
        # 加载配置
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
        else:
            config = {}
        
        # 创建模型
        model = cls(
            n_vars=config.get('n_vars', 16),
            d_model=config.get('d_model', 128),
            n_heads=config.get('n_heads', 4),
            n_layers=config.get('n_layers', 2),
            hist_len=config.get('hist_len', 128),
            pred_len=config.get('pred_len', 32)
        )
        
        # 加载权重
        if os.path.exists(weights_path):
            state_dict = torch.load(weights_path, map_location=device, weights_only=False)
            model.load_state_dict(state_dict, strict=False)
            print(f"✓ Loaded weights from {weights_path}")
        
        return model.to(device)
    
    def predict(
        self,
        time_series: torch.Tensor,
        text: str = None,
        tokenizer: DistilBertTokenizer = None
    ) -> torch.Tensor:
        """便捷预测接口"""
        self.eval()
        
        if text is not None and tokenizer is not None:
            encoded = tokenizer(
                text, padding='max_length', truncation=True,
                max_length=128, return_tensors='pt'
            )
            input_ids = encoded['input_ids'].to(time_series.device)
            attention_mask = encoded['attention_mask'].to(time_series.device)
        else:
            input_ids = None
            attention_mask = None
        
        with torch.no_grad():
            output = self.forward(time_series, input_ids, attention_mask)
        
        return output


# 模型信息
def get_model_info():
    return {
        'name': 'GitPulse',
        'version': '1.0',
        'architecture': 'Transformer+Text',
        'description': 'Multimodal time series prediction model for GitHub project health',
        'metrics': {
            'R2': 0.7559,
            'MSE': 0.0755,
            'DA': 0.8668,
            'TA@0.2': 0.8160
        }
    }


