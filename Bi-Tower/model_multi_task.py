"""
多任务学习版本的双塔模型
同时预测多个关键指标
"""
import torch
import torch.nn as nn
from transformers import DistilBertModel
from config import config


class TimeSeriesEncoder(nn.Module):
    """时序塔 - LSTM编码器"""
    
    def __init__(self, input_dim, hidden_dim, num_layers, dropout=0.1):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
            bidirectional=False
        )
        
        self.dropout = nn.Dropout(dropout)
    
    def forward(self, x):
        lstm_out, (h_n, c_n) = self.lstm(x)
        hidden = h_n[-1]
        hidden = self.dropout(hidden)
        return hidden


class TextEncoder(nn.Module):
    """文本塔 - DistilBERT编码器"""
    
    def __init__(self, model_name='distilbert-base-uncased', freeze=True):
        super().__init__()
        self.bert = DistilBertModel.from_pretrained(model_name)
        
        if freeze:
            for param in self.bert.parameters():
                param.requires_grad = False
        
        self.hidden_dim = self.bert.config.hidden_size
    
    def forward(self, input_ids, attention_mask):
        outputs = self.bert(
            input_ids=input_ids,
            attention_mask=attention_mask
        )
        hidden = outputs.last_hidden_state[:, 0, :]
        return hidden


class FusionLayer(nn.Module):
    """融合层"""
    
    def __init__(self, time_dim, text_dim, hidden_dim, dropout=0.1):
        super().__init__()
        input_dim = time_dim + text_dim
        
        self.fusion = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout)
        )
    
    def forward(self, time_hidden, text_hidden):
        combined = torch.cat([time_hidden, text_hidden], dim=-1)
        fused = self.fusion(combined)
        return fused


class MultiTaskDualTowerModel(nn.Module):
    """
    多任务双塔模型
    
    同时预测：
    1. activity_score（活跃度）
    2. community_engagement（社区参与度）
    3. issues_count（Issue数量）
    4. prs_count（PR数量）
    5. contributors_count（贡献者数）
    """
    
    # 定义预测目标
    TARGET_METRICS = [
        'activity_score',
        'community_engagement',
        'issues_count',
        'prs_count',
        'contributors_count'
    ]
    
    def __init__(self, config):
        super().__init__()
        
        # 时序塔
        self.time_encoder = TimeSeriesEncoder(
            input_dim=config.TIME_FEATURES,
            hidden_dim=config.TIME_HIDDEN_DIM,
            num_layers=config.TIME_NUM_LAYERS,
            dropout=config.TIME_DROPOUT
        )
        
        # 文本塔
        self.text_encoder = TextEncoder(
            model_name=config.TEXT_MODEL_NAME,
            freeze=config.TEXT_FREEZE
        )
        
        # 融合层
        self.fusion_layer = FusionLayer(
            time_dim=config.TIME_HIDDEN_DIM,
            text_dim=config.TEXT_HIDDEN_DIM,
            hidden_dim=config.FUSION_HIDDEN_DIM,
            dropout=config.FUSION_DROPOUT
        )
        
        # 多任务预测头
        self.predictors = nn.ModuleDict({
            metric: nn.Sequential(
                nn.Linear(config.FUSION_HIDDEN_DIM // 2, config.PREDICTOR_HIDDEN_DIM),
                nn.ReLU(),
                nn.Dropout(0.1),
                nn.Linear(config.PREDICTOR_HIDDEN_DIM, config.PREDICTION_HORIZON)
            )
            for metric in self.TARGET_METRICS
        })
    
    def forward(self, time_series, text_input_ids, text_attention_mask):
        """
        Args:
            time_series: [batch_size, seq_len, feature_dim]
            text_input_ids: [batch_size, max_len]
            text_attention_mask: [batch_size, max_len]
        Returns:
            predictions: dict of [batch_size, horizon]
        """
        # 时序编码
        time_hidden = self.time_encoder(time_series)
        
        # 文本编码
        text_hidden = self.text_encoder(text_input_ids, text_attention_mask)
        
        # 融合
        fused = self.fusion_layer(time_hidden, text_hidden)
        
        # 多任务预测
        predictions = {
            metric: self.predictors[metric](fused)
            for metric in self.TARGET_METRICS
        }
        
        return predictions
    
    def count_parameters(self):
        """统计模型参数量"""
        total = sum(p.numel() for p in self.parameters())
        trainable = sum(p.numel() for p in self.parameters() if p.requires_grad)
        
        print(f"\n{'='*60}")
        print(f"多任务模型参数统计:")
        print(f"{'='*60}")
        print(f"  总参数量: {total:,}")
        print(f"  可训练参数: {trainable:,}")
        print(f"  冻结参数: {total - trainable:,}")
        print(f"  预测任务数: {len(self.TARGET_METRICS)}")
        print(f"{'='*60}\n")
        
        return total, trainable


def create_multi_task_model(config):
    """创建多任务模型实例"""
    model = MultiTaskDualTowerModel(config)
    model.count_parameters()
    return model


if __name__ == '__main__':
    # 测试模型
    print("创建多任务双塔模型...")
    
    model = create_multi_task_model(config)
    model.eval()
    
    # 创建测试输入
    batch_size = 4
    time_series = torch.randn(batch_size, config.TIME_WINDOW, config.TIME_FEATURES)
    text_input_ids = torch.randint(0, 30000, (batch_size, config.TEXT_MAX_LENGTH))
    text_attention_mask = torch.ones(batch_size, config.TEXT_MAX_LENGTH)
    
    print(f"输入形状:")
    print(f"  时序数据: {time_series.shape}")
    print(f"  文本input_ids: {text_input_ids.shape}")
    
    # 前向传播
    with torch.no_grad():
        predictions = model(time_series, text_input_ids, text_attention_mask)
    
    print(f"\n输出形状（多任务）:")
    for metric, pred in predictions.items():
        print(f"  {metric}: {pred.shape}")
    
    print("\n✓ 多任务模型测试通过！")





