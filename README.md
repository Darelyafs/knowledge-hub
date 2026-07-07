# 知识共享库 📚

基于 Flask + SQLite 的云端信息共享平台。

**⚡ 核心特点：打开网页就能编辑，无需注册、无需 GitHub 账号。**

---

## 功能

- 🔗 **网址收藏** — 添加链接、写简介、记录个人感受、打标签、标注阅读状态
- 📖 **PDF 读后感** — 上传 PDF、写读后感、评分、行动清单
- 🏷️ **标签系统** — 自动补全、标签云浏览、按标签筛选
- 🔍 **全文搜索** — 搜索所有标题、简介和笔记内容
- 📱 **响应式设计** — 手机和电脑都能用

---

## 本地运行

```bash
# 1. 安装依赖
pip install flask

# 2. 启动应用
python app.py

# 3. 打开浏览器
# http://127.0.0.1:5000
```

---

## 部署上线

### 方案一：Render（推荐，免费）

1. 将代码推送到 GitHub 仓库
2. 在 [Render.com](https://render.com) 注册，连接 GitHub
3. 创建 **Web Service**，选择仓库
4. 配置：
   - **Runtime**: Python 3
   - **Build Command**: `pip install flask`
   - **Start Command**: `gunicorn app:app -b 0.0.0.0:$PORT`
5. 部署完成，获得公开网址！

> ⚠️ Render 免费层的 SQLite 数据库会在每次部署时重置。如需持久化，升级到付费计划或改用 Railway。

### 方案二：Railway（免费额度）

1. 推送到 GitHub
2. 在 [Railway.app](https://railway.app) 连接仓库
3. 自动检测 Python，一键部署
4. 数据持久化（免费额度内）

### 方案三：自建服务器

```bash
# 使用 gunicorn（Linux/Mac）
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app

# 或使用 waitress（Windows）
pip install waitress
waitress-serve --port=5000 app:app
```

---

## 使用方式

1. 打开网址 → 浏览内容
2. 点击「+ 添加链接」→ 填写表单 → 保存
3. 鼠标悬停任意卡片 → 显示 ✏️ 编辑和 🗑️ 删除按钮
4. 顶部搜索框输入关键词 → 实时搜索

---

## 项目结构

```
knowledge-hub-app/
├── app.py                # Flask 应用（全部路由 + 数据库）
├── requirements.txt      # flask
├── templates/            # HTML 模板（8 个）
│   ├── base.html         #   基础布局
│   ├── index.html        #   首页
│   ├── links.html        #   链接列表
│   ├── link_form.html    #   链接表单
│   ├── reads.html        #   读后感列表
│   ├── read_form.html    #   读后感表单
│   ├── tags.html         #   标签云
│   └── search.html       #   搜索结果
├── static/
│   └── style.css         # 全局样式
└── data/
    ├── knowledge.db      # SQLite 数据库（自动创建）
    └── uploads/          # 上传的 PDF 文件
```
