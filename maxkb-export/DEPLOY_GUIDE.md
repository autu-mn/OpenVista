# OpenVista MaxKB 部署指南

## ⚠️ 重要警告

**Windows 用户注意**：请务必使用脚本导出数据库，**不要**使用 PowerShell 的 `>` 重定向！

```powershell
# ❌ 错误 - 会破坏二进制文件
docker exec ... pg_dump ... > file.dump

# ✅ 正确 - 使用脚本
.\maxkb-export\export.ps1
```

---

## 文件结构

```
maxkb-export/
├── db/
│   └── maxkb_full.dump      # PostgreSQL 备份（包含所有数据）
├── export.ps1               # Windows 导出脚本
├── export.sh                # Linux/Mac 导出脚本
├── install.ps1              # Windows 安装脚本
├── install.sh               # Linux/Mac 安装脚本
└── DEPLOY_GUIDE.md          # 本文档
```

---

## 一、导出数据（在配置好的机器上）

### Windows

```powershell
cd D:\Pycharm\PycharmProject\cvProject\DataPulse
.\maxkb-export\export.ps1
```

### Linux/Mac

```bash
cd /path/to/DataPulse
chmod +x maxkb-export/export.sh
./maxkb-export/export.sh
```

**导出内容包含**：
- ✅ 知识库及所有文档
- ✅ 模型配置（含 API_KEY）
- ✅ Agent 配置
- ✅ 工具配置
- ✅ 用户账户及权限
- ✅ 所有系统设置

---

## 二、安装部署（在新机器上）

### 前提条件

1. 已安装 Docker Desktop 并运行
2. 已获取完整的 `maxkb-export` 文件夹

### Windows

```powershell
.\maxkb-export\install.ps1
```

### Linux/Mac

```bash
chmod +x maxkb-export/install.sh
./maxkb-export/install.sh
```

### 安装完成后

- 访问地址：http://localhost:8080
- 默认用户名：`admin`
- 默认密码：`MaxKB@123456`

> **注意**：如果备份中包含用户数据，请使用备份中的账户登录。

---

## 三、手动操作（高级）

### 手动导出数据库

```bash
# 1. 在容器内执行导出
docker exec openvista-maxkb pg_dump -U root -d maxkb --no-owner --no-acl -Fc -f /tmp/backup.dump

# 2. 复制到本地
docker cp openvista-maxkb:/tmp/backup.dump ./maxkb-export/db/maxkb_full.dump

# 3. 清理容器内临时文件
docker exec openvista-maxkb rm -f /tmp/backup.dump
```

### 手动恢复数据库

```bash
# 1. 复制备份到容器
docker cp ./maxkb-export/db/maxkb_full.dump openvista-maxkb:/tmp/backup.dump

# 2. 恢复数据库
docker exec openvista-maxkb pg_restore -U root -d maxkb --clean --if-exists --no-owner /tmp/backup.dump

# 3. 重启服务
docker restart openvista-maxkb
```

---

## 四、故障排除

### 问题：pg_restore 报错 "not a valid archive"

**原因**：备份文件被 PowerShell 以 UTF-16 编码保存，破坏了二进制格式。

**解决**：使用 `export.ps1` 脚本重新导出。

### 问题：恢复后数据为空

**原因**：pg_restore 命令失败但错误被忽略。

**解决**：手动执行恢复命令查看错误信息：
```bash
docker exec openvista-maxkb pg_restore -U root -d maxkb --clean --if-exists --no-owner /tmp/backup.dump
```

### 问题：需要重新注册

**原因**：用户表未正确恢复。

**解决**：确保备份文件包含完整数据（大小应 > 10MB）。

---

## 五、备份策略建议

1. **定期导出**：每次修改模型/知识库配置后执行导出
2. **保留多版本**：保留最近 3 个备份版本
3. **验证备份**：导出后检查文件大小是否正常

```powershell
# 推荐：带时间戳的备份
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
Copy-Item ".\maxkb-export\db\maxkb_full.dump" ".\maxkb-export\db\maxkb_$timestamp.dump"
```
