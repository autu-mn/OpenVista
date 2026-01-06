#!/bin/bash
# 手动重置 MaxKB 管理员密码

echo "正在重置 MaxKB 管理员密码..."

# MaxKB@123456 的 MD5 哈希值
PASSWORD_MD5="0df6c52f03e1c75504c7bb9a09c2a016"

echo "UPDATE \"user\" SET password = '${PASSWORD_MD5}' WHERE username = 'admin';" | docker exec -i openvista-maxkb psql -U root -d maxkb

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ 密码重置成功！"
    echo ""
    echo "请使用以下凭据登录："
    echo "  用户名: admin"
    echo "  密码:   MaxKB@123456"
else
    echo ""
    echo "✗ 密码重置失败，请检查容器是否正常运行"
fi
