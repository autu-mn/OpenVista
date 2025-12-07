# LLM2TSA 快速开始指南

## 🚀 5分钟快速上手

本指南将帮助你快速实现第一个功能：**时序数据增强（模式1）**。

---

## 步骤1：创建模块结构

```bash
# 在 backend 目录下执行
mkdir -p LLM2TSA
touch LLM2TSA/__init__.py
touch LLM2TSA/enhancer.py
touch LLM2TSA/llm_client.py
touch LLM2TSA/utils.py
```

---

## 步骤2：实现LLM客户端封装

创建 `backend/LLM2TSA/llm_client.py`：

```python
"""LLM客户端统一接口"""
import os
from typing import Optional
from abc import ABC, abstractmethod

try:
    from Agent.deepseek_client import DeepSeekClient
    DEEPSEEK_AVAILABLE = True
except ImportError:
    DEEPSEEK_AVAILABLE = False


class BaseLLMClient(ABC):
    """LLM客户端基类"""
    
    @abstractmethod
    def generate(self, prompt: str, max_tokens: int = 2000) -> str:
        """生成文本"""
        pass


class UnifiedLLMClient(BaseLLMClient):
    """统一的LLM客户端，封装不同LLM实现"""
    
    def __init__(self, provider: str = "deepseek"):
        self.provider = provider
        self.client = self._init_client()
    
    def _init_client(self):
        """初始化客户端"""
        if self.provider == "deepseek":
            if not DEEPSEEK_AVAILABLE:
                raise ValueError("DeepSeek客户端不可用")
            return DeepSeekClient()
        else:
            raise ValueError(f"不支持的LLM提供商: {self.provider}")
    
    def generate(self, prompt: str, max_tokens: int = 2000) -> str:
        """生成文本"""
        try:
            if self.provider == "deepseek":
                return self.client.ask(prompt, context="")
            else:
                raise ValueError(f"不支持的LLM提供商: {self.provider}")
        except Exception as e:
            print(f"LLM生成失败: {str(e)}")
            raise
```

---

## 步骤3：实现时序数据增强器

创建 `backend/LLM2TSA/enhancer.py`：

```python
"""时序数据增强器 - 模式1实现"""
import json
from typing import Dict, List, Optional
from .llm_client import UnifiedLLMClient


class TimeSeriesEnhancer:
    """时序数据增强器：为时序数据添加语义描述"""
    
    def __init__(self, llm_provider: str = "deepseek"):
        self.llm_client = UnifiedLLMClient(provider=llm_provider)
    
    def enhance_metric(self, metric_name: str, time_series: Dict[str, float]) -> Dict:
        """
        为单个指标生成增强信息
        
        参数:
            metric_name: 指标名称，如 "OpenRank"
            time_series: 时序数据字典，如 {"2020-08": 4.76, "2020-09": 4.93}
        
        返回:
            {
                "description": "指标描述",
                "trends": [...],
                "key_points": [...],
                "semantic_features": {...}
            }
        """
        if not time_series:
            return {
                "description": "暂无数据",
                "trends": [],
                "key_points": [],
                "semantic_features": {}
            }
        
        # 1. 生成指标描述
        description = self._generate_description(metric_name, time_series)
        
        # 2. 识别趋势
        trends = self._detect_trends(metric_name, time_series)
        
        # 3. 提取关键点
        key_points = self._extract_key_points(metric_name, time_series)
        
        # 4. 生成语义特征
        semantic_features = self._extract_semantic_features(time_series)
        
        return {
            "description": description,
            "trends": trends,
            "key_points": key_points,
            "semantic_features": semantic_features
        }
    
    def _generate_description(self, metric_name: str, time_series: Dict[str, float]) -> str:
        """生成指标描述"""
        dates = sorted(time_series.keys())
        first_value = time_series[dates[0]]
        last_value = time_series[dates[-1]]
        data_points = len(time_series)
        
        prompt = f"""
请为以下时序指标生成简洁的描述（100字以内）：

指标名称：{metric_name}
数据范围：{dates[0]} 至 {dates[-1]}（共{data_points}个月）
初始值：{first_value:.2f}
最新值：{last_value:.2f}
变化幅度：{((last_value - first_value) / first_value * 100):.1f}%

请用自然语言描述这个指标的含义和整体趋势。
"""
        
        try:
            description = self.llm_client.generate(prompt, max_tokens=200)
            return description.strip()
        except Exception as e:
            print(f"生成描述失败: {e}")
            return f"{metric_name}指标反映了项目相关的变化趋势。"
    
    def _detect_trends(self, metric_name: str, time_series: Dict[str, float]) -> List[Dict]:
        """识别趋势模式"""
        dates = sorted(time_series.keys())
        values = [time_series[d] for d in dates]
        
        # 简单的趋势检测（可以后续优化）
        trends = []
        
        # 计算整体趋势
        if len(values) >= 2:
            overall_change = (values[-1] - values[0]) / values[0] * 100
            if overall_change > 10:
                trend_type = "上升"
            elif overall_change < -10:
                trend_type = "下降"
            else:
                trend_type = "稳定"
            
            trends.append({
                "period": f"{dates[0]} to {dates[-1]}",
                "type": trend_type,
                "change_percent": round(overall_change, 1),
                "description": f"整体呈现{trend_type}趋势，变化幅度{abs(overall_change):.1f}%"
            })
        
        # 使用LLM生成更详细的趋势分析
        if len(values) >= 6:
            recent_data = {dates[i]: values[i] for i in range(-6, 0)}
            prompt = f"""
基于以下{metric_name}指标的最近6个月数据，识别趋势模式：

{json.dumps(recent_data, ensure_ascii=False, indent=2)}

请识别：
1. 趋势类型（上升/下降/波动/周期性）
2. 趋势描述（50字以内）

格式：JSON
{{
    "type": "上升",
    "description": "..."
}}
"""
            try:
                llm_result = self.llm_client.generate(prompt, max_tokens=300)
                # 解析JSON结果（简化处理）
                if "上升" in llm_result or "增长" in llm_result:
                    trends.append({
                        "period": f"{dates[-6]} to {dates[-1]}",
                        "type": "上升",
                        "description": llm_result[:100]
                    })
            except:
                pass
        
        return trends
    
    def _extract_key_points(self, metric_name: str, time_series: Dict[str, float]) -> List[Dict]:
        """提取关键时间点"""
        dates = sorted(time_series.keys())
        values = [time_series[d] for d in dates]
        
        key_points = []
        
        # 找到最大值和最小值
        max_idx = values.index(max(values))
        min_idx = values.index(min(values))
        
        if max_idx != min_idx:
            key_points.append({
                "date": dates[max_idx],
                "value": values[max_idx],
                "type": "峰值",
                "description": f"达到历史最高值 {values[max_idx]:.2f}"
            })
            
            key_points.append({
                "date": dates[min_idx],
                "value": values[min_idx],
                "type": "谷值",
                "description": f"达到历史最低值 {values[min_idx]:.2f}"
            })
        
        # 最新值
        key_points.append({
            "date": dates[-1],
            "value": values[-1],
            "type": "最新",
            "description": f"最新值为 {values[-1]:.2f}"
        })
        
        return key_points
    
    def _extract_semantic_features(self, time_series: Dict[str, float]) -> Dict:
        """提取语义特征"""
        values = list(time_series.values())
        
        if not values:
            return {}
        
        # 计算统计特征
        mean_val = sum(values) / len(values)
        max_val = max(values)
        min_val = min(values)
        std_val = (sum((x - mean_val) ** 2 for x in values) / len(values)) ** 0.5
        
        # 计算变异系数
        cv = std_val / mean_val if mean_val > 0 else 0
        
        # 语义化特征
        growth_rate = "高" if (values[-1] - values[0]) / values[0] > 0.5 else "中等" if (values[-1] - values[0]) / values[0] > 0.1 else "低"
        stability = "高" if cv < 0.2 else "中等" if cv < 0.5 else "低"
        
        return {
            "growth_rate": growth_rate,
            "stability": stability,
            "volatility": "高" if cv > 0.5 else "低",
            "range": f"{min_val:.2f} - {max_val:.2f}"
        }
    
    def generate_summary(self, all_metrics: Dict[str, Dict]) -> str:
        """生成整体趋势总结"""
        # 简化版：只使用关键指标
        key_metrics = {}
        for name, data in all_metrics.items():
            if "OpenRank" in name or "活跃度" in name or "Star数" in name:
                key_metrics[name] = data
        
        if not key_metrics:
            return "暂无足够数据生成总结。"
        
        prompt = f"""
基于以下时序指标数据，生成一份项目发展趋势总结（200字以内）：

{json.dumps(key_metrics, ensure_ascii=False, indent=2)[:1000]}

请总结：
1. 整体发展趋势
2. 关键变化点
3. 未来展望
"""
        
        try:
            summary = self.llm_client.generate(prompt, max_tokens=500)
            return summary.strip()
        except Exception as e:
            print(f"生成总结失败: {e}")
            return "项目数据正在分析中..."
```

---

## 步骤4：集成到API

修改 `backend/app.py`，添加增强接口：

```python
# 在文件顶部添加导入
from LLM2TSA.enhancer import TimeSeriesEnhancer

# 创建增强器实例
enhancer = TimeSeriesEnhancer()

# 添加新的路由
@app.route('/api/enhance/<path:repo_key>/metric/<metric_name>', methods=['GET'])
def enhance_metric(repo_key, metric_name):
    """获取单个指标的增强信息"""
    try:
        # 获取时序数据
        grouped = data_service.get_grouped_timeseries(repo_key)
        
        # 查找指定指标
        metric_data = None
        for group in grouped.get('groups', {}).values():
            if metric_name in group.get('metrics', {}):
                metric_data = group['metrics'][metric_name]
                break
        
        if not metric_data:
            return jsonify({'error': f'未找到指标: {metric_name}'}), 404
        
        # 提取原始数据
        raw_data = {}
        for i, date in enumerate(grouped.get('timeAxis', [])):
            value = metric_data.get('data', [])[i]
            if value is not None:
                raw_data[date] = value
        
        # 生成增强信息
        enhanced = enhancer.enhance_metric(metric_name, raw_data)
        
        return jsonify(enhanced)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

---

## 步骤5：前端展示（可选）

在 `frontend/src/components/TimeSeriesChart.tsx` 中添加增强信息展示：

```typescript
// 添加状态
const [enhancedInfo, setEnhancedInfo] = useState<any>(null);

// 获取增强信息
useEffect(() => {
  if (metricName) {
    fetch(`/api/enhance/${repoKey}/metric/${metricName}`)
      .then(res => res.json())
      .then(data => setEnhancedInfo(data));
  }
}, [metricName]);

// 在组件中展示
{enhancedInfo && (
  <div className="mt-4 p-4 bg-gray-50 rounded-lg">
    <h3 className="font-semibold mb-2">指标说明</h3>
    <p className="text-sm text-gray-700">{enhancedInfo.description}</p>
    
    {enhancedInfo.trends && enhancedInfo.trends.length > 0 && (
      <div className="mt-3">
        <h4 className="font-medium mb-1">趋势分析</h4>
        {enhancedInfo.trends.map((trend: any, idx: number) => (
          <div key={idx} className="text-sm text-gray-600">
            {trend.description}
          </div>
        ))}
      </div>
    )}
  </div>
)}
```

---

## 步骤6：测试

创建测试脚本 `backend/test_enhancer.py`：

```python
"""测试增强器功能"""
from LLM2TSA.enhancer import TimeSeriesEnhancer

# 测试数据
test_data = {
    "2020-08": 4.76,
    "2020-09": 4.93,
    "2020-10": 5.03,
    "2020-11": 6.62,
    "2020-12": 12.65,
    "2021-01": 11.08,
    "2021-02": 5.81,
}

# 创建增强器
enhancer = TimeSeriesEnhancer()

# 测试增强
result = enhancer.enhance_metric("OpenRank", test_data)

print("=" * 60)
print("增强结果：")
print("=" * 60)
print(f"描述：{result['description']}")
print(f"\n趋势：")
for trend in result['trends']:
    print(f"  - {trend['description']}")
print(f"\n关键点：")
for point in result['key_points']:
    print(f"  - {point['date']}: {point['description']}")
print(f"\n语义特征：{result['semantic_features']}")
```

运行测试：

```bash
cd backend
python test_enhancer.py
```

---

## 下一步

1. **优化Prompt**：根据实际效果调整Prompt模板
2. **添加缓存**：避免重复调用LLM
3. **实现模式2**：时序预测功能
4. **实现模式3**：智能体分析功能

---

## 常见问题

### Q: LLM调用失败怎么办？

A: 增强器已经包含错误处理，失败时会返回默认描述。检查：
- DeepSeek API Key是否正确配置
- 网络连接是否正常
- API调用是否超限

### Q: 如何提高生成质量？

A: 
1. 优化Prompt，提供更多上下文
2. 使用更好的LLM模型（如GPT-4）
3. 添加few-shot示例

### Q: 性能如何优化？

A:
1. 添加缓存机制（相同输入缓存结果）
2. 批量处理多个指标
3. 异步调用LLM API

---

**祝开发顺利！** 🚀

