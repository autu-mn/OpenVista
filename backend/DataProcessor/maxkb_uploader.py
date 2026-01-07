"""
MaxKB 知识库自动上传模块
支持登录认证和文件上传到MaxKB知识库
"""

import requests
import os
from typing import Optional, Dict
import json
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class MaxKBUploader:
    """MaxKB知识库上传器"""
    
    def __init__(self, base_url: str = None, 
                 username: str = None, 
                 password: str = None,
                 knowledge_id: str = None):
        """
        初始化MaxKB上传器
        
        Args:
            base_url: MaxKB服务地址，默认从环境变量MAXKB_URL读取，或 http://localhost:8080
            username: 登录用户名，默认从环境变量MAXKB_USERNAME读取，或 admin
            password: 登录密码，默认从环境变量MAXKB_PASSWORD读取（必须提供）
            knowledge_id: 知识库ID，默认从环境变量MAXKB_KNOWLEDGE_ID读取，如果为None需要手动设置
        """
        self.base_url = (base_url or os.getenv('MAXKB_URL', 'http://localhost:8080')).rstrip('/')
        self.username = username or os.getenv('MAXKB_USERNAME', 'admin')
        self.password = password or os.getenv('MAXKB_PASSWORD')
        self.knowledge_id = knowledge_id or os.getenv('MAXKB_KNOWLEDGE_ID')
        
        if not self.password:
            raise ValueError("密码未提供，请设置 MAXKB_PASSWORD 环境变量或在初始化时提供 password 参数")
        self.session = requests.Session()
        self.token = None
        self.workspace = "default"  # 默认工作空间
        
    def login(self) -> bool:
        """
        登录MaxKB并获取认证token
        
        Returns:
            bool: 登录是否成功
        """
        try:
            # MaxKB登录API通常是 /api/user/login 或 /admin/api/user/login
            login_urls = [
                f"{self.base_url}/admin/api/user/login",
                f"{self.base_url}/api/user/login",
                f"{self.base_url}/api/auth/login"
            ]
            
            login_data = {
                "username": self.username,
                "password": self.password
            }
            
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            # 尝试不同的登录端点
            for login_url in login_urls:
                try:
                    response = self.session.post(
                        login_url,
                        json=login_data,
                        headers=headers,
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        # 尝试从响应中获取token
                        try:
                            result = response.json()
                        except:
                            result = None
                        
                        if result is None:
                            # 可能没有返回JSON，尝试使用Cookie
                            cookies = response.cookies
                            if cookies:
                                self.session.cookies.update(cookies)
                                print(f"[OK] MaxKB登录成功（使用Cookie认证）")
                                return True
                            continue
                        
                        # 可能的token字段名
                        token = None
                        if isinstance(result, dict):
                            token = result.get('token') or result.get('access_token')
                            if not token and result.get('data'):
                                data = result.get('data')
                                if isinstance(data, dict):
                                    token = data.get('token')
                        
                        if token:
                            self.token = token
                            # 设置session的Authorization header
                            self.session.headers.update({
                                "Authorization": f"Bearer {self.token}"
                            })
                            print(f"[OK] MaxKB登录成功")
                            return True
                        else:
                            # 如果响应中没有token，可能token在cookie中
                            # 检查Set-Cookie header
                            cookies = response.cookies
                            if cookies:
                                self.session.cookies.update(cookies)
                                print(f"[OK] MaxKB登录成功（使用Cookie认证）")
                                return True
                            
                except requests.exceptions.RequestException as e:
                    continue
            
            print(f"[ERROR] MaxKB登录失败：无法找到有效的登录端点")
            return False
            
        except Exception as e:
            print(f"[ERROR] MaxKB登录失败：{str(e)}")
            return False
    
    def set_knowledge_id(self, knowledge_id: str):
        """设置知识库ID"""
        self.knowledge_id = knowledge_id
    
    def set_token(self, token: str):
        """
        手动设置认证token（从浏览器F12获取）
        
        Args:
            token: Bearer token字符串（不需要包含"Bearer "前缀）
        """
        self.token = token
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}"
        })
        print(f"[OK] 已设置MaxKB认证token")
    
    def _find_document_by_source_id(self, source_file_id: str, file_name: str):
        """通过source_file_id查找文档ID"""
        try:
            list_url = (
                f"{self.base_url}/admin/api/workspace/{self.workspace}/"
                f"knowledge/{self.knowledge_id}/document"
            )
            list_headers = {}
            if self.token:
                list_headers["Authorization"] = f"Bearer {self.token}"
            
            list_response = self.session.get(list_url, headers=list_headers, timeout=10)
            if list_response.status_code == 200:
                list_result = list_response.json()
                if isinstance(list_result, dict) and 'data' in list_result:
                    docs = list_result['data']
                    # 查找匹配的文档
                    for doc in docs:
                        if isinstance(doc, dict):
                            doc_meta = doc.get('meta', {})
                            doc_source_id = doc_meta.get('source_file_id')
                            doc_name = doc.get('name', '')
                            
                            if doc_source_id == source_file_id or doc_name == file_name:
                                return doc.get('id')
            return None
        except Exception as e:
            print(f"[WARN] 查找文档失败: {e}")
            return None
    
    def _create_document_from_split_result(self, file_name: str, split_data: dict):
        """直接从split结果创建文档"""
        try:
            create_url = (
                f"{self.base_url}/admin/api/workspace/{self.workspace}/"
                f"knowledge/{self.knowledge_id}/document"
            )
            
            create_data = {
                'name': file_name,
                'data': [split_data]  # 直接使用split返回的数据
            }
            
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            
            create_response = self.session.post(
                create_url,
                json=create_data,
                headers=headers,
                timeout=30
            )
            
            if create_response.status_code in [200, 201]:
                create_result = create_response.json()
                print(f"[OK] 文档创建成功（从split结果）")
                return True
            else:
                print(f"[ERROR] 从split结果创建失败：HTTP {create_response.status_code}")
                return False
        except Exception as e:
            print(f"[ERROR] 从split结果创建出错: {e}")
            return False
    
    def upload_document(self, file_path: str, chunk_size: int = 500, document_name: str = None) -> bool:
        """
        上传文档到MaxKB知识库
        
        Args:
            file_path: 要上传的文件路径
            chunk_size: 文档分块大小（字符数），默认500
            document_name: 文档名称（可选，默认使用文件名）
            
        Returns:
            bool: 上传是否成功
        """
        if not self.token and not self.session.cookies:
            print("[ERROR] 未登录，请先调用login()方法")
            return False
        
        if not self.knowledge_id:
            print("[ERROR] 未设置知识库ID，请先调用set_knowledge_id()方法")
            return False
        
        if not os.path.exists(file_path):
            print(f"[ERROR] 文件不存在：{file_path}")
            return False
        
        try:
            # 构建上传URL
            upload_url = (
                f"{self.base_url}/admin/api/workspace/{self.workspace}/"
                f"knowledge/{self.knowledge_id}/document/split"
            )
            
            # 准备文件上传
            file_name = document_name if document_name else os.path.basename(file_path)
            
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
            
            # 准备multipart/form-data
            files = {
                'file': (file_name, file_content.encode('utf-8'), 'text/plain')
            }
            
            # 准备表单数据
            data = {
                'chunk_size': str(chunk_size),
                'chunk_overlap': '50'  # 默认重叠50字符
            }
            
            # 设置请求头
            headers = {
                "Accept": "application/json, text/plain, */*",
                "Referer": f"{self.base_url}/admin/knowledge/document/upload/{self.workspace}?id={self.knowledge_id}",
                "Origin": self.base_url
            }
            
            # 如果已有token，添加到headers
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            
            # 发送上传请求
            response = self.session.post(
                upload_url,
                files=files,
                data=data,
                headers=headers,
                timeout=60
            )
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    
                    # MaxKB API返回格式: {'code': 200, 'message': '成功', 'data': [...]}
                    if isinstance(result, dict) and 'data' in result:
                        data = result['data']
                        if isinstance(data, list) and len(data) > 0:
                            # 获取第一个文档的source_file_id和内容
                            first_doc = data[0]
                            source_file_id = first_doc.get('source_file_id')
                            content_list = first_doc.get('content', [])
                            
                            if source_file_id:
                                # 根据抓包信息，创建文档使用 PUT /document/batch_create API
                                print(f"[INFO] 文件已解析，source_file_id: {source_file_id}")
                                print(f"[INFO] 正在创建文档记录...")
                                
                                # 使用正确的API端点：PUT /document/batch_create
                                create_url = (
                                    f"{self.base_url}/admin/api/workspace/{self.workspace}/"
                                    f"knowledge/{self.knowledge_id}/document/batch_create"
                                )
                                
                                # 构建创建文档的数据
                                # 根据抓包信息，batch_create需要传递split返回的数据数组
                                # 更新文档名称，确保content数据完整传递
                                first_doc_copy = first_doc.copy()
                                first_doc_copy['name'] = file_name  # 使用指定的文档名称
                                
                                # 确保content数据存在且格式正确
                                if not first_doc_copy.get('content') or len(first_doc_copy.get('content', [])) == 0:
                                    print(f"[WARN] split返回的content为空，尝试重新构建content数据")
                                    # 如果content为空，尝试从文件内容重新构建
                                    with open(file_path, 'r', encoding='utf-8') as f:
                                        file_content = f.read()
                                    # 简单分割（按段落）
                                    paragraphs = file_content.split('\n\n')
                                    first_doc_copy['content'] = [
                                        {'title': '', 'content': para.strip()} 
                                        for para in paragraphs if para.strip()
                                    ]
                                
                                # 确保content数组中的每个段落都有正确的格式
                                if first_doc_copy.get('content'):
                                    # 验证并清理content数据
                                    cleaned_content = []
                                    for para in first_doc_copy.get('content', []):
                                        if isinstance(para, dict):
                                            para_content = para.get('content', '')
                                            if para_content and para_content.strip():
                                                cleaned_content.append({
                                                    'title': para.get('title', ''),
                                                    'content': para_content.strip()
                                                })
                                    first_doc_copy['content'] = cleaned_content
                                
                                create_data = [first_doc_copy]
                                
                                create_headers = {
                                    "Content-Type": "application/json",
                                    "Accept": "application/json"
                                }
                                if self.token:
                                    create_headers["Authorization"] = f"Bearer {self.token}"
                                
                                # 使用PUT方法调用batch_create API
                                create_response = self.session.put(
                                    create_url,
                                    json=create_data,
                                    headers=create_headers,
                                    timeout=60  # 大文件可能需要更长时间
                                )
                                
                                create_result = create_response.json()
                                
                                # 检查响应
                                if isinstance(create_result, dict):
                                    result_code = create_result.get('code', create_response.status_code)
                                    if result_code == 200:
                                        print(f"[OK] 文件上传成功：{file_name}")
                                        
                                        # 提取文档ID
                                        doc_id = None
                                        if 'data' in create_result:
                                            doc_data = create_result['data']
                                            if isinstance(doc_data, dict):
                                                doc_id = doc_data.get('id')
                                            elif isinstance(doc_data, list) and len(doc_data) > 0:
                                                # batch_create可能返回多个文档ID
                                                doc_id = doc_data[0].get('id')
                                        
                                        if doc_id:
                                            print(f"  文档ID：{doc_id}")
                                            print(f"  文档链接：{self.base_url}/admin/paragraph/{self.knowledge_id}/{doc_id}?from=workspace&isShared=false")
                                        else:
                                            # 如果没有返回ID，等待后从文档列表中查找
                                            print(f"[INFO] 等待文档处理完成...")
                                            import time
                                            time.sleep(5)  # 等待更长时间让段落处理完成
                                            doc_id = self._find_document_by_source_id(source_file_id, file_name)
                                            if doc_id:
                                                print(f"  文档ID：{doc_id}")
                                                print(f"  文档链接：{self.base_url}/admin/paragraph/{self.knowledge_id}/{doc_id}?from=workspace&isShared=false")
                                        
                                        # 尝试单独创建段落（如果batch_create没有自动创建）
                                        if content_list and len(content_list) > 0:
                                            print(f"[INFO] 文档包含 {len(content_list)} 个段落")
                                            
                                            # 检查是否需要单独创建段落
                                            import time
                                            time.sleep(3)  # 等待文档创建完成
                                            
                                            # 尝试通过段落API创建段落
                                            try:
                                                # 获取文档ID
                                                para_doc_id = doc_id
                                                if not para_doc_id:
                                                    para_doc_id = self._find_document_by_source_id(source_file_id, file_name)
                                                
                                                if not para_doc_id:
                                                    print(f"[ERROR] 无法获取文档ID，跳过段落创建")
                                                    return True
                                                
                                                # 使用带document_id的段落API URL（格式1总是404，直接使用格式2）
                                                paragraph_url = (
                                                    f"{self.base_url}/admin/api/workspace/{self.workspace}/"
                                                    f"knowledge/{self.knowledge_id}/document/{para_doc_id}/paragraph"
                                                )
                                                
                                                if para_doc_id:
                                                    print(f"[INFO] 检查段落是否需要单独创建...")
                                                    
                                                    # 先检查是否已有段落
                                                    check_para_url = (
                                                        f"{self.base_url}/admin/api/workspace/{self.workspace}/"
                                                        f"knowledge/{self.knowledge_id}/paragraph"
                                                    )
                                                    check_headers = {}
                                                    if self.token:
                                                        check_headers["Authorization"] = f"Bearer {self.token}"
                                                    
                                                    check_response = self.session.get(check_para_url, headers=check_headers, timeout=10)
                                                    existing_paras = []
                                                    if check_response.status_code == 200:
                                                        check_result = check_response.json()
                                                        if isinstance(check_result, dict) and 'data' in check_result:
                                                            existing_paras = [p for p in check_result['data'] if isinstance(p, dict) and p.get('document_id') == para_doc_id]
                                                        elif isinstance(check_result, list):
                                                            existing_paras = [p for p in check_result if isinstance(p, dict) and p.get('document_id') == para_doc_id]
                                                    
                                                    # 如果段落为空或数量不匹配，尝试创建段落
                                                    if len(existing_paras) == 0 or len(existing_paras) < len(content_list):
                                                        print(f"[INFO] 尝试为文档创建段落...")
                                                        # 为每个段落创建记录
                                                        created_paras = 0
                                                        for idx, para_item in enumerate(content_list):
                                                            if isinstance(para_item, dict):
                                                                para_content = para_item.get('content', '').strip()
                                                                if para_content:  # 只创建有内容的段落
                                                                    para_data = {
                                                                        'document_id': para_doc_id,
                                                                        'content': para_content,
                                                                        'title': para_item.get('title', '').strip(),
                                                                        'order': idx
                                                                    }
                                                                    
                                                                    para_headers = {
                                                                        "Content-Type": "application/json",
                                                                        "Accept": "application/json"
                                                                    }
                                                                    if self.token:
                                                                        para_headers["Authorization"] = f"Bearer {self.token}"
                                                                    
                                                                    try:
                                                                        para_response = self.session.post(
                                                                            paragraph_url,
                                                                            json=para_data,
                                                                            headers=para_headers,
                                                                            timeout=30
                                                                        )
                                                                        
                                                                        if para_response.status_code in [200, 201]:
                                                                            para_result = para_response.json()
                                                                            if para_result.get('code') == 200:
                                                                                created_paras += 1
                                                                                # 每100个段落显示一次进度
                                                                                if (idx + 1) % 100 == 0 or idx < 3:
                                                                                    print(f"[INFO] 已创建 {created_paras}/{idx+1} 个段落...")
                                                                            else:
                                                                                if idx < 10:  # 只打印前10个失败信息
                                                                                    print(f"[WARN] 段落{idx+1}创建失败: code {para_result.get('code')}, message {para_result.get('message', '未知')}")
                                                                        else:
                                                                            if idx < 10:  # 只打印前10个失败信息
                                                                                error_text = para_response.text[:200] if hasattr(para_response, 'text') else '未知错误'
                                                                                print(f"[WARN] 段落{idx+1}创建失败: {para_response.status_code}, {error_text}")
                                                                    except Exception as e:
                                                                        if idx < 10:  # 只打印前10个错误
                                                                            print(f"[WARN] 创建段落{idx+1}时出错: {e}")
                                                                    
                                                                    # 避免请求过快，每50个段落暂停一下
                                                                    if (idx + 1) % 50 == 0:
                                                                        time.sleep(0.3)
                                                        
                                                        if created_paras > 0:
                                                            print(f"[OK] 成功创建 {created_paras} 个段落")
                                                        else:
                                                            print(f"[INFO] 段落可能已由batch_create自动创建，或需要等待处理")
                                                    else:
                                                        print(f"[INFO] 文档已有 {len(existing_paras)} 个段落，无需重复创建")
                                            except Exception as e:
                                                print(f"[WARN] 创建段落时出错（可能已自动创建）: {e}")
                                            
                                            print(f"[INFO] 段落处理可能需要10-30秒，请稍后刷新页面查看")
                                        else:
                                            print(f"[WARN] 文档没有段落内容，可能是文件为空或split失败")
                                        
                                        return True
                                    else:
                                        error_msg = create_result.get('message', '未知错误')
                                        print(f"[ERROR] 创建文档失败：code {result_code}, {error_msg}")
                                        if '模型不存在' in error_msg or result_code == 500:
                                            print(f"[HINT] 请在 MaxKB 管理界面为知识库配置嵌入模型！")
                                        return False
                                else:
                                    print(f"[ERROR] 创建文档响应格式错误")
                                    return False
                            else:
                                print(f"[WARN] 未找到source_file_id，尝试直接使用split结果创建文档")
                                # 如果没有source_file_id，尝试直接使用split的结果
                                return self._create_document_from_split_result(file_name, first_doc)
                        else:
                            print(f"[WARN] split返回的数据为空")
                            return False
                    else:
                        # 兼容旧格式
                        print(f"[OK] 文件上传成功：{file_name}")
                        return True
                        
                except Exception as e:
                    print(f"[WARN] 解析响应JSON失败: {e}")
                    # 即使JSON解析失败，如果状态码是200，也认为成功
                    return True
            else:
                print(f"[ERROR] 文件上传失败：HTTP {response.status_code}")
                return False
                
        except Exception as e:
            print(f"[ERROR] 文件上传失败：{str(e)}")
            return False
    
    def upload_text_file(self, file_path: str, chunk_size: int = 500, document_name: str = None) -> bool:
        """
        上传文本文件到MaxKB（便捷方法）
        
        Args:
            file_path: 文本文件路径
            chunk_size: 分块大小
            document_name: 文档名称（可选）
            
        Returns:
            bool: 上传是否成功
        """
        return self.upload_document(file_path, chunk_size, document_name)


def upload_to_maxkb(file_path: str, 
                    base_url: str = None,
                    username: str = None,
                    password: str = None,
                    knowledge_id: str = None,
                    chunk_size: int = 500) -> bool:
    """
    便捷函数：上传文件到MaxKB
    
    Args:
        file_path: 要上传的文件路径
        base_url: MaxKB服务地址，默认从环境变量MAXKB_URL读取
        username: 登录用户名，默认从环境变量MAXKB_USERNAME读取
        password: 登录密码，默认从环境变量MAXKB_PASSWORD读取（必须提供）
        knowledge_id: 知识库ID，默认从环境变量MAXKB_KNOWLEDGE_ID读取
        chunk_size: 文档分块大小
        
    Returns:
        bool: 上传是否成功
    """
    uploader = MaxKBUploader(base_url, username, password, knowledge_id)
    
    if not uploader.login():
        return False
    
    if not knowledge_id:
        print("⚠ 警告：未提供知识库ID，请先设置")
        return False
    
    return uploader.upload_text_file(file_path, chunk_size)


if __name__ == "__main__":
    # 测试示例 - 从环境变量读取配置
    # 请确保已设置 MAXKB_URL, MAXKB_USERNAME, MAXKB_PASSWORD, MAXKB_KNOWLEDGE_ID 环境变量
    uploader = MaxKBUploader()
    
    if uploader.login():
        uploader.upload_text_file("test.txt", chunk_size=500)
    else:
        print("登录失败，请检查环境变量配置")

