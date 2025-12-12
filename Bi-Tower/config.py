"""
配置文件
"""
import os

class Config:
    """双塔模型配置"""
    
    # ============================================================================
    # 路径配置
    # ============================================================================
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    RAW_DATA_DIR = os.path.join(DATA_DIR, 'raw')
    PROCESSED_DATA_DIR = os.path.join(DATA_DIR, 'processed')
    CHECKPOINT_DIR = os.path.join(DATA_DIR, 'checkpoints')
    RESULTS_DIR = os.path.join(BASE_DIR, 'results')
    
    # 创建目录
    for dir_path in [RAW_DATA_DIR, PROCESSED_DATA_DIR, CHECKPOINT_DIR, RESULTS_DIR]:
        os.makedirs(dir_path, exist_ok=True)
    
    # ============================================================================
    # 数据配置
    # ============================================================================
    # 时序数据
    TIME_WINDOW = 12  # 使用过去12个月的数据
    PREDICTION_HORIZON = 3  # 预测未来3个月
    TIME_FEATURES = 20  # 时序特征维度（默认值，会根据实际数据自动调整）
    
    # 文本数据
    TEXT_MAX_LENGTH = 512  # 文本最大长度
    TEXT_MODEL_NAME = 'distilbert-base-uncased'  # 使用轻量级模型
    
    # 数据集划分
    TRAIN_RATIO = 0.7
    VAL_RATIO = 0.15
    TEST_RATIO = 0.15
    
    # ============================================================================
    # 模型配置
    # ============================================================================
    # 时序塔
    TIME_HIDDEN_DIM = 128
    TIME_NUM_LAYERS = 2
    TIME_DROPOUT = 0.1
    
    # 文本塔
    TEXT_HIDDEN_DIM = 768  # DistilBERT输出维度
    TEXT_FREEZE = True  # 是否冻结文本编码器
    
    # 融合层
    FUSION_HIDDEN_DIM = 256
    FUSION_DROPOUT = 0.1
    
    # 预测头
    PREDICTOR_HIDDEN_DIM = 128
    
    # ============================================================================
    # 训练配置
    # ============================================================================
    BATCH_SIZE = 16
    LEARNING_RATE = 1e-4
    WEIGHT_DECAY = 1e-5
    NUM_EPOCHS = 50
    
    # 早停
    EARLY_STOPPING_PATIENCE = 10
    
    # 学习率调度
    LR_SCHEDULER = 'ReduceLROnPlateau'
    LR_PATIENCE = 5
    LR_FACTOR = 0.5
    
    # 梯度裁剪
    GRADIENT_CLIP = 1.0
    
    # 设备
    DEVICE = 'cuda'  # 'cuda' or 'cpu'
    
    # ============================================================================
    # 日志配置
    # ============================================================================
    LOG_INTERVAL = 10  # 每N个batch打印一次
    SAVE_INTERVAL = 1  # 每N个epoch保存一次
    
    # ============================================================================
    # 数据爬取配置
    # ============================================================================
    # 要爬取的热门项目列表（OpenDigger已知仓库）
    TARGET_PROJECTS = [
        # 已有数据
        'X-lab2017/open-digger',
        'microsoft/vscode',
        
        # 编程语言与编译器
        'NixOS/nixpkgs',
        'llvm/llvm-project',
        'pytorch/pytorch',
        'flutter/flutter',
        'zed-industries/zed',
        
        # 开发工具与平台
        'microsoft/winget-pkgs',
        'godotengine/godot',
        'elastic/kibana',
        'grafana/grafana',
        
        # 框架与库
        'home-assistant/core',
        'odoo/odoo',
        'zephyrproject-rtos/zephyr',
        'vllm-project/vllm',
        
        # 开源社区项目
        'digitalinnovationone/dio-lab-open-source',
        'ghscr/ghscription',
        'DigitalPlatDev/FreeDomain',
        'department-of-veterans-affairs/va.gov-team',
        
        # 企业应用
        'Expensify/App',
    ]
    
    NUM_PROJECTS_TO_CRAWL = 10  # 初始爬取数量（可根据需要调整）
    
    # ============================================================================
    # 评估配置
    # ============================================================================
    EVAL_METRICS = ['mae', 'rmse', 'mape', 'r2']

# 创建全局配置实例
config = Config()

