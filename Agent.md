## Step1：知识库构建
首先在.env里面配置MaxKB基本信息，代码在 **backend/DataProcessor/maxkb_uploader.py**里面。首先需要在.env里面输入几个字段：
![1.png](image\1.png)

### MaxKB服务地址（默认：http://localhost:8080）
    MAXKB_URL=http://localhost:8080

### 登录用户名
    MAXKB_USERNAME=admin

### 登录密码
    MAXKB_PASSWORD=your_password

### 知识库ID
    MAXKB_KNOWLEDGE_ID=your_knowledge_id
![2.png](image\2.png)
具体获取方式就是先创建知识库，然后点击进去，网页里http://localhost:8080/admin/knowledge/019ae417-c380-7790-92e6-2fc017ed1652/default/document，这里**019ae417-c380-7790-92e6-2fc017ed1652**就是知识库的ID。

这些都配置好就可以实现文档上传到知识库了

## Step2：Agent功能设置

为了让Agent功能强大，需要让他**使用知识库、使用联网功能、配置提示词、设置最大token**。

这些在**MaxKB**的**应用**栏目里面可以直接设置。

**工具**里面点击**创建->从工具商店创建**，选择**秘塔AI搜索**，输入**API KEY**是**mk-748CC5B0CD3D17454BDAEB1691A2B491**。然后应用选择这个工具，就能联网了

## Step3：Agent配置到项目中

可以**嵌入第三方**，直接把MaxKB的前端放进我们项目的前端。

![4](image/4.png)


