"""
验证 GitHub Tokens 是否来自不同账户
运行此脚本检查你的 tokens 配置是否正确
"""
import os
import requests
from dotenv import load_dotenv
from tabulate import tabulate

load_dotenv()

def verify_tokens():
    """验证所有 GitHub tokens"""
    tokens = []
    
    # 加载所有 tokens
    main_token = os.getenv('GITHUB_TOKEN')
    if main_token:
        tokens.append(('GITHUB_TOKEN', main_token))
    
    for i in range(1, 7):
        token = os.getenv(f'GITHUB_TOKEN_{i}')
        if token:
            tokens.append((f'GITHUB_TOKEN_{i}', token))
    
    if not tokens:
        print("❌ 错误: 未找到任何 GitHub Token")
        print("请在 backend/.env 文件中配置 GITHUB_TOKEN")
        return
    
    print(f"✅ 找到 {len(tokens)} 个 tokens\n")
    print("="*80)
    
    results = []
    user_ids = set()
    
    for token_name, token in tokens:
        print(f"\n检查 {token_name}...")
        
        headers = {'Authorization': f'token {token}'}
        
        # 获取用户信息
        try:
            user_response = requests.get('https://api.github.com/user', headers=headers, timeout=10)
            
            if user_response.status_code == 200:
                user_data = user_response.json()
                username = user_data.get('login', 'N/A')
                user_id = user_data.get('id', 'N/A')
                account_type = user_data.get('type', 'N/A')
                
                user_ids.add(user_id)
                
                # 获取 rate limit 信息
                rate_response = requests.get('https://api.github.com/rate_limit', headers=headers, timeout=10)
                
                if rate_response.status_code == 200:
                    rate_data = rate_response.json()
                    core = rate_data['resources']['core']
                    graphql = rate_data['resources']['graphql']
                    
                    rest_remaining = core['remaining']
                    rest_limit = core['limit']
                    rest_percent = (rest_remaining / rest_limit * 100) if rest_limit > 0 else 0
                    
                    graphql_remaining = graphql['remaining']
                    graphql_limit = graphql['limit']
                    graphql_percent = (graphql_remaining / graphql_limit * 100) if graphql_limit > 0 else 0
                    
                    results.append([
                        token_name,
                        username,
                        user_id,
                        f"{rest_remaining}/{rest_limit} ({rest_percent:.1f}%)",
                        f"{graphql_remaining}/{graphql_limit} ({graphql_percent:.1f}%)"
                    ])
                    
                    print(f"  ✅ 用户: {username} (ID: {user_id})")
                    print(f"  📊 REST API: {rest_remaining}/{rest_limit} ({rest_percent:.1f}%)")
                    print(f"  📊 GraphQL: {graphql_remaining}/{graphql_limit} ({graphql_percent:.1f}%)")
                else:
                    print(f"  ⚠️ 无法获取 rate limit 信息")
                    results.append([
                        token_name,
                        username,
                        user_id,
                        "N/A",
                        "N/A"
                    ])
            elif user_response.status_code == 401:
                print(f"  ❌ Token 无效或已过期")
                results.append([token_name, "❌ 无效", "N/A", "N/A", "N/A"])
            else:
                print(f"  ❌ 错误: HTTP {user_response.status_code}")
                results.append([token_name, "❌ 错误", "N/A", "N/A", "N/A"])
        
        except requests.exceptions.RequestException as e:
            print(f"  ❌ 请求失败: {e}")
            results.append([token_name, "❌ 请求失败", "N/A", "N/A", "N/A"])
    
    # 输出汇总表格
    print("\n" + "="*80)
    print("\n📋 Tokens 汇总表:")
    print()
    headers = ["Token 名称", "用户名", "用户 ID", "REST API 剩余", "GraphQL 剩余"]
    print(tabulate(results, headers=headers, tablefmt="grid"))
    
    # 分析结果
    print("\n" + "="*80)
    print("\n🔍 分析结果:")
    print()
    
    unique_user_ids = len(user_ids)
    total_tokens = len([r for r in results if r[1] != "❌ 无效" and r[1] != "❌ 错误" and r[1] != "❌ 请求失败"])
    
    if unique_user_ids == 0:
        print("❌ 所有 tokens 都无效或无法访问")
        print("   → 请检查 tokens 是否正确配置")
    elif unique_user_ids == 1:
        print(f"⚠️  警告: 所有 {total_tokens} 个 tokens 都来自同一个账户!")
        print(f"   用户 ID: {list(user_ids)[0]}")
        print()
        print("   这意味着:")
        print("   • 所有 tokens 共享同一个 rate limit (5000次/小时)")
        print("   • 无法通过添加更多 tokens 来提高爬取速度")
        print("   • 很容易触发 rate limit")
        print()
        print("   ✅ 解决方案:")
        print("   1. 创建多个不同的 GitHub 账户")
        print("   2. 为每个账户生成一个 token")
        print("   3. 将这些 tokens 添加到 .env 文件")
        print()
        print("   参考文档: CRITICAL_RATE_LIMIT_WARNING.md")
    else:
        print(f"✅ 太好了! 你有 {unique_user_ids} 个不同账户的 tokens")
        print(f"   → 总 rate limit: {unique_user_ids} × 5000 = {unique_user_ids * 5000} 次/小时")
        print()
        print("   这意味着:")
        print("   • 可以并发使用多个 tokens")
        print("   • rate limit 是单个账户的 {unique_user_ids} 倍")
        print("   • 爬取速度显著提升")
    
    print("\n" + "="*80)
    
    # 检查是否需要等待 rate limit 重置
    needs_wait = False
    for result in results:
        if "0/" in result[3] or "0/" in result[4]:  # REST 或 GraphQL 为 0
            needs_wait = True
            break
    
    if needs_wait:
        print("\n⚠️  注意: 部分 tokens 的 rate limit 已耗尽")
        print("   → 建议等待 rate limit 重置后再开始爬取")
        print("   → Rate limit 每小时重置一次")

if __name__ == '__main__':
    print("="*80)
    print("  GitHub Tokens 验证工具")
    print("="*80)
    verify_tokens()
    print()




