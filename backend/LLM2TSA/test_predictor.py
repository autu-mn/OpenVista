"""
模块2（LLM为中心的预测器）测试脚本
"""

import os
import sys
import json

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from LLM2TSA.predictor import LLMTimeSeriesPredictor

def test_predictor():
    """测试预测器功能"""
    print("=" * 60)
    print("模块2测试：LLM为中心的预测器")
    print("=" * 60)
    
    # 初始化预测器
    predictor = LLMTimeSeriesPredictor(enable_cache=True)
    
    # 测试数据：模拟OpenRank历史数据
    test_data = {
        "2020-08": 4.76,
        "2020-09": 5.12,
        "2020-10": 5.45,
        "2020-11": 5.78,
        "2020-12": 12.65,
        "2021-01": 6.23,
        "2021-02": 5.81,
        "2021-03": 6.12,
        "2021-04": 6.45,
        "2021-05": 6.78,
        "2021-06": 7.12,
        "2021-07": 7.45,
        "2021-08": 7.78,
        "2021-09": 8.12,
        "2021-10": 8.45,
        "2021-11": 8.78,
        "2021-12": 9.12,
        "2022-01": 9.45,
        "2022-02": 9.78,
        "2022-03": 10.12,
        "2022-04": 10.45,
        "2022-05": 10.78,
        "2022-06": 11.12,
        "2022-07": 11.45,
        "2022-08": 11.78,
        "2022-09": 12.12,
        "2022-10": 12.45,
        "2022-11": 12.78,
        "2022-12": 13.12,
        "2023-01": 13.45,
        "2023-02": 13.78,
        "2023-03": 14.12,
        "2023-04": 14.45,
        "2023-05": 14.78,
        "2023-06": 15.12,
        "2023-07": 15.45,
        "2023-08": 15.78,
        "2023-09": 16.12,
        "2023-10": 16.45,
        "2023-11": 16.78,
        "2023-12": 17.12,
        "2024-01": 17.45,
        "2024-02": 17.78,
        "2024-03": 18.12,
        "2024-04": 18.45,
        "2024-05": 18.78,
        "2024-06": 19.12,
        "2024-07": 19.45,
        "2024-08": 19.78,
        "2024-09": 20.12,
        "2024-10": 20.45,
        "2024-11": 20.78,
        "2024-12": 21.12,
        "2025-01": 21.45,
        "2025-02": 21.78,
        "2025-03": 22.12,
        "2025-04": 22.45,
        "2025-05": 22.78,
        "2025-06": 23.12,
        "2025-07": 23.45,
        "2025-08": 23.78,
        "2025-09": 24.12,
        "2025-10": 24.45,
        "2025-11": 4.58
    }
    
    print("\n1. 测试单指标预测")
    print("-" * 60)
    result = predictor.predict(
        metric_name="OpenRank",
        historical_data=test_data,
        forecast_months=6,
        include_reasoning=True
    )
    
    print(f"\n预测结果:")
    print(f"  指标: OpenRank")
    print(f"  置信度: {result.get('confidence', 0):.2%}")
    print(f"  预测理由: {result.get('reasoning', 'N/A')}")
    
    if result.get('trend_analysis'):
        trend = result['trend_analysis']
        print(f"\n趋势分析:")
        print(f"  方向: {trend.get('direction', 'N/A')}")
        print(f"  强度: {trend.get('strength', 'N/A')}")
        print(f"  波动性: {trend.get('volatility', 'N/A')}")
    
    print(f"\n预测值:")
    forecast = result.get('forecast', {})
    for month, value in sorted(forecast.items()):
        print(f"  {month}: {value:.2f}")
    
    print("\n2. 测试批量预测")
    print("-" * 60)
    metrics_data = {
        "OpenRank": test_data,
        "活跃度": {k: v * 0.8 for k, v in test_data.items()}
    }
    
    batch_results = predictor.predict_multiple(metrics_data, forecast_months=3)
    
    for metric_name, pred_result in batch_results.items():
        print(f"\n{metric_name}:")
        print(f"  置信度: {pred_result.get('confidence', 0):.2%}")
        forecast = pred_result.get('forecast', {})
        for month, value in sorted(forecast.items()):
            print(f"    {month}: {value:.2f}")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)

if __name__ == '__main__':
    test_predictor()

