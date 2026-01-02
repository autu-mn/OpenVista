"""
MaxKB AI 客户端
使用 MaxKB 的原生 API 进行智能问答
"""
import os
import requests
import logging
from typing import Dict, Optional
from pathlib import Path

from dotenv import load_dotenv

# 查找项目根目录的 .env 文件
def find_dotenv():
    """向上查找 .env 文件"""
    current = Path(__file__).resolve().parent
    for _ in range(5):  # 最多向上查找5层
        env_file = current / '.env'
        if env_file.exists():
            return str(env_file)
        current = current.parent
    return None

# 加载 .env 文件
env_path = find_dotenv()
if env_path:
    load_dotenv(env_path)
else:
    load_dotenv()  # 尝试默认加载

logger = logging.getLogger(__name__)


class MaxKBClient:
    """MaxKB AI API 客户端"""
    
    def __init__(self, base_url: str = None, api_key: str = None):
        """
        初始化 MaxKB 客户端
        
        配置方式：
        - MAXKB_AI_URL = MaxKB 服务地址（如 http://localhost:8080）
        - MAXKB_API_KEY = 应用访问密钥（如 application-c527aa669276e38ab7880b1f43255c9a）
        
        Args:
            base_url: MaxKB 服务地址
            api_key: 应用访问密钥
        """
        # 获取环境变量（支持多种命名）
        # 优先使用 MAXKB_URL（纯服务器地址），因为 MAXKB_AI_URL 可能包含应用路径
        raw_url = base_url or os.getenv('MAXKB_URL', '') or os.getenv('MAXKB_AI_URL', '')
        self.api_key = api_key or os.getenv('MAXKB_API_KEY', '') or os.getenv('MAXKB_AI_API_KEY', '') or os.getenv('MAXKB_AI_KEY', '')
        
        # 从 URL 中提取纯服务器地址（去除 /chat/api/... 路径）
        # 例如：http://localhost:8080/chat/api/xxx -> http://localhost:8080
        import re
        match = re.match(r'(https?://[^/]+)', raw_url)
        if match:
            self.base_url = match.group(1)
        else:
            self.base_url = raw_url.rstrip('/')
        
        if not self.base_url:
            raise ValueError(
                "未找到 MaxKB 服务地址，请设置环境变量：\n"
                "MAXKB_AI_URL=http://localhost:8080\n"
                "MAXKB_API_KEY=application-xxxxxxxx"
            )
        
        if not self.api_key:
            raise ValueError(
                "未找到 MaxKB API Key，请设置环境变量：\n"
                "MAXKB_API_KEY=application-xxxxxxxx"
            )
        
        # 确保 api_key 格式正确
        if not self.api_key.startswith('application-'):
            self.api_key = f"application-{self.api_key}"
        
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # 缓存会话 ID
        self._chat_id = None
        
        logger.info(f"[MaxKB] 客户端初始化成功，服务地址: {self.base_url}")
    
    def _get_chat_id(self) -> Optional[str]:
        """获取会话 ID"""
        if self._chat_id:
            return self._chat_id
        
        try:
            url = f"{self.base_url}/chat/api/open"
            logger.debug(f"[MaxKB] 获取会话 ID: {url}")
            
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 200:
                    self._chat_id = result.get('data')
                    logger.info(f"[MaxKB] 获取会话 ID 成功: {self._chat_id}")
                    return self._chat_id
                else:
                    logger.error(f"[MaxKB] 获取会话 ID 失败: {result}")
            else:
                logger.error(f"[MaxKB] 获取会话 ID 失败: HTTP {response.status_code}")
                
        except Exception as e:
            logger.exception(f"[MaxKB] 获取会话 ID 异常: {e}")
        
        return None
    
    def ask(self, question: str, context: str = None) -> str:
        """
        发送问题并获取回答
        
        完全依赖 MaxKB 的知识库和提示词配置，只发送用户原始问题
        
        Args:
            question: 用户问题
            context: 忽略，由 MaxKB 知识库提供上下文
            
        Returns:
            AI 回答文本（已过滤思考过程）
        """
        # 只发送用户原始问题，让 MaxKB 使用其知识库和提示词模板
        result = self.send_message(question)
        
        if "error" in result:
            return f"抱歉，AI 调用失败：{result['error']}"
        
        # 获取内容并过滤思考过程
        content = result.get("content", "抱歉，无法获取回答。")
        content = self._filter_reasoning_content(content)
        
        return content
    
    def _filter_reasoning_content(self, content: str) -> str:
        """过滤掉思考过程内容，只保留最终回答"""
        import re
        
        # 过滤 <think>...</think> 标签
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        
        # 过滤 <thinking>...</thinking> 标签
        content = re.sub(r'<thinking>.*?</thinking>', '', content, flags=re.DOTALL)
        
        # 过滤 **思考过程** 或 ## 思考 等格式
        content = re.sub(r'\*\*思考.*?\*\*.*?(?=\n\n|\n#|$)', '', content, flags=re.DOTALL)
        content = re.sub(r'#{1,3}\s*思考.*?(?=\n#{1,3}[^#]|\n\n[^#]|$)', '', content, flags=re.DOTALL)
        
        # 过滤以"让我"、"我来"、"首先我"等开头的思考段落
        lines = content.split('\n')
        filtered_lines = []
        skip_until_blank = False
        
        for line in lines:
            stripped = line.strip()
            # 检测思考过程开始
            if any(stripped.startswith(prefix) for prefix in ['让我', '我来', '首先我', '我需要', '我先']):
                skip_until_blank = True
                continue
            # 遇到空行或标题时停止跳过
            if skip_until_blank and (not stripped or stripped.startswith('#')):
                skip_until_blank = False
            if not skip_until_blank:
                filtered_lines.append(line)
        
        content = '\n'.join(filtered_lines)
        
        # 清理多余空行
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        return content.strip()
    
    def send_message(self, message: str, stream: bool = True, timeout: int = 60) -> Dict:
        """
        直接发送消息到 MaxKB
        
        Args:
            message: 用户消息
            stream: 是否使用流式响应
            timeout: 超时时间（秒）
            
        Returns:
            响应字典
        """
        # 获取会话 ID
        chat_id = self._get_chat_id()
        if not chat_id:
            return {"error": "无法获取会话 ID，请检查 MaxKB 配置"}
        
        try:
            url = f"{self.base_url}/chat/api/chat_message/{chat_id}"
            
            payload = {
                "message": message,
                "stream": stream,
                "re_chat": False
            }
            
            logger.info(f"[MaxKB] 发送消息到: {url}")
            logger.debug(f"[MaxKB] 消息内容: {message[:100]}...")
            
            response = requests.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=timeout
            )
            
            logger.info(f"[MaxKB] 响应状态: {response.status_code}")
            
            if response.status_code == 200:
                # MaxKB 返回 SSE 流式响应
                content_type = response.headers.get('content-type', '')
                logger.debug(f"[MaxKB] Content-Type: {content_type}")
                
                # 尝试解析 SSE 流
                full_content = ""
                response_text = response.text
                
                # SSE 格式: data: {...}\n\n
                for line in response_text.split('\n'):
                    line = line.strip()
                    if line.startswith('data:'):
                        try:
                            import json
                            data_str = line[5:].strip()
                            if data_str:
                                data = json.loads(data_str)
                                if isinstance(data, dict) and 'content' in data:
                                    full_content += data['content']
                        except json.JSONDecodeError:
                            pass
                
                if full_content:
                    logger.info(f"[MaxKB] 成功获取回答，长度: {len(full_content)}")
                    return {"content": full_content}
                
                # 如果不是 SSE，尝试解析 JSON
                try:
                    result = response.json()
                    code = result.get('code', 200)
                    
                    # 检查业务码
                    if code == 500:
                        # 业务逻辑错误
                        data = result.get('data', {})
                        error_content = data.get('content', '') if isinstance(data, dict) else str(data)
                        if 'Exception' in error_content:
                            logger.error(f"[MaxKB] 服务端异常: {error_content}")
                            return {"error": f"MaxKB 服务异常，请检查 MaxKB 配置。错误: {error_content}"}
                        return {"error": f"API 返回错误(code={code}): {result.get('message', result)}"}
                    
                    if code == 200:
                        data = result.get('data', {})
                        if isinstance(data, dict):
                            content = data.get('content', '')
                            if content and 'Exception' not in content:
                                return {"content": content}
                            elif not content:
                                return {"content": str(data)}
                            else:
                                # content 包含异常信息
                                return {"error": f"MaxKB 返回异常: {content}"}
                        elif isinstance(data, str):
                            return {"content": data}
                        return {"content": str(data)}
                    else:
                        return {"error": f"API 返回错误: {result.get('message', result)}"}
                except:
                    # 返回原始文本
                    if response_text:
                        return {"content": response_text}
                    return {"error": "无法解析响应"}
            else:
                error_msg = f"API 调用失败: HTTP {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f" - {error_detail}"
                except:
                    error_msg += f" - {response.text[:200]}"
                logger.error(f"[MaxKB] {error_msg}")
                
                # 如果是会话相关错误，清除缓存的 chat_id
                if response.status_code in [401, 403, 404]:
                    self._chat_id = None
                    
                return {"error": error_msg}
                
        except requests.Timeout:
            error_msg = f"请求超时（{timeout}秒）"
            logger.error(f"[MaxKB] {error_msg}")
            return {"error": error_msg}
        except requests.ConnectionError as e:
            error_msg = f"连接失败: {str(e)}"
            logger.error(f"[MaxKB] {error_msg}")
            return {"error": error_msg}
        except Exception as e:
            error_msg = f"请求异常: {str(e)}"
            logger.exception(f"[MaxKB] {error_msg}")
            return {"error": error_msg}
    
    def is_available(self) -> bool:
        """
        检查 MaxKB 服务是否可用
        
        Returns:
            是否可用
        """
        try:
            chat_id = self._get_chat_id()
            return chat_id is not None
        except Exception as e:
            logger.warning(f"[MaxKB] 服务不可用: {e}")
            return False


# 单例实例
_client: Optional[MaxKBClient] = None


def get_maxkb_client() -> Optional[MaxKBClient]:
    """
    获取 MaxKB 客户端单例
    
    Returns:
        MaxKBClient 实例，如果未配置则返回 None
    """
    global _client
    
    if _client is None:
        try:
            _client = MaxKBClient()
        except ValueError as e:
            logger.warning(f"[MaxKB] 客户端初始化失败: {e}")
            return None
    
    return _client
