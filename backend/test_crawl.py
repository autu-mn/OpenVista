#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试爬取修复后的效果"""
from DataProcessor.github_text_crawler import GitHubTextCrawler
from DataProcessor.data_processor import DataProcessor

if __name__ == '__main__':
    print("="*60)
    print("测试爬取：amazeui/amazeui")
    print("="*60)
    
    crawler = GitHubTextCrawler()
    data = crawler.crawl_all('amazeui', 'amazeui')
    
    print("\n" + "="*60)
    print("测试数据处理")
    print("="*60)
    
    processor = DataProcessor(data, 'amazeui', 'amazeui')
    processor.process_data()
    
    print("\n" + "="*60)
    print("测试完成！")
    print("="*60)

