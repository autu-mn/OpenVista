"""
简化版批量爬取脚本
生成爬取命令列表，用户手动执行
"""
import os
import sys

# 设置输出编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import config


def generate_crawl_commands(projects):
    """生成爬取命令"""
    
    print(f"\n{'='*80}")
    print("批量爬取命令生成器")
    print(f"{'='*80}\n")
    
    tsa_try_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tsa-try')
    
    # 检查哪些项目已存在
    existing = []
    missing = []
    
    for proj in projects:
        owner, repo = proj.split('/')
        data_dir = os.path.join(tsa_try_dir, 'data', f"{owner}_{repo}")
        model_input = os.path.join(data_dir, 'model_input.json')
        
        if os.path.exists(model_input):
            existing.append(proj)
        else:
            missing.append(proj)
    
    print(f"已有数据的项目 ({len(existing)} 个):")
    for proj in existing:
        print(f"  ✓ {proj}")
    
    print(f"\n需要爬取的项目 ({len(missing)} 个):")
    for proj in missing:
        print(f"  - {proj}")
    
    if not missing:
        print(f"\n所有项目数据已存在！")
        return
    
    # 生成批处理脚本
    print(f"\n{'='*80}")
    print("方案 1: 手动逐个爬取")
    print(f"{'='*80}\n")
    
    print("依次运行以下命令:\n")
    
    for i, proj in enumerate(missing, 1):
        owner, repo = proj.split('/')
        print(f"# {i}. {proj}")
        print(f"# 修改 tsa-try/crawl_complete_data.py:")
        print(f"#   repo_owner = '{owner}'")
        print(f"#   repo_name = '{repo}'")
        print(f"cd tsa-try")
        print(f"python crawl_complete_data.py")
        print(f"cd ..\n")
    
    # 生成 Windows 批处理文件
    print(f"\n{'='*80}")
    print("方案 2: 使用批处理文件（自动化）")
    print(f"{'='*80}\n")
    
    batch_file = os.path.join(os.path.dirname(__file__), 'crawl_all.bat')
    
    with open(batch_file, 'w', encoding='utf-8') as f:
        f.write("@echo off\n")
        f.write("REM 批量爬取脚本\n\n")
        
        for proj in missing:
            owner, repo = proj.split('/')
            f.write(f"echo ========================================\n")
            f.write(f"echo 爬取: {proj}\n")
            f.write(f"echo ========================================\n")
            f.write(f"cd tsa-try\n")
            
            # 使用 Python 修改文件
            f.write(f'python -c "')
            f.write(f"import re; ")
            f.write(f"content = open('crawl_complete_data.py', 'r', encoding='utf-8').read(); ")
            f.write(f"content = re.sub(r'repo_owner = .*', 'repo_owner = \\\"{owner}\\\"', content); ")
            f.write(f"content = re.sub(r'repo_name = .*', 'repo_name = \\\"{repo}\\\"', content); ")
            f.write(f"open('crawl_complete_data.py', 'w', encoding='utf-8').write(content)")
            f.write(f'"\n')
            
            f.write(f"python crawl_complete_data.py\n")
            f.write(f"cd ..\n")
            f.write(f"timeout /t 5 /nobreak\n\n")
    
    print(f"✓ 批处理文件已生成: {batch_file}")
    print(f"\n运行命令:")
    print(f"  {batch_file}")
    
    # 生成数据准备脚本
    print(f"\n{'='*80}")
    print("方案 3: 直接使用现有数据准备训练集")
    print(f"{'='*80}\n")
    
    if existing:
        print(f"你已经有 {len(existing)} 个项目的数据，可以直接开始训练：\n")
        print(f"cd Bi-Tower")
        print(f"python prepare_data.py")
        print(f"python train.py --config balanced --device cpu --epochs 20")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='生成批量爬取命令')
    parser.add_argument('--num_projects', type=int, default=10,
                        help='项目数量')
    parser.add_argument('--all', action='store_true',
                        help='所有项目')
    
    args = parser.parse_args()
    
    if args.all:
        projects = config.TARGET_PROJECTS
    else:
        projects = config.TARGET_PROJECTS[:args.num_projects]
    
    generate_crawl_commands(projects)

