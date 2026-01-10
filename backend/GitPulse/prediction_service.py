"""
GitPulse 预测服务
基于 Transformer+Text 多模态模型的时序预测

重要：模型训练时对数据进行了标准化处理，预测时需要：
1. 对输入数据进行相同的标准化
2. 对输出结果进行反标准化
"""

import os
import sys
import json
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# 需要取整的指标（这些指标不能有小数）
INTEGER_METRICS = {
    'Star数', '星标数', 'Stars',
    'Fork数', 'Forks',
    '参与者数', '参与者',
    '新增贡献者', '新贡献者',
    '贡献者', '总贡献者',
    '不活跃贡献者',
    '新增Issue', 'Issues新增',
    '关闭Issue', 'Issues关闭',
    '变更请求', 'PR数',
    'PR接受数', 'PR合并数',
    'PR审查', 'PR评审',
    'Issue评论', '评论数',
    '关注度', 'Watchers',
    '总线因子',
    '代码新增行数', '代码删除行数', '代码修改行数'
}

# 16个核心指标的映射
METRIC_MAPPING = {
    'OpenRank': 0,
    '活跃度': 1,
    'Star数': 2,
    'Fork数': 3,
    '关注度': 4,
    '参与者数': 5,
    '新增贡献者': 6,
    '贡献者': 7,
    '不活跃贡献者': 8,
    '总线因子': 9,
    '新增Issue': 10,
    '关闭Issue': 11,
    'Issue评论': 12,
    '变更请求': 13,
    'PR接受数': 14,
    'PR审查': 15,
}

# 反向映射
INDEX_TO_METRIC = {v: k for k, v in METRIC_MAPPING.items()}


def check_dependencies() -> Tuple[bool, str]:
    """检查 GitPulse 依赖是否已安装"""
    missing = []
    
    try:
        import torch
    except ImportError:
        missing.append('torch')
    
    try:
        import transformers
    except ImportError:
        missing.append('transformers')
    
    if missing:
        return False, f"缺少依赖包: {', '.join(missing)}。请运行: pip install torch transformers"
    
    # 检查模型权重文件
    weights_path = os.path.join(os.path.dirname(__file__), 'gitpulse_weights.pt')
    if not os.path.exists(weights_path):
        return False, f"模型权重文件不存在: {weights_path}"
    
    return True, "所有依赖已就绪"


class DataNormalizer:
    """数据标准化/反标准化器 - 保持原始精度"""
    
    def __init__(self):
        self.means = None  # [16]
        self.stds = None   # [16]
        self.fitted = False
        self.last_values = None  # 最后一个历史值
    
    def fit(self, data: np.ndarray):
        """
        从历史数据计算标准化参数
        使用标准的均值和标准差，保持数据精度
        
        Args:
            data: [T, 16] 历史时序数据
        """
        # 保存最后一个历史值（用于平滑过渡）
        self.last_values = data[-1].copy()
        
        # 使用标准的均值和标准差
        self.means = np.mean(data, axis=0)
        self.stds = np.std(data, axis=0)
        
        # 防止标准差为0
        self.stds = np.where(self.stds < 1e-8, 1.0, self.stds)
        
        self.fitted = True
        print(f"[Normalizer] 均值: {self.means[:3].round(4)}..., 标准差: {self.stds[:3].round(4)}...")
    
    def transform(self, data: np.ndarray) -> np.ndarray:
        """标准化数据"""
        if not self.fitted:
            raise ValueError("请先调用 fit() 计算标准化参数")
        return (data - self.means) / self.stds
    
    def inverse_transform(self, data: np.ndarray) -> np.ndarray:
        """反标准化数据"""
        if not self.fitted:
            raise ValueError("请先调用 fit() 计算标准化参数")
        return data * self.stds + self.means
    
    def _detect_delayed_data(self, historical_data: np.ndarray, check_months: int = 2) -> int:
        """
        检测数据延迟导致的异常值
        
        OpenDigger 数据通常有 1-2 个月的延迟，最后几个月可能是 0 或异常低值
        
        Args:
            historical_data: [hist_len, 16] 历史数据
            check_months: 检查最后多少个月
        
        Returns:
            需要排除的月份数（从末尾开始）
        """
        hist_len = len(historical_data)
        if hist_len < 6:
            return 0
        
        exclude_months = 0
        
        # 计算历史数据的统计特征（排除最后 check_months 个月）
        stable_data = historical_data[:-check_months] if check_months > 0 else historical_data
        
        for i in range(check_months):
            idx = hist_len - 1 - i  # 从最后一个月开始检查
            current_values = historical_data[idx]
            
            # 检查每个指标
            anomaly_count = 0
            for j in range(len(current_values)):
                stable_mean = np.mean(stable_data[:, j])
                stable_std = np.std(stable_data[:, j])
                
                # 如果某个值接近0，但历史均值很高，可能是数据延迟
                if stable_mean > 10:  # 只对均值较大的指标检查
                    # 如果当前值 < 均值的 5% 且 < 均值 - 3*标准差
                    if current_values[j] < stable_mean * 0.05 and current_values[j] < stable_mean - 3 * stable_std:
                        anomaly_count += 1
            
            # 如果超过一半的指标异常，认为这个月是延迟数据
            if anomaly_count >= len(current_values) // 3:
                exclude_months = i + 1
            else:
                break
        
        if exclude_months > 0:
            print(f"[Normalizer] 检测到数据延迟，排除最后 {exclude_months} 个月的异常数据")
        
        return exclude_months
    
    def trend_based_prediction(self, model_prediction: np.ndarray, 
                                 historical_data: np.ndarray,
                                 trend_window: int = 6) -> np.ndarray:
        """
        基于历史趋势的预测后处理
        
        核心思想：
        1. 检测并排除数据延迟导致的异常值（最后1-2个月可能是0）
        2. 从有效的历史数据计算趋势
        3. 预测从有效的最后历史值开始，延续趋势
        4. 模型输出作为趋势微调
        
        Args:
            model_prediction: [pred_len, 16] 模型反标准化后的预测
            historical_data: [hist_len, 16] 原始历史数据
            trend_window: 用于计算趋势的窗口大小
        
        Returns:
            修正后的预测数据
        """
        pred_len = len(model_prediction)
        n_vars = model_prediction.shape[1]
        result = np.zeros_like(model_prediction)
        
        # 检测数据延迟
        exclude_months = self._detect_delayed_data(historical_data, check_months=2)
        
        # 使用有效的历史数据
        if exclude_months > 0:
            valid_historical = historical_data[:-exclude_months]
            print(f"[Normalizer] 使用前 {len(valid_historical)} 个月的有效数据")
        else:
            valid_historical = historical_data
        
        hist_len = len(valid_historical)
        if hist_len < 3:
            # 数据太少，直接返回模型预测
            return model_prediction
        
        # 计算有效的最后值和趋势窗口
        valid_last_values = valid_historical[-1]
        actual_window = min(trend_window, hist_len - 1)
        
        for i in range(n_vars):
            last_value = valid_last_values[i]
            
            # 计算最近的趋势（月均变化量）
            if actual_window >= 2:
                recent_values = valid_historical[-actual_window:, i]
                
                # 使用线性回归计算趋势斜率
                x = np.arange(actual_window)
                try:
                    slope = np.polyfit(x, recent_values, 1)[0]
                except:
                    slope = 0
                
                # 限制趋势幅度，避免极端外推
                # 最多每月变化 5%（更保守）
                max_monthly_change = abs(last_value) * 0.05 + 0.5
                slope = np.clip(slope, -max_monthly_change, max_monthly_change)
            else:
                slope = 0
            
            # 模型预测的相对变化
            model_relative = (model_prediction[:, i] - self.means[i]) / max(self.stds[i], 1e-8)
            
            # 生成预测
            current_slope = slope
            for t in range(pred_len):
                # 基础预测：延续历史趋势
                trend_value = last_value + current_slope * (t + 1)
                
                # 模型微调（权重较小，主要依赖趋势）
                model_weight = 0.15 * np.exp(-t * 0.15)
                model_adjustment = model_relative[t] * self.stds[i] * model_weight
                
                # 最终预测
                result[t, i] = trend_value + model_adjustment
                
                # 确保非负
                result[t, i] = max(0, result[t, i])
                
                # 趋势衰减：趋势逐渐趋于平稳
                current_slope *= 0.85
        
        return result
    
    def fit_transform(self, data: np.ndarray) -> np.ndarray:
        """计算参数并标准化"""
        self.fit(data)
        return self.transform(data)


class GitPulsePredictor:
    """GitPulse 预测器 - 直接使用 GitPulseModel"""
    
    def __init__(self):
        import torch
        from transformers import DistilBertTokenizer
        from .model import GitPulseModel
        
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"[GitPulse] 使用设备: {self.device}")
        
        # 加载模型配置
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        model_config = config.get('model_config', {})
        
        # 创建模型
        self.model = GitPulseModel(
            n_vars=model_config.get('n_vars', 16),
            d_model=model_config.get('d_model', 128),
            n_heads=model_config.get('n_heads', 4),
            n_layers=model_config.get('n_layers', 2),
            hist_len=model_config.get('hist_len', 128),
            pred_len=model_config.get('pred_len', 32),
            dropout=model_config.get('dropout', 0.1),
            freeze_bert=model_config.get('freeze_bert', True)
        )
        
        # 加载权重
        weights_path = os.path.join(os.path.dirname(__file__), 'gitpulse_weights.pt')
        state_dict = torch.load(weights_path, map_location=self.device, weights_only=False)
        self.model.load_state_dict(state_dict, strict=False)
        self.model = self.model.to(self.device)
        self.model.eval()
        
        # 加载 tokenizer
        self.tokenizer = DistilBertTokenizer.from_pretrained('distilbert-base-uncased')
        
        # 保存配置
        self.hist_len = model_config.get('hist_len', 128)
        self.pred_len = model_config.get('pred_len', 32)
        self.n_vars = model_config.get('n_vars', 16)
        
        # 数据标准化器
        self.normalizer = DataNormalizer()
        
        print(f"[GitPulse] 模型加载成功 (hist_len={self.hist_len}, pred_len={self.pred_len})")
    
    def predict(self, timeseries: np.ndarray, text: str = "") -> Tuple[np.ndarray, Dict]:
        """
        执行预测（带标准化/反标准化）
        
        Args:
            timeseries: [T, 16] 历史时序数据（原始尺度）
            text: 项目描述文本
        
        Returns:
            prediction: [pred_len, 16] 预测结果（原始尺度）
            stats: 统计信息
        """
        import torch
        
        # 准备时序数据
        ts = np.array(timeseries, dtype=np.float32)
        
        # 如果数据不足 hist_len，进行填充
        if len(ts) < self.hist_len:
            padding_len = self.hist_len - len(ts)
            # 使用第一个值进行填充（而不是0）
            padding = np.tile(ts[0:1], (padding_len, 1)) if len(ts) > 0 else np.zeros((padding_len, self.n_vars))
            ts = np.vstack([padding, ts])
        elif len(ts) > self.hist_len:
            ts = ts[-self.hist_len:]
        
        # ====== 关键：标准化输入数据 ======
        self.normalizer.fit(ts)  # 从历史数据计算均值和标准差
        ts_normalized = self.normalizer.transform(ts)
        
        # 转换为 tensor [1, hist_len, n_vars]
        ts_tensor = torch.tensor(ts_normalized, dtype=torch.float32).unsqueeze(0).to(self.device)
        
        # 准备文本
        if text:
            encoded = self.tokenizer(
                text, padding='max_length', truncation=True,
                max_length=128, return_tensors='pt'
            )
            input_ids = encoded['input_ids'].to(self.device)
            attention_mask = encoded['attention_mask'].to(self.device)
        else:
            input_ids = None
            attention_mask = None
        
        # 预测（输出是标准化后的尺度）
        with torch.no_grad():
            output = self.model(ts_tensor, input_ids, attention_mask)
        
        prediction_normalized = output.squeeze(0).cpu().numpy()  # [pred_len, n_vars]
        
        # ====== 反标准化：恢复到原始尺度 ======
        model_prediction = self.normalizer.inverse_transform(prediction_normalized)
        
        # ====== 关键：基于历史趋势的预测后处理 ======
        # 这确保预测从历史最后值开始，延续历史趋势，而不是跳到全局均值
        prediction = self.normalizer.trend_based_prediction(
            model_prediction=model_prediction,
            historical_data=ts,  # 传入原始历史数据用于计算趋势
            trend_window=6  # 使用最近6个月计算趋势
        )
        
        stats = {
            'input_length': len(timeseries),
            'prediction_length': self.pred_len,
            'device': self.device,
            'trend_based': True,
            'last_values': self.normalizer.last_values[:3].tolist() if self.normalizer.last_values is not None else None
        }
        
        return prediction, stats


class PredictionService:
    """预测服务封装"""
    
    def __init__(self):
        self._predictor = None
        self._available = False
        self._error_message = None
        self._initialize()
    
    def _initialize(self):
        """初始化预测服务"""
        # 检查依赖
        is_ready, msg = check_dependencies()
        
        if not is_ready:
            self._error_message = msg
            print(f"[ERROR] GitPulse 依赖检查失败: {msg}")
            return
        
        # 初始化预测器
        try:
            self._predictor = GitPulsePredictor()
            self._available = True
            print("[OK] GitPulse 预测服务初始化成功")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._error_message = f"模型加载失败: {str(e)}"
            print(f"[ERROR] {self._error_message}")
    
    def is_available(self) -> bool:
        """检查服务是否可用"""
        return self._available
    
    def get_error(self) -> Optional[str]:
        """获取错误信息"""
        return self._error_message
    
    def predict(self, timeseries_dir: str, forecast_months: int = 12,
                repo_info: Dict = None) -> Dict:
        """
        从 timeseries_for_model 目录预测
        
        Args:
            timeseries_dir: timeseries_for_model 目录路径
            forecast_months: 预测月数
            repo_info: 仓库信息
        
        Returns:
            预测结果
        """
        if not self._available:
            return {
                'error': self._error_message or '预测服务不可用',
                'available': False
            }
        
        try:
            # 加载所有月度数据
            all_months_data = self._load_timeseries_data(timeseries_dir)
            
            if not all_months_data:
                return {
                    'error': '没有找到有效的时序数据',
                    'available': True
                }
            
            # ====== 处理数据延迟：排除最后1-2个月 ======
            # OpenDigger 数据通常有 1-2 个月延迟，最后几个月可能是 0 或异常
            sorted_all_months = sorted(all_months_data.keys())
            
            print(f"[GitPulse] 原始数据月份: {sorted_all_months[-5:] if len(sorted_all_months) >= 5 else sorted_all_months}")
            
            # 检测并排除延迟数据
            delay_months_to_predict = []
            if len(sorted_all_months) >= 6:
                # 计算历史均值（排除最后2个月）
                valid_months = sorted_all_months[:-2]
                
                # 收集所有指标的历史均值
                all_valid_sums = []
                for m in valid_months:
                    metrics = all_months_data[m]
                    month_sum = 0
                    for key, val in metrics.items():
                        if isinstance(val, (int, float)) and val > 0:
                            month_sum += val
                    if month_sum > 0:
                        all_valid_sums.append(month_sum)
                
                if all_valid_sums:
                    hist_mean_sum = sum(all_valid_sums) / len(all_valid_sums)
                    print(f"[GitPulse] 历史月均指标总和: {hist_mean_sum:.1f}")
                    
                    # 检查最后2个月
                    for m in sorted_all_months[-2:]:
                        metrics = all_months_data[m]
                        month_sum = 0
                        for key, val in metrics.items():
                            if isinstance(val, (int, float)) and val > 0:
                                month_sum += val
                        
                        print(f"[GitPulse] {m} 月指标总和: {month_sum:.1f}")
                        
                        # 如果当月总和接近0但历史均值很高，认为是延迟数据
                        if hist_mean_sum > 100 and month_sum < hist_mean_sum * 0.1:
                            delay_months_to_predict.append(m)
                            print(f"[GitPulse] {m} 被识别为延迟数据，排除")
            
            # 从数据中移除延迟月份
            for m in delay_months_to_predict:
                if m in all_months_data:
                    del all_months_data[m]
            
            if delay_months_to_predict:
                print(f"[GitPulse] 已排除延迟数据: {delay_months_to_predict}")
            
            # 准备16个指标的历史数据矩阵 [T, 16]
            timeseries_matrix, sorted_months = self._prepare_timeseries_matrix(all_months_data)
            
            if timeseries_matrix is None:
                return {
                    'error': '无法构建时序矩阵',
                    'available': True
                }
            
            print(f"[GitPulse] 历史数据矩阵: {timeseries_matrix.shape}, 最近值: {timeseries_matrix[-1, :3].round(2)}")
            
            # 准备文本描述
            text_context = ""
            if repo_info:
                text_context = f"{repo_info.get('full_name', '')} - {repo_info.get('description', '')}"
            
            # 执行预测（已包含标准化/反标准化）
            prediction, stats = self._predictor.predict(timeseries_matrix, text_context)
            
            print(f"[GitPulse] 预测结果: shape={prediction.shape}, 第一月预测: {prediction[0, :3].round(2)}")
            
            # 限制预测月数
            if forecast_months < self._predictor.pred_len:
                prediction = prediction[:forecast_months]
            
            # 构建预测结果
            predictions = self._build_predictions(
                prediction, sorted_months, all_months_data, forecast_months
            )
            
            # 处理整数指标
            predictions = self._round_integer_metrics(predictions)
            
            # 构建完整结果
            result = {
                'available': True,
                'predictions': predictions,
                'forecast_months': forecast_months,
                'historical_months': len(all_months_data),
                'model': 'GitPulse (Transformer+Text)',
                'last_month': sorted_months[-1] if sorted_months else None,
                'model_info': {
                    'R2': 0.7559,
                    'MSE': 0.0755,
                    'DA': 0.8668
                }
            }
            
            # 添加仓库信息
            if repo_info:
                result['repo_info'] = {
                    'name': repo_info.get('name', ''),
                    'full_name': repo_info.get('full_name', ''),
                    'description': repo_info.get('description', '')
                }
            
            return result
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                'error': str(e),
                'available': True
            }
    
    def _load_timeseries_data(self, timeseries_dir: str) -> Dict[str, Dict]:
        """加载时序数据目录中的所有月度文件"""
        if not os.path.exists(timeseries_dir):
            return {}
        
        all_data = {}
        
        for filename in os.listdir(timeseries_dir):
            if not filename.endswith('.json'):
                continue
            
            name_part = filename[:-5]
            
            # 检查是否是月份格式 YYYY-MM
            if len(name_part) != 7 or name_part[4] != '-':
                continue
            
            try:
                int(name_part[:4])
                int(name_part[5:7])
            except ValueError:
                continue
            
            filepath = os.path.join(timeseries_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    month_data = json.load(f)
                
                metrics = month_data.get('opendigger_metrics', {})
                if metrics:
                    all_data[name_part] = metrics
                    
            except Exception as e:
                print(f"[WARN] 加载 {filename} 失败: {e}")
                continue
        
        return all_data
    
    def _prepare_timeseries_matrix(self, all_months_data: Dict[str, Dict]) -> Tuple[np.ndarray, List[str]]:
        """
        将按月组织的数据转换为 [T, 16] 矩阵
        """
        if not all_months_data:
            return None, []
        
        sorted_months = sorted(all_months_data.keys())
        T = len(sorted_months)
        
        # 初始化矩阵
        matrix = np.zeros((T, 16), dtype=np.float32)
        
        for t, month in enumerate(sorted_months):
            month_metrics = all_months_data[month]
            
            for metric_name, metric_idx in METRIC_MAPPING.items():
                value = month_metrics.get(metric_name, 0)
                try:
                    matrix[t, metric_idx] = float(value) if value is not None else 0.0
                except (TypeError, ValueError):
                    matrix[t, metric_idx] = 0.0
        
        return matrix, sorted_months
    
    def _build_predictions(self, prediction: np.ndarray, sorted_months: List[str],
                          all_months_data: Dict[str, Dict], forecast_months: int) -> Dict:
        """构建预测结果字典"""
        results = {}
        
        # 获取最后一个历史月份
        if not sorted_months:
            return results
        
        last_date = sorted_months[-1]
        last_year, last_month = map(int, last_date.split('-'))
        
        # 为每个指标构建预测结果
        for metric_name, metric_idx in METRIC_MAPPING.items():
            # 历史数据
            historical = {}
            for month in sorted_months:
                if metric_name in all_months_data[month]:
                    historical[month] = all_months_data[month].get(metric_name, 0)
            
            # 获取最后一个历史值（用于合理性检查）
            last_historical_value = list(historical.values())[-1] if historical else 0
            
            # 预测数据
            forecast = {}
            for i in range(min(forecast_months, len(prediction))):
                target_month = last_month + i + 1
                target_year = last_year
                while target_month > 12:
                    target_month -= 12
                    target_year += 1
                target_str = f"{target_year:04d}-{target_month:02d}"
                
                pred_value = float(prediction[i, metric_idx])
                
                # 合理性检查：预测值不应该与历史值差异过大
                # 如果差异超过历史值的5倍，进行裁剪
                if last_historical_value > 0:
                    max_allowed = last_historical_value * 5
                    min_allowed = last_historical_value * 0.1
                    pred_value = max(min_allowed, min(max_allowed, pred_value))
                
                forecast[target_str] = pred_value
            
            # 计算趋势
            if forecast and historical:
                first_pred = list(forecast.values())[0]
                last_pred = list(forecast.values())[-1]
                last_hist = list(historical.values())[-1]
                
                trend = 'up' if last_pred > last_hist else 'down'
                change_pct = ((last_pred - last_hist) / max(abs(last_hist), 1)) * 100
            else:
                trend = 'stable'
                change_pct = 0
            
            # 计算置信度
            confidence = self._calculate_confidence(len(historical), forecast_months)
            
            results[metric_name] = {
                'forecast': forecast,
                'historical': historical,  # 添加历史数据用于前端对比
                'historical_length': len(historical),
                'confidence': confidence,
                'trend': trend,
                'change_percent': round(change_pct, 2),
                'reasoning': f"基于 GitPulse 多模态 Transformer 模型预测 (R²=0.7559)"
            }
        
        return results
    
    def _calculate_confidence(self, hist_len: int, pred_len: int) -> float:
        """计算预测置信度"""
        # 基于历史数据量
        if hist_len >= 48:
            base = 0.85
        elif hist_len >= 24:
            base = 0.75
        elif hist_len >= 12:
            base = 0.65
        else:
            base = 0.50
        
        # 预测越远置信度越低
        decay = 1.0 - (pred_len / 32) * 0.15
        
        return round(base * decay, 2)
    
    def _round_integer_metrics(self, predictions: Dict) -> Dict:
        """将整数类型的指标预测值取整"""
        for metric_name, pred_data in predictions.items():
            if not isinstance(pred_data, dict):
                continue
            
            needs_round = any(int_metric in metric_name for int_metric in INTEGER_METRICS)
            
            if needs_round and 'forecast' in pred_data:
                forecast = pred_data['forecast']
                if isinstance(forecast, dict):
                    pred_data['forecast'] = {
                        month: max(0, round(value))
                        for month, value in forecast.items()
                    }
        
        return predictions


# 单例模式
_prediction_service = None

def get_prediction_service() -> PredictionService:
    """获取预测服务单例"""
    global _prediction_service
    if _prediction_service is None:
        _prediction_service = PredictionService()
    return _prediction_service
