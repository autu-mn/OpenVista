"""
双塔模型定义
"""
import torch
import torch.nn as nn
from transformers import DistilBertModel, DistilBertConfig
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
        """
        Args:
            x: [batch_size, seq_len, input_dim]
        Returns:
            hidden: [batch_size, hidden_dim]
        """
        # LSTM前向传播
        lstm_out, (h_n, c_n) = self.lstm(x)
        
        # 使用最后一个时间步的隐状态
        hidden = h_n[-1]  # [batch_size, hidden_dim]
        hidden = self.dropout(hidden)
        
        return hidden


class TextEncoder(nn.Module):
    """文本塔 - DistilBERT编码器"""
    
    def __init__(self, model_name='distilbert-base-uncased', freeze=True):
        super().__init__()
        
        # 加载预训练的DistilBERT
        self.bert = DistilBertModel.from_pretrained(model_name)
        
        # 是否冻结参数
        if freeze:
            for param in self.bert.parameters():
                param.requires_grad = False
            print(f"  [INFO] 文本编码器参数已冻结")
        else:
            print(f"  [INFO] 文本编码器参数可训练")
        
        self.hidden_dim = self.bert.config.hidden_size  # 768
    
    def forward(self, input_ids, attention_mask):
        """
        Args:
            input_ids: [batch_size, seq_len]
            attention_mask: [batch_size, seq_len]
        Returns:
            hidden: [batch_size, hidden_dim]
        """
        # BERT前向传播
        outputs = self.bert(
            input_ids=input_ids,
            attention_mask=attention_mask
        )
        
        # 使用[CLS] token的表示
        hidden = outputs.last_hidden_state[:, 0, :]  # [batch_size, 768]
        
        return hidden


class FusionLayer(nn.Module):
    """融合层 - 将时序向量和文本向量融合"""
    
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
        """
        Args:
            time_hidden: [batch_size, time_dim]
            text_hidden: [batch_size, text_dim]
        Returns:
            fused: [batch_size, hidden_dim // 2]
        """
        # 拼接
        combined = torch.cat([time_hidden, text_hidden], dim=-1)
        
        # 融合
        fused = self.fusion(combined)
        
        return fused


class PredictionHead(nn.Module):
    """预测头 - 输出未来预测值"""
    
    def __init__(self, input_dim, hidden_dim, output_dim):
        super().__init__()
        
        self.predictor = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim, output_dim)
        )
    
    def forward(self, x):
        """
        Args:
            x: [batch_size, input_dim]
        Returns:
            predictions: [batch_size, output_dim]
        """
        predictions = self.predictor(x)
        return predictions


class DualTowerModel(nn.Module):
    """
    双塔模型 - 完整架构
    
    时序塔 + 文本塔 → 融合层 → 预测头
    """
    
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
        
        # 预测头
        self.prediction_head = PredictionHead(
            input_dim=config.FUSION_HIDDEN_DIM // 2,
            hidden_dim=config.PREDICTOR_HIDDEN_DIM,
            output_dim=config.PREDICTION_HORIZON
        )
    
    def forward(self, time_series, text_input_ids, text_attention_mask):
        """
        Args:
            time_series: [batch_size, seq_len, feature_dim]
            text_input_ids: [batch_size, max_len]
            text_attention_mask: [batch_size, max_len]
        Returns:
            predictions: [batch_size, horizon]
        """
        # 时序编码
        time_hidden = self.time_encoder(time_series)  # [batch, 128]
        
        # 文本编码
        text_hidden = self.text_encoder(text_input_ids, text_attention_mask)  # [batch, 768]
        
        # 融合
        fused = self.fusion_layer(time_hidden, text_hidden)  # [batch, 128]
        
        # 预测
        predictions = self.prediction_head(fused)  # [batch, 3]
        
        return predictions
    
    def count_parameters(self):
        """统计模型参数量"""
        total = sum(p.numel() for p in self.parameters())
        trainable = sum(p.numel() for p in self.parameters() if p.requires_grad)
        
        print(f"\n{'='*60}")
        print(f"模型参数统计:")
        print(f"{'='*60}")
        print(f"  总参数量: {total:,}")
        print(f"  可训练参数: {trainable:,}")
        print(f"  冻结参数: {total - trainable:,}")
        print(f"{'='*60}\n")
        
        return total, trainable


def create_model(config):
    """创建模型实例"""
    model = DualTowerModel(config)
    model.count_parameters()
    return model


if __name__ == '__main__':
    # 测试模型
    print("创建双塔模型...")
    
    model = create_model(config)
    model.eval()
    
    # 创建测试输入
    batch_size = 4
    time_series = torch.randn(batch_size, config.TIME_WINDOW, config.TIME_FEATURES)
    text_input_ids = torch.randint(0, 30000, (batch_size, config.TEXT_MAX_LENGTH))
    text_attention_mask = torch.ones(batch_size, config.TEXT_MAX_LENGTH)
    
    print(f"输入形状:")
    print(f"  时序数据: {time_series.shape}")
    print(f"  文本input_ids: {text_input_ids.shape}")
    print(f"  文本attention_mask: {text_attention_mask.shape}")
    
    # 前向传播
    with torch.no_grad():
        predictions = model(time_series, text_input_ids, text_attention_mask)
    
    print(f"\n输出形状:")
    print(f"  预测值: {predictions.shape}")
    print(f"  预测值示例: {predictions[0].tolist()}")
    
    print("\n✓ 模型测试通过！")

