#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量爬取 OpenDigger 仓库数据脚本

功能：
1. 从 OpenDigger 获取热门仓库列表
2. 批量爬取时序数据（指标 + Issue/Commit 文本）
3. 默认跳过描述性文档（README、LICENSE等），专注时序数据
4. 支持断点续传（中断后从上次位置继续）
5. 用于制作数据集

使用方法：
    python batch_crawl_opendigger.py --count 100 --max-per-month 50
    python batch_crawl_opendigger.py --resume        # 从上次中断处继续
    python batch_crawl_opendigger.py --with-docs     # 同时爬取描述性文档
"""

import os
import sys
import json
import time
import argparse
import requests
from datetime import datetime
from typing import List, Dict, Optional

# 添加项目根目录到 Python 路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, os.path.dirname(SCRIPT_DIR))

# 进度文件路径
PROGRESS_FILE = os.path.join(SCRIPT_DIR, 'data', 'batch_crawl_progress.json')

# OpenDigger 热门仓库列表（按 OpenRank 排序的知名开源项目）
# 这些是 OpenDigger 上有数据的仓库
OPENDIGGER_REPOS = [
    # 前端框架
    "facebook/react",
    "vuejs/vue",
    "angular/angular",
    "sveltejs/svelte",
    "vercel/next.js",
    "nuxt/nuxt",
    "remix-run/remix",
    
    # 后端框架
    "nodejs/node",
    "django/django",
    "spring-projects/spring-boot",
    "laravel/laravel",
    "rails/rails",
    "expressjs/express",
    "fastapi/fastapi",
    "pallets/flask",
    
    # 数据库
    "redis/redis",
    "mongodb/mongo",
    "postgres/postgres",
    "mysql/mysql-server",
    "elastic/elasticsearch",
    "ClickHouse/ClickHouse",
    "apache/spark",
    "apache/kafka",
    
    # 容器与云原生
    "kubernetes/kubernetes",
    "docker/docker-ce",
    "moby/moby",
    "containerd/containerd",
    "helm/helm",
    "prometheus/prometheus",
    "grafana/grafana",
    "istio/istio",
    
    # AI/ML
    "tensorflow/tensorflow",
    "pytorch/pytorch",
    "huggingface/transformers",
    "langchain-ai/langchain",
    "AUTOMATIC1111/stable-diffusion-webui",
    "openai/openai-python",
    "microsoft/DeepSpeed",
    "Lightning-AI/pytorch-lightning",
    
    # 编程语言
    "rust-lang/rust",
    "golang/go",
    "python/cpython",
    "microsoft/TypeScript",
    "JetBrains/kotlin",
    "apple/swift",
    "ziglang/zig",
    
    # 开发工具
    "microsoft/vscode",
    "vim/vim",
    "neovim/neovim",
    "git/git",
    "cli/cli",
    "junegunn/fzf",
    "BurntSushi/ripgrep",
    
    # 运维工具
    "ansible/ansible",
    "hashicorp/terraform",
    "pulumi/pulumi",
    "argoproj/argo-cd",
    "jenkins-x/jx",
    
    # 测试工具
    "facebook/jest",
    "cypress-io/cypress",
    "playwright-community/playwright",
    "pytest-dev/pytest",
    
    # 网络与安全
    "nginx/nginx",
    "traefik/traefik",
    "caddyserver/caddy",
    "envoyproxy/envoy",
    
    # 大数据
    "apache/hadoop",
    "apache/flink",
    "apache/airflow",
    "apache/superset",
    "dbt-labs/dbt-core",
    
    # 消息队列
    "apache/rocketmq",
    "rabbitmq/rabbitmq-server",
    "nats-io/nats-server",
    
    # Web 服务器
    "apache/httpd",
    "openresty/openresty",
    
    # 移动开发
    "flutter/flutter",
    "react-native-community/react-native",
    "nicklockwood/SwiftFormat",
    
    # 区块链
    "ethereum/go-ethereum",
    "bitcoin/bitcoin",
    "solana-labs/solana",
    
    # 游戏引擎
    "godotengine/godot",
    "bevyengine/bevy",
    
    # 其他知名项目
    "torvalds/linux",
    "apache/dubbo",
    "alibaba/nacos",
    "alibaba/arthas",
    "apache/skywalking",
    "PaddlePaddle/Paddle",
    "milvus-io/milvus",
    "apache/doris",
    "StarRocks/starrocks",
    "pingcap/tidb",
    "cockroachdb/cockroach",
    "vitessio/vitess",
    "etcd-io/etcd",
    "hashicorp/consul",
    "hashicorp/vault",
    "traefik/traefik",
    "cloudflare/cloudflared",
    "cloudflare/workers-sdk",
    "vercel/turbo",
    "evanw/esbuild",
    "rollup/rollup",
    "webpack/webpack",
    "parcel-bundler/parcel",
    "vitejs/vite",
    "tailwindlabs/tailwindcss",
    "chakra-ui/chakra-ui",
    "mui/material-ui",
    "ant-design/ant-design",
    "shadcn-ui/ui",
]


def load_progress() -> Dict:
    """加载进度文件"""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {
        'completed': [],
        'failed': [],
        'last_index': 0,
        'started_at': None,
        'updated_at': None
    }


def save_progress(progress: Dict):
    """保存进度文件"""
    os.makedirs(os.path.dirname(PROGRESS_FILE), exist_ok=True)
    progress['updated_at'] = datetime.now().isoformat()
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def get_repos_to_crawl(count: int, progress: Dict) -> List[str]:
    """获取需要爬取的仓库列表"""
    # 过滤掉已完成的
    completed = set(progress.get('completed', []))
    repos = [r for r in OPENDIGGER_REPOS if r not in completed]
    
    # 限制数量
    return repos[:count]


def crawl_single_repo(owner: str, repo: str, max_per_month: int = 50, enable_llm: bool = True, skip_docs: bool = True) -> bool:
    """
    爬取单个仓库的数据
    
    Args:
        owner: 仓库所有者
        repo: 仓库名称
        max_per_month: 每月最大爬取数量
        enable_llm: 是否启用 LLM 摘要
        skip_docs: 是否跳过描述性文档（README、LICENSE等）
    
    Returns:
        是否成功
    """
    try:
        # 导入爬取模块
        from crawl_monthly_data import crawl_project_monthly
        
        print(f"\n{'='*60}")
        print(f"开始爬取: {owner}/{repo}")
        print(f"{'='*60}")
        
        # 调用爬取函数
        result = crawl_project_monthly(
            owner=owner,
            repo=repo,
            max_per_month=max_per_month,
            enable_llm_summary=enable_llm,
            skip_docs=skip_docs
        )
        
        if result:
            print(f"✓ {owner}/{repo} 爬取成功")
            return True
        else:
            print(f"✗ {owner}/{repo} 爬取失败")
            return False
            
    except Exception as e:
        print(f"✗ {owner}/{repo} 爬取异常: {str(e)}")
        return False


def batch_crawl(
    count: int = 100,
    max_per_month: int = 50,
    enable_llm: bool = True,
    skip_docs: bool = True,
    resume: bool = False,
    delay: float = 2.0
):
    """
    批量爬取仓库数据
    
    Args:
        count: 要爬取的仓库数量
        max_per_month: 每月最大爬取数量
        enable_llm: 是否启用 LLM 摘要
        skip_docs: 是否跳过描述性文档（默认跳过，只爬时序数据）
        resume: 是否从上次中断处继续
        delay: 每个仓库之间的延迟（秒）
    """
    # 加载进度
    progress = load_progress()
    
    if not resume:
        # 重新开始
        progress = {
            'completed': [],
            'failed': [],
            'last_index': 0,
            'started_at': datetime.now().isoformat(),
            'updated_at': None
        }
    
    # 获取需要爬取的仓库
    repos = get_repos_to_crawl(count, progress)
    
    if not repos:
        print("没有需要爬取的仓库")
        return
    
    print(f"\n{'='*60}")
    print(f"批量爬取 OpenDigger 仓库数据")
    print(f"{'='*60}")
    print(f"目标数量: {count}")
    print(f"待爬取: {len(repos)}")
    print(f"已完成: {len(progress.get('completed', []))}")
    print(f"已失败: {len(progress.get('failed', []))}")
    print(f"每月最大数量: {max_per_month}")
    print(f"启用 LLM: {enable_llm}")
    print(f"跳过文档: {skip_docs}")
    print(f"{'='*60}\n")
    
    # 开始爬取
    for idx, repo_full in enumerate(repos):
        owner, repo = repo_full.split('/')
        
        print(f"\n[{idx + 1}/{len(repos)}] 正在爬取 {repo_full}...")
        
        success = crawl_single_repo(
            owner=owner,
            repo=repo,
            max_per_month=max_per_month,
            enable_llm=enable_llm,
            skip_docs=skip_docs
        )
        
        if success:
            progress['completed'].append(repo_full)
        else:
            progress['failed'].append(repo_full)
        
        progress['last_index'] = idx + 1
        
        # 保存进度
        save_progress(progress)
        
        # 延迟，避免 API 限制
        if idx < len(repos) - 1:
            print(f"等待 {delay} 秒后继续...")
            time.sleep(delay)
    
    # 打印最终统计
    print(f"\n{'='*60}")
    print("批量爬取完成！")
    print(f"{'='*60}")
    print(f"成功: {len(progress['completed'])}")
    print(f"失败: {len(progress['failed'])}")
    
    if progress['failed']:
        print(f"\n失败的仓库:")
        for repo in progress['failed']:
            print(f"  - {repo}")


def list_progress():
    """显示当前进度"""
    progress = load_progress()
    
    print(f"\n{'='*60}")
    print("批量爬取进度")
    print(f"{'='*60}")
    print(f"已完成: {len(progress.get('completed', []))}")
    print(f"已失败: {len(progress.get('failed', []))}")
    print(f"开始时间: {progress.get('started_at', '未开始')}")
    print(f"更新时间: {progress.get('updated_at', '未更新')}")
    
    if progress.get('completed'):
        print(f"\n已完成的仓库 ({len(progress['completed'])}):")
        for repo in progress['completed'][:10]:
            print(f"  ✓ {repo}")
        if len(progress['completed']) > 10:
            print(f"  ... 还有 {len(progress['completed']) - 10} 个")
    
    if progress.get('failed'):
        print(f"\n失败的仓库 ({len(progress['failed'])}):")
        for repo in progress['failed']:
            print(f"  ✗ {repo}")


def reset_progress():
    """重置进度"""
    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)
        print("进度已重置")
    else:
        print("没有进度文件需要重置")


def main():
    parser = argparse.ArgumentParser(
        description='批量爬取 OpenDigger 仓库数据',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python batch_crawl_opendigger.py --count 100           # 爬取 100 个仓库（只爬时序数据）
  python batch_crawl_opendigger.py --resume              # 从上次中断处继续
  python batch_crawl_opendigger.py --status              # 查看当前进度
  python batch_crawl_opendigger.py --reset               # 重置进度
  python batch_crawl_opendigger.py --count 50 --no-llm   # 不生成 AI 摘要
  python batch_crawl_opendigger.py --with-docs           # 同时爬取描述性文档
        """
    )
    
    parser.add_argument(
        '--count', '-c',
        type=int,
        default=100,
        help='要爬取的仓库数量（默认: 100）'
    )
    
    parser.add_argument(
        '--max-per-month', '-m',
        type=int,
        default=50,
        help='每月最大爬取 Issue/Commit 数量（默认: 50）'
    )
    
    parser.add_argument(
        '--resume', '-r',
        action='store_true',
        help='从上次中断处继续爬取'
    )
    
    parser.add_argument(
        '--no-llm',
        action='store_true',
        help='禁用 LLM 摘要生成'
    )
    
    parser.add_argument(
        '--with-docs',
        action='store_true',
        help='同时爬取描述性文档（README、LICENSE等），默认不爬取'
    )
    
    parser.add_argument(
        '--delay', '-d',
        type=float,
        default=2.0,
        help='每个仓库之间的延迟秒数（默认: 2.0）'
    )
    
    parser.add_argument(
        '--status', '-s',
        action='store_true',
        help='显示当前爬取进度'
    )
    
    parser.add_argument(
        '--reset',
        action='store_true',
        help='重置爬取进度'
    )
    
    args = parser.parse_args()
    
    if args.status:
        list_progress()
        return
    
    if args.reset:
        reset_progress()
        return
    
    # 开始批量爬取
    batch_crawl(
        count=args.count,
        max_per_month=args.max_per_month,
        enable_llm=not args.no_llm,
        skip_docs=not args.with_docs,  # 默认跳过文档，--with-docs 才爬取
        resume=args.resume,
        delay=args.delay
    )


if __name__ == '__main__':
    main()

