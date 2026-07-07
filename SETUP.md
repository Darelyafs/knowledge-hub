# 部署指南 — Supabase + Cloudflare R2 + Render

全部免费，数据永久保存，代码随便更新。

---

## 总览

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────────┐
│   Render     │────▶│    Supabase     │     │  Cloudflare R2   │
│  (Flask 应用) │     │  (PostgreSQL)   │     │   (PDF 文件)     │
│              │◀────│   500 MB 免费    │     │   10 GB 免费      │
└──────────────┘     └─────────────────┘     └──────────────────┘
  托管网页              存文字数据              存 PDF 文件
  自动部署              永不丢失                永不丢失
```

---

## 第一步：注册 Supabase（3 分钟）

1. 打开 [supabase.com](https://supabase.com) → **Start your project** → 用 GitHub 登录
2. 创建组织名（随意起）→ **Create organization**
3. 创建项目：
   - Name: `knowledge-hub`
   - Database Password: 点 **Generate a password** → 复制保存！
   - Region: 选 **ap-southeast-1 (Singapore)** 或 **ap-northeast-1 (Tokyo)**
   - **Create project** → 等 2 分钟
4. 获取连接串：
   - 左侧菜单 → **Settings** → **Database**
   - 找到 **Connection string** → 选 **URI** 标签
   - 复制连接串，把 `[YOUR-PASSWORD]` 替换成你刚才保存的密码
   - 看起来像：`postgresql://postgres.xxx:password@aws-0-xxx.pooler.supabase.com:6543/postgres`

> ✅ 这条连接串就是 `DATABASE_URL`，先记下来。

---

## 第二步：注册 Cloudflare R2（5 分钟）

1. 打开 [cloudflare.com](https://dash.cloudflare.com/sign-up) → 注册（邮箱即可）
2. 左侧菜单 → **R2** → **Create bucket**
   - Bucket name: `knowledge-hub-pdfs`
   - Location: **Asia Pacific**（离你最近的）
   - **Create bucket**
3. 让存储桶可公开访问：
   - 进入刚创建的 bucket → **Settings**
   - **Public access** → 打开 **R2.dev subdomain** → 点 **Allow Access**
   - 记下显示的 Public URL：`https://pub-xxxxxxxxxxxx.r2.dev`
4. 创建 API 令牌：
   - 左侧菜单 → **R2** → 右上角 **Manage R2 API Tokens**
   - **Create API token**
   - Token name: `knowledge-hub`
   - Permissions: 选 **Object Read & Write**
   - **Create token** → 复制保存：
     - Access Key ID
     - Secret Access Key（只显示一次！）
     - Endpoint URL（类似 `https://<id>.r2.cloudflarestorage.com`）

> ✅ 现在你有 4 个 R2 值：Endpoint、Key ID、Secret、Public URL

---

## 第三步：推送到 GitHub

```bash
cd knowledge-hub-app

# 确认 .gitignore 包含了 data/ 目录
git add .
git commit -m "knowledge hub app"
```

在 GitHub 新建仓库（如 `knowledge-hub`），然后：

```bash
git remote add origin https://github.com/<你的用户名>/knowledge-hub.git
git branch -M main
git push -u origin main
```

---

## 第四步：部署到 Render

1. 打开 [render.com](https://render.com) → 用 GitHub 登录
2. **New** → **Web Service** → 选择你的 `knowledge-hub` 仓库
3. 配置：
   - **Name**: `knowledge-hub`（或随意）
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app -b 0.0.0.0:$PORT`
4. 添加环境变量（**Environment** 部分）：

| Key | Value |
|-----|-------|
| `DATABASE_URL` | 第一步的 Supabase 连接串 |
| `R2_ENDPOINT_URL` | 第二步的 Endpoint URL |
| `R2_ACCESS_KEY_ID` | 第二步的 Access Key ID |
| `R2_SECRET_ACCESS_KEY` | 第二步的 Secret Access Key |
| `R2_BUCKET_NAME` | `knowledge-hub-pdfs` |
| `R2_PUBLIC_URL` | 第二步的 Public URL（`https://pub-xxx.r2.dev`） |
| `SECRET_KEY` | 随意敲一串英文数字 |

5. 选择 **Free** plan → **Create Web Service**
6. 等 2-3 分钟 → 拿到网址！

---

## 第五步：验证

1. 打开 Render 给的网址
2. 添加一条链接试试
3. 添加一个读后感 + 上传 PDF
4. 等 5 分钟 → 修改点代码 → `git push` → 等 Render 重新部署 → **刷新页面，之前的数据还在！**

---

## 本地开发

本地不需要配置任何环境变量，自动使用 SQLite + 本地文件：

```bash
pip install -r requirements.txt
python app.py
# http://127.0.0.1:5000
```

---

## 域名绑定（可选）

Render 免费域名是 `xxx.onrender.com`，如果你想用自己的域名：

1. Render 控制台 → Web Service → **Settings** → **Custom Domain**
2. 按提示添加 CNAME 记录
3. 免费 SSL 证书自动配置

---

## 常见问题

**Q: 代码更新后数据丢了？**
A: 检查 Render 上环境变量是否全部正确设置，特别是 `DATABASE_URL`。

**Q: PDF 上传后打不开？**
A: 检查 R2 bucket 是否开启了 Public Access（第二步第 3 条）。

**Q: Render 服务休眠了？**
A: 免费 Web Service 15 分钟无人访问会休眠，下次访问时自动唤醒（约 30 秒）。如果介意可以花 $7/月去掉休眠。
