"""DeepSeek AI 客户端"""
import os
import requests
from typing import Dict, List
from dotenv import load_dotenv

load_dotenv()


class DeepSeekClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('DEEPSEEK_KEY')
        if not self.api_key:
            raise ValueError("未找到 DeepSeek API Key，请设置 DEEPSEEK_KEY 环境变量")
        
        self.base_url = "https://api.deepseek.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def chat(self, messages: List[Dict[str, str]], 
             model: str = "deepseek-chat",
             temperature: float = 0.7,
             max_tokens: int = 2000) -> Dict:
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens
                },
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"API调用失败: {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}
    
    def ask(self, question: str, context: str = None) -> str:
        messages = []
        
        if context:
            messages.append({
                "role": "system",
                "content": f"你是一个GitHub仓库数据分析助手。以下是相关的项目数据：\n\n{context}\n\n请基于这些数据回答用户的问题。"
            })
        else:
            messages.append({
                "role": "system",
                "content": "你是一个GitHub仓库数据分析助手，帮助用户理解项目数据。"
            })
        
        messages.append({"role": "user", "content": question})
        
        result = self.chat(messages)
        
        if "error" in result:
            return f"抱歉，AI调用失败：{result['error']}"
        
        try:
            return result["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            return "抱歉，无法解析AI响应。"
