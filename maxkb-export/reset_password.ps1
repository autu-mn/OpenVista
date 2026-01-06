# 手动重置 MaxKB 管理员密码

Write-Host "正在重置 MaxKB 管理员密码..." -ForegroundColor Yellow

# MaxKB@123456 的 MD5 哈希值
$passwordMd5 = "0df6c52f03e1c75504c7bb9a09c2a016"
$sql = "UPDATE `"user`" SET password = '$passwordMd5' WHERE username = 'admin';"

echo $sql | docker exec -i openvista-maxkb psql -U root -d maxkb

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✓ 密码重置成功！" -ForegroundColor Green
    Write-Host ""
    Write-Host "请使用以下凭据登录："
    Write-Host "  用户名: admin"
    Write-Host "  密码:   MaxKB@123456"
} else {
    Write-Host ""
    Write-Host "✗ 密码重置失败，请检查容器是否正常运行" -ForegroundColor Red
}
