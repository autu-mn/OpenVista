"""
DeepSeek API 客户端
用于 LLM 摘要生成和预测解释
"""

import os
from typing import Optional
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 尝试导入 openai 库（DeepSeek 兼容 OpenAI API）
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class DeepSeekClient:
    """DeepSeek API 客户端"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "deepseek-chat"):
        """
        初始化 DeepSeek 客户端
        
        Args:
            api_key: DeepSeek API Key，默认从环境变量读取
            model: 模型名称，默认 deepseek-chat
        """
        self.api_key = api_key or os.getenv('DEEPSEEK_API_KEY') or os.getenv('DEEPSEEK_KEY')
        self.model = model
        self.base_url = "https://api.deepseek.com"
        
        if not self.api_key:
            raise ValueError("DeepSeek API Key 未配置，请设置 DEEPSEEK_API_KEY 环境变量")
        
        if not OPENAI_AVAILABLE:
            raise ImportError("需要安装 openai 库: pip install openai")
        
        # 初始化 OpenAI 客户端（DeepSeek 兼容 OpenAI API）
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
    
    def ask(self, prompt: str, context: str = "", system_prompt: str = None) -> str:
        """
        发送问题到 DeepSeek
        
        Args:
            prompt: 用户提问
            context: 上下文信息
            system_prompt: 系统提示（可选）
        
        Returns:
            AI 回复文本
        """
        messages = []
        
        # 添加系统提示
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        else:
            messages.append({
                "role": "system", 
                "content": "你是一个专业的 GitHub 项目分析助手，擅长分析开源项目数据并提供洞察。"
            })
        
        # 构建用户消息
        user_message = prompt
        if context:
            user_message = f"{context}\n\n{prompt}"
        
        messages.append({"role": "user", "content": user_message})
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=2000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            raise RuntimeError(f"DeepSeek API 调用失败: {e}")
    
    def generate_summary(self, text: str, max_length: int = 500) -> str:
        """
        生成文本摘要
        
        Args:
            text: 原始文本
            max_length: 摘要最大长度
        
        Returns:
            摘要文本
        """
        prompt = f"""请为以下内容生成一个简洁的摘要（不超过{max_length}字）：

{text[:5000]}  # 限制输入长度

要求：
1. 提取关键信息
2. 语言简洁明了
3. 保持专业性"""
        
        return self.ask(prompt)
    
    def analyze_trend(self, data: dict, metric_name: str) -> str:
        """
        分析数据趋势
        
        Args:
            data: 时序数据字典 {"2024-01": 5.2, ...}
            metric_name: 指标名称
        
        Returns:
            趋势分析文本
        """
        prompt = f"""分析以下 {metric_name} 数据的趋势：

数据: {data}

请提供：
1. 整体趋势描述
2. 关键变化点
3. 可能的原因分析
4. 未来趋势预测"""
        
        return self.ask(prompt)


def get_deepseek_client() -> Optional[DeepSeekClient]:
    """
    获取 DeepSeek 客户端实例
    
    Returns:
        DeepSeekClient 实例，如果不可用则返回 None
    """
    try:
        return DeepSeekClient()
    except (ValueError, ImportError) as e:
        print(f"[WARN] DeepSeek 客户端初始化失败: {e}")
        return None






