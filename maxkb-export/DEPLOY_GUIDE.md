# MaxKB 部署指南

本指南帮助你导出并分享你的 MaxKB AI 助手配置。

---

## 📤 第一步：导出数据库

在你的电脑上运行（确保你的 MaxKB 容器正在运行）：

```bash
# 查看容器名称
docker ps | grep maxkb

# 导出数据库（替换 maxkb 为你的容器名）
docker exec maxkb pg_dump -U root -d maxkb -Fc > maxkb-export/db/maxkb_full.dump

# 确认文件大小（应该有几十MB）
ls -lh maxkb-export/db/maxkb_full.dump
```

**导出的内容包括：**
- ✅ 所有知识库和文档内容
- ✅ 所有向量数据（Embedding）
- ✅ Agent/应用配置和提示词
- ✅ 模型配置（不含 API Key）

---

## 📁 第二步：确认文件结构

确保目录结构如下：

```
maxkb-export/
├── db/
│   └── maxkb_full.dump    ← 你导出的数据库
├── install.sh             ← Linux/Mac 安装脚本
├── install.ps1            ← Windows 安装脚本
├── README.md              ← 使用说明
└── DEPLOY_GUIDE.md        ← 本文件
```

---

## 📦 第三步：上传到 GitHub

```bash
git add maxkb-export/
git commit -m "添加 MaxKB 部署包"
git push
```

> ⚠️ 注意：`maxkb_full.dump` 文件较大（约30-100MB），确保 Git LFS 已配置或仓库支持大文件。

---

## 📖 第四步：告诉使用者

在项目 README 中添加以下说明：

```markdown
## 🤖 AI 助手部署

### 前提条件
- Docker Desktop 已安装并运行
- DeepSeek API Key（获取：https://platform.deepseek.com/）

### 安装步骤

**Linux/Mac:**
```bash
cd maxkb-export
chmod +x install.sh
./install.sh
```

**Windows PowerShell:**
```powershell
cd maxkb-export
.\install.ps1
```

### 配置 API Key
1. 打开 http://localhost:8080
2. 登录：`admin` / `MaxKB@123456`
3. 进入「系统设置」→「模型管理」
4. 编辑「OpenRank-1」模型，填入 DeepSeek API Key
5. 保存后即可使用
```

---

## ❓ 常见问题

**Q: 安装后登录不了？**
A: 密码统一重置为 `MaxKB@123456`

**Q: AI 不回复？**
A: 请确认已在「模型管理」中配置了有效的 DeepSeek API Key

**Q: 端口 8080 被占用？**
A: 修改 `docker-compose.yml` 中的端口映射，如改为 `"8081:8080"`
