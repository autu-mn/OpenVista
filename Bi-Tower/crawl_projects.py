"""
批量爬取OpenDigger已知项目的数据
"""
import os
import sys
import time
import argparse
from tqdm import tqdm

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import config

# 导入tsa-try的爬虫脚本
tsa_try_dir = os.path.join(os.path.dirname(config.BASE_DIR), 'tsa-try')
sys.path.insert(0, tsa_try_dir)


def crawl_single_project(owner, repo):
    """爬取单个项目"""
    print(f"\n{'='*60}")
    print(f"爬取项目: {owner}/{repo}")
    print(f"{'='*60}\n")
    
    try:
        # 使用 subprocess 调用爬虫脚本
        import subprocess
        
        # 修改 crawl_complete_data.py 中的项目名称并运行
        crawl_script = os.path.join(tsa_try_dir, 'crawl_complete_data.py')
        
        # 临时修改环境变量传递项目名称
        env = os.environ.copy()
        env['CRAWL_OWNER'] = owner
        env['CRAWL_REPO'] = repo
        
        # 由于原始脚本不支持参数，我们需要直接修改并运行
        # 更简单的方法：直接复制逻辑
        
        # 检查数据是否已存在
        data_dir = os.path.join(tsa_try_dir, 'data', f"{owner}_{repo}")
        model_input = os.path.join(data_dir, 'model_input.json')
        
        if os.path.exists(model_input):
            print(f"✓ {owner}/{repo} 数据已存在")
            return True
        
        # 执行爬取（需要手动运行 crawl_complete_data.py 并修改其中的项目名）
        print(f"  请手动运行以下命令爬取 {owner}/{repo}:")
        print(f"  1. 打开 tsa-try/crawl_complete_data.py")
        print(f"  2. 修改 repo_owner = '{owner}'")
        print(f"  3. 修改 repo_name = '{repo}'")
        print(f"  4. 运行: python tsa-try/crawl_complete_data.py")
        print(f"\n  或者使用 cd tsa-try && python crawl_complete_data.py")
        
        # 返回 False 表示需要手动处理
        return False
            
    except Exception as e:
        print(f"\n✗ {owner}/{repo} 爬取异常: {e}")
        return False


def main(args):
    """主函数"""
    
    print(f"\n{'='*60}")
    print("批量爬取OpenDigger项目数据")
    print(f"{'='*60}\n")
    
    # 选择要爬取的项目
    if args.all:
        projects = config.TARGET_PROJECTS
    else:
        projects = config.TARGET_PROJECTS[:args.num_projects]
    
    print(f"计划爬取 {len(projects)} 个项目:\n")
    for i, proj in enumerate(projects, 1):
        print(f"  {i}. {proj}")
    
    if not args.force:
        response = input(f"\n确认开始爬取? (y/n): ")
        if response.lower() != 'y':
            print("已取消")
            return
    
    # 开始爬取
    print(f"\n{'='*60}")
    print("开始爬取")
    print(f"{'='*60}\n")
    
    success_count = 0
    failed_projects = []
    
    for proj in tqdm(projects, desc="总体进度"):
        owner, repo = proj.split('/')
        
        # 检查是否已存在
        data_dir = os.path.join(tsa_try_dir, 'data', f"{owner}_{repo}")
        model_input = os.path.join(data_dir, 'model_input.json')
        
        if os.path.exists(model_input) and not args.overwrite:
            print(f"\n  [SKIP] {proj} 已存在，跳过")
            success_count += 1
            continue
        
        # 爬取
        success = crawl_single_project(owner, repo)
        
        if success:
            success_count += 1
        else:
            failed_projects.append(proj)
        
        # 延迟（避免API限流）
        if args.delay > 0:
            time.sleep(args.delay)
    
    # 总结
    print(f"\n{'='*60}")
    print("爬取完成")
    print(f"{'='*60}")
    print(f"  成功: {success_count}/{len(projects)}")
    print(f"  失败: {len(failed_projects)}/{len(projects)}")
    
    if failed_projects:
        print(f"\n失败项目:")
        for proj in failed_projects:
            print(f"  - {proj}")
    
    print(f"\n{'='*60}\n")
    
    # 自动准备数据
    if success_count > 0 and args.auto_prepare:
        print("自动准备训练数据...")
        from prepare_data import prepare_data
        prepare_data(num_projects=None)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='批量爬取OpenDigger项目')
    parser.add_argument('--num_projects', type=int, default=10,
                        help='爬取项目数量（默认10个）')
    parser.add_argument('--all', action='store_true',
                        help='爬取所有项目')
    parser.add_argument('--overwrite', action='store_true',
                        help='覆盖已存在的数据')
    parser.add_argument('--force', action='store_true',
                        help='不询问确认，直接开始')
    parser.add_argument('--delay', type=int, default=5,
                        help='每个项目间的延迟（秒）')
    parser.add_argument('--auto_prepare', action='store_true',
                        help='爬取完成后自动准备训练数据')
    
    args = parser.parse_args()
    
    main(args)

