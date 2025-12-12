"""
预训练模型配置变体
提供不同的模型配置以适应不同的计算资源和性能需求
"""
from config import Config


class LightweightConfig(Config):
    """轻量级配置 - 最快训练速度"""
    
    # 文本模型（更小）
    TEXT_MODEL_NAME = 'sentence-transformers/all-MiniLM-L6-v2'  # 22M 参数
    
    # 时序模型（更小）
    TIME_HIDDEN_DIM = 64
    TIME_NUM_LAYERS = 1
    
    # 融合层（更小）
    FUSION_HIDDEN_DIM = 128
    PREDICTOR_HIDDEN_DIM = 64
    
    # 训练参数
    BATCH_SIZE = 32  # 更大的 batch
    NUM_EPOCHS = 30
    
    def __str__(self):
        return "轻量级配置 (总训练参数: ~150K)"


class BalancedConfig(Config):
    """平衡配置 - 推荐使用"""
    
    # 文本模型（更强的预训练模型）
    TEXT_MODEL_NAME = 'microsoft/deberta-v3-small'  # 44M 参数
    
    # 时序模型
    TIME_HIDDEN_DIM = 128
    TIME_NUM_LAYERS = 2
    
    # 融合层
    FUSION_HIDDEN_DIM = 256
    PREDICTOR_HIDDEN_DIM = 128
    
    # 训练参数
    BATCH_SIZE = 16
    NUM_EPOCHS = 50
    
    def __str__(self):
        return "平衡配置 (总训练参数: ~300K)"


class HighPerformanceConfig(Config):
    """高性能配置 - 最佳效果"""
    
    # 文本模型（最强）
    TEXT_MODEL_NAME = 'microsoft/deberta-v3-base'  # 86M 参数
    
    # 时序模型（更深）
    TIME_HIDDEN_DIM = 256
    TIME_NUM_LAYERS = 3
    
    # 融合层（更大）
    FUSION_HIDDEN_DIM = 512
    PREDICTOR_HIDDEN_DIM = 256
    
    # 训练参数
    BATCH_SIZE = 8  # 更小的 batch（更精确的梯度）
    NUM_EPOCHS = 100
    LEARNING_RATE = 5e-5  # 更小的学习率
    
    def __str__(self):
        return "高性能配置 (总训练参数: ~800K)"


class CodeBERTConfig(Config):
    """CodeBERT配置 - 针对技术文本优化"""
    
    # 使用在代码和技术文档上预训练的模型
    TEXT_MODEL_NAME = 'microsoft/codebert-base'  # 125M 参数
    
    # 时序模型
    TIME_HIDDEN_DIM = 128
    TIME_NUM_LAYERS = 2
    
    # 融合层
    FUSION_HIDDEN_DIM = 256
    PREDICTOR_HIDDEN_DIM = 128
    
    # 训练参数
    BATCH_SIZE = 16
    NUM_EPOCHS = 50
    
    def __str__(self):
        return "CodeBERT配置 (适合技术文本)"


class BiLSTMConfig(Config):
    """双向LSTM配置 - 更强的时序建模"""
    
    # 文本模型
    TEXT_MODEL_NAME = 'microsoft/deberta-v3-small'
    
    # 双向 LSTM（需要修改 model.py）
    TIME_HIDDEN_DIM = 128
    TIME_NUM_LAYERS = 2
    TIME_BIDIRECTIONAL = True  # 新增：双向
    
    # 融合层（需要考虑双向输出）
    FUSION_HIDDEN_DIM = 256
    PREDICTOR_HIDDEN_DIM = 128
    
    def __str__(self):
        return "双向LSTM配置 (更强的时序建模)"


# 配置映射
CONFIGS = {
    'lightweight': LightweightConfig,
    'balanced': BalancedConfig,
    'high_performance': HighPerformanceConfig,
    'codebert': CodeBERTConfig,
    'bilstm': BiLSTMConfig,
}


def get_config(name='balanced'):
    """获取配置"""
    if name not in CONFIGS:
        print(f"[WARN] 未知配置 '{name}'，使用默认配置 'balanced'")
        name = 'balanced'
    
    config_class = CONFIGS[name]
    config = config_class()
    
    print(f"\n使用配置: {config}")
    print(f"  文本模型: {config.TEXT_MODEL_NAME}")
    print(f"  时序维度: {config.TIME_HIDDEN_DIM}")
    print(f"  融合维度: {config.FUSION_HIDDEN_DIM}")
    print(f"  Batch大小: {config.BATCH_SIZE}")
    print(f"  训练轮数: {config.NUM_EPOCHS}")
    
    return config


def compare_configs():
    """对比不同配置"""
    print("\n" + "="*80)
    print("配置对比")
    print("="*80 + "\n")
    
    configs_info = [
        ('lightweight', '轻量级', '150K', '3-5h', '~1.5', '快速验证、资源受限'),
        ('balanced', '平衡型', '300K', '6-8h', '~1.2', '日常使用、推荐'),
        ('high_performance', '高性能', '800K', '12-15h', '~1.0', '最佳效果、充足资源'),
        ('codebert', 'CodeBERT', '300K', '6-8h', '~1.1', '技术文本优化'),
    ]
    
    print(f"{'配置':<15} {'描述':<10} {'训练参数':<10} {'时间(CPU)':<12} {'预期MAE':<12} {'适用场景'}")
    print("-" * 80)
    
    for name, desc, params, time, mae, scenario in configs_info:
        print(f"{name:<15} {desc:<10} {params:<10} {time:<12} {mae:<12} {scenario}")
    
    print("\n" + "="*80 + "\n")


if __name__ == '__main__':
    # 显示所有配置
    compare_configs()
    
    # 测试加载配置
    for config_name in ['lightweight', 'balanced', 'high_performance']:
        print(f"\n{'='*60}")
        config = get_config(config_name)
        print(f"{'='*60}")

