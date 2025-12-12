@echo off
REM 批量爬取脚本

echo ========================================
echo 爬取: NixOS/nixpkgs
echo ========================================
cd tsa-try
python -c "import re; content = open('crawl_complete_data.py', 'r', encoding='utf-8').read(); content = re.sub(r'repo_owner = .*', 'repo_owner = \"NixOS\"', content); content = re.sub(r'repo_name = .*', 'repo_name = \"nixpkgs\"', content); open('crawl_complete_data.py', 'w', encoding='utf-8').write(content)"
python crawl_complete_data.py
cd ..
timeout /t 5 /nobreak

echo ========================================
echo 爬取: llvm/llvm-project
echo ========================================
cd tsa-try
python -c "import re; content = open('crawl_complete_data.py', 'r', encoding='utf-8').read(); content = re.sub(r'repo_owner = .*', 'repo_owner = \"llvm\"', content); content = re.sub(r'repo_name = .*', 'repo_name = \"llvm-project\"', content); open('crawl_complete_data.py', 'w', encoding='utf-8').write(content)"
python crawl_complete_data.py
cd ..
timeout /t 5 /nobreak

echo ========================================
echo 爬取: pytorch/pytorch
echo ========================================
cd tsa-try
python -c "import re; content = open('crawl_complete_data.py', 'r', encoding='utf-8').read(); content = re.sub(r'repo_owner = .*', 'repo_owner = \"pytorch\"', content); content = re.sub(r'repo_name = .*', 'repo_name = \"pytorch\"', content); open('crawl_complete_data.py', 'w', encoding='utf-8').write(content)"
python crawl_complete_data.py
cd ..
timeout /t 5 /nobreak

echo ========================================
echo 爬取: flutter/flutter
echo ========================================
cd tsa-try
python -c "import re; content = open('crawl_complete_data.py', 'r', encoding='utf-8').read(); content = re.sub(r'repo_owner = .*', 'repo_owner = \"flutter\"', content); content = re.sub(r'repo_name = .*', 'repo_name = \"flutter\"', content); open('crawl_complete_data.py', 'w', encoding='utf-8').write(content)"
python crawl_complete_data.py
cd ..
timeout /t 5 /nobreak

echo ========================================
echo 爬取: zed-industries/zed
echo ========================================
cd tsa-try
python -c "import re; content = open('crawl_complete_data.py', 'r', encoding='utf-8').read(); content = re.sub(r'repo_owner = .*', 'repo_owner = \"zed-industries\"', content); content = re.sub(r'repo_name = .*', 'repo_name = \"zed\"', content); open('crawl_complete_data.py', 'w', encoding='utf-8').write(content)"
python crawl_complete_data.py
cd ..
timeout /t 5 /nobreak

echo ========================================
echo 爬取: microsoft/winget-pkgs
echo ========================================
cd tsa-try
python -c "import re; content = open('crawl_complete_data.py', 'r', encoding='utf-8').read(); content = re.sub(r'repo_owner = .*', 'repo_owner = \"microsoft\"', content); content = re.sub(r'repo_name = .*', 'repo_name = \"winget-pkgs\"', content); open('crawl_complete_data.py', 'w', encoding='utf-8').write(content)"
python crawl_complete_data.py
cd ..
timeout /t 5 /nobreak

echo ========================================
echo 爬取: godotengine/godot
echo ========================================
cd tsa-try
python -c "import re; content = open('crawl_complete_data.py', 'r', encoding='utf-8').read(); content = re.sub(r'repo_owner = .*', 'repo_owner = \"godotengine\"', content); content = re.sub(r'repo_name = .*', 'repo_name = \"godot\"', content); open('crawl_complete_data.py', 'w', encoding='utf-8').write(content)"
python crawl_complete_data.py
cd ..
timeout /t 5 /nobreak

echo ========================================
echo 爬取: elastic/kibana
echo ========================================
cd tsa-try
python -c "import re; content = open('crawl_complete_data.py', 'r', encoding='utf-8').read(); content = re.sub(r'repo_owner = .*', 'repo_owner = \"elastic\"', content); content = re.sub(r'repo_name = .*', 'repo_name = \"kibana\"', content); open('crawl_complete_data.py', 'w', encoding='utf-8').write(content)"
python crawl_complete_data.py
cd ..
timeout /t 5 /nobreak

