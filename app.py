"""
知识共享库 — Flask Web 应用
打开浏览器就能直接浏览、添加、编辑、删除内容，无需注册。

部署模式：Supabase (PostgreSQL) + Cloudflare R2 — 数据永久保存，免费
本地模式：SQLite + 本地文件 — 开箱即用，无需配置
"""
import os
import io
import json
import sqlite3
from datetime import datetime

from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify

# ── 环境检测 ──────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = os.environ.get("DATABASE_URL", "")              # Supabase PostgreSQL
R2_ENDPOINT = os.environ.get("R2_ENDPOINT_URL", "")            # Cloudflare R2
R2_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID", "")
R2_KEY_SECRET = os.environ.get("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET = os.environ.get("R2_BUCKET_NAME", "")
R2_PUBLIC = os.environ.get("R2_PUBLIC_URL", "")                # 如 https://pub-xxx.r2.dev

USE_PG = bool(DATABASE_URL)
USE_R2 = all([R2_ENDPOINT, R2_KEY_ID, R2_KEY_SECRET, R2_BUCKET])

PDF_MAX_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {"pdf"}

# 本地模式路径
DB_PATH = os.path.join(BASE_DIR, "data", "knowledge.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 分类
LINK_CATEGORIES = ["前端开发", "后端开发", "工具效率", "设计创意", "AI/ML", "其他"]
READ_CATEGORIES = ["技术书籍", "人文社科", "产品管理", "其他"]

# Flask
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24).hex())

# ── R2 客户端（懒加载）─────────────────────────────────
_r2_client = None


def get_r2():
    global _r2_client
    if _r2_client is None and USE_R2:
        import boto3
        _r2_client = boto3.client(
            "s3",
            endpoint_url=R2_ENDPOINT,
            aws_access_key_id=R2_KEY_ID,
            aws_secret_access_key=R2_KEY_SECRET,
        )
    return _r2_client


# ── 数据库抽象层 ──────────────────────────────────────
def get_db():
    """获取数据库连接（自动选择 PostgreSQL 或 SQLite）"""
    if USE_PG:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
    return conn


def q(conn, sql, params=()):
    """执行 SQL，自动转换占位符（? → %s for PG）"""
    if USE_PG:
        sql = sql.replace("?", "%s")
    return conn.execute(sql, params)


def init_db():
    """初始化数据库表（兼容 PG 和 SQLite）"""
    conn = get_db()
    if USE_PG:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS links (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                summary TEXT DEFAULT '',
                thoughts TEXT DEFAULT '',
                category TEXT DEFAULT '其他',
                tags TEXT DEFAULT '[]',
                status TEXT DEFAULT '未读',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reads (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                book TEXT DEFAULT '',
                author TEXT DEFAULT '',
                summary TEXT DEFAULT '',
                key_points TEXT DEFAULT '',
                thoughts TEXT DEFAULT '',
                action_items TEXT DEFAULT '',
                category TEXT DEFAULT '技术书籍',
                tags TEXT DEFAULT '[]',
                rating INTEGER DEFAULT 0,
                pdf_key TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                summary TEXT DEFAULT '',
                thoughts TEXT DEFAULT '',
                category TEXT DEFAULT '其他',
                tags TEXT DEFAULT '[]',
                status TEXT DEFAULT '未读',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS reads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                book TEXT DEFAULT '',
                author TEXT DEFAULT '',
                summary TEXT DEFAULT '',
                key_points TEXT DEFAULT '',
                thoughts TEXT DEFAULT '',
                action_items TEXT DEFAULT '',
                category TEXT DEFAULT '技术书籍',
                tags TEXT DEFAULT '[]',
                rating INTEGER DEFAULT 0,
                pdf_key TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
    conn.commit()
    conn.close()


# ── 辅助函数 ──────────────────────────────────────────
def parse_tags(tags_json):
    try:
        return json.loads(tags_json)
    except (json.JSONDecodeError, TypeError):
        return []


def all_tags():
    conn = get_db()
    link_tags = q(conn, "SELECT DISTINCT tags FROM links").fetchall()
    read_tags = q(conn, "SELECT DISTINCT tags FROM reads").fetchall()
    conn.close()
    tag_set = set()
    for row in link_tags + read_tags:
        for t in parse_tags(row["tags"]):
            if t.strip():
                tag_set.add(t.strip())
    return sorted(tag_set)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def format_date(dt_str):
    if not dt_str:
        return ""
    try:
        if isinstance(dt_str, datetime):
            return dt_str.strftime("%Y-%m-%d")
        return datetime.strptime(str(dt_str)[:19], "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")
    except ValueError:
        return str(dt_str)[:10]


def pdf_url(pdf_key):
    """根据 key 生成 PDF 访问 URL"""
    if not pdf_key:
        return ""
    if USE_R2 and R2_PUBLIC:
        return f"{R2_PUBLIC.rstrip('/')}/{pdf_key}"
    return url_for("uploaded_file", filename=pdf_key)


# Jinja 过滤器
app.jinja_env.filters["parse_tags"] = parse_tags
app.jinja_env.filters["format_date"] = format_date
app.jinja_env.filters["pdf_url"] = pdf_url


# ── 文件上传（R2 或本地）────────────────────────────────
def upload_pdf(file, old_key=""):
    """上传 PDF，返回存储 key。R2 模式返回 object key，本地模式返回文件名"""
    if not file or not file.filename or not allowed_file(file.filename):
        return old_key

    filename = secure_filename(file.filename)
    name, ext = os.path.splitext(filename)
    key = f"pdfs/{name}_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"

    if USE_R2:
        r2 = get_r2()
        file_bytes = file.read()
        r2.upload_fileobj(io.BytesIO(file_bytes), R2_BUCKET, key, ExtraArgs={"ContentType": "application/pdf"})
        # 删除旧文件
        if old_key:
            try:
                r2.delete_object(Bucket=R2_BUCKET, Key=old_key)
            except Exception:
                pass
    else:
        file.save(os.path.join(UPLOAD_DIR, key))
        if old_key:
            old_path = os.path.join(UPLOAD_DIR, old_key)
            if os.path.exists(old_path):
                try:
                    os.remove(old_path)
                except OSError:
                    pass
    return key


def delete_pdf(key):
    """删除存储中的 PDF"""
    if not key:
        return
    if USE_R2:
        try:
            get_r2().delete_object(Bucket=R2_BUCKET, Key=key)
        except Exception:
            pass
    else:
        path = os.path.join(UPLOAD_DIR, key)
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass


# ── 首页 ──────────────────────────────────────────────
@app.route("/")
def index():
    conn = get_db()
    stats = {
        "links": q(conn, "SELECT COUNT(*) as n FROM links").fetchone()["n"],
        "reads": q(conn, "SELECT COUNT(*) as n FROM reads").fetchone()["n"],
        "tags": len(all_tags()),
    }
    recent_links = q(conn, "SELECT * FROM links ORDER BY updated_at DESC LIMIT 5").fetchall()
    recent_reads = q(conn, "SELECT * FROM reads ORDER BY updated_at DESC LIMIT 5").fetchall()
    conn.close()
    return render_template("index.html", stats=stats, recent_links=recent_links, recent_reads=recent_reads)


# ── 链接 CRUD ─────────────────────────────────────────
@app.route("/links")
def link_list():
    category = request.args.get("category", "")
    tag = request.args.get("tag", "")
    status = request.args.get("status", "")
    conn = get_db()

    query = "SELECT * FROM links WHERE 1=1"
    params = []
    if category:
        query += " AND category = ?"
        params.append(category)
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY updated_at DESC"

    links = q(conn, query, params).fetchall()
    if tag:
        links = [l for l in links if tag in parse_tags(l["tags"])]
    conn.close()

    return render_template("links.html", links=links, categories=LINK_CATEGORIES,
                           current_category=category, current_tag=tag, current_status=status, all_tags=all_tags())


@app.route("/links/add")
def link_add():
    return render_template("link_form.html", link=None, categories=LINK_CATEGORIES, all_tags=all_tags())


@app.route("/links/<int:link_id>/edit")
def link_edit(link_id):
    conn = get_db()
    link = q(conn, "SELECT * FROM links WHERE id = ?", (link_id,)).fetchone()
    conn.close()
    if not link:
        flash("链接不存在", "error")
        return redirect(url_for("link_list"))
    return render_template("link_form.html", link=link, categories=LINK_CATEGORIES, all_tags=all_tags())


@app.route("/links/save", methods=["POST"])
def link_save():
    link_id = request.form.get("id", "")
    title = request.form["title"].strip()
    u = request.form["url"].strip()
    summary = request.form.get("summary", "").strip()
    thoughts = request.form.get("thoughts", "").strip()
    category = request.form.get("category", "其他")
    tags = request.form.get("tags", "").strip()
    status = request.form.get("status", "未读")

    tags_list = [t.strip() for t in tags.replace("，", ",").split(",") if t.strip()]
    tags_json = json.dumps(tags_list, ensure_ascii=False)

    conn = get_db()
    if link_id:
        q(conn, """UPDATE links SET title=?, url=?, summary=?, thoughts=?, category=?,
                   tags=?, status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
          (title, u, summary, thoughts, category, tags_json, status, int(link_id)))
        flash("链接已更新 ✓", "success")
    else:
        q(conn, """INSERT INTO links (title, url, summary, thoughts, category, tags, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
          (title, u, summary, thoughts, category, tags_json, status))
        flash("链接已添加 ✓", "success")
    conn.commit()
    conn.close()
    return redirect(url_for("link_list"))


@app.route("/links/<int:link_id>/delete", methods=["POST"])
def link_delete(link_id):
    conn = get_db()
    q(conn, "DELETE FROM links WHERE id = ?", (link_id,))
    conn.commit()
    conn.close()
    flash("链接已删除", "info")
    return redirect(url_for("link_list"))


# ── 读后感 CRUD ───────────────────────────────────────
@app.route("/reads")
def read_list():
    category = request.args.get("category", "")
    tag = request.args.get("tag", "")
    conn = get_db()

    query = "SELECT * FROM reads WHERE 1=1"
    params = []
    if category:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY updated_at DESC"

    reads = q(conn, query, params).fetchall()
    if tag:
        reads = [r for r in reads if tag in parse_tags(r["tags"])]
    conn.close()

    return render_template("reads.html", reads=reads, categories=READ_CATEGORIES,
                           current_category=category, current_tag=tag, all_tags=all_tags())


@app.route("/reads/add")
def read_add():
    return render_template("read_form.html", read=None, categories=READ_CATEGORIES, all_tags=all_tags())


@app.route("/reads/<int:read_id>/edit")
def read_edit(read_id):
    conn = get_db()
    read = q(conn, "SELECT * FROM reads WHERE id = ?", (read_id,)).fetchone()
    conn.close()
    if not read:
        flash("读后感不存在", "error")
        return redirect(url_for("read_list"))
    return render_template("read_form.html", read=read, categories=READ_CATEGORIES, all_tags=all_tags())


@app.route("/reads/save", methods=["POST"])
def read_save():
    read_id = request.form.get("id", "")
    title = request.form["title"].strip()
    book = request.form.get("book", "").strip()
    author = request.form.get("author", "").strip()
    summary = request.form.get("summary", "").strip()
    key_points = request.form.get("key_points", "").strip()
    thoughts = request.form.get("thoughts", "").strip()
    action_items = request.form.get("action_items", "").strip()
    category = request.form.get("category", "技术书籍")
    tags = request.form.get("tags", "").strip()
    rating = int(request.form.get("rating", 0))

    tags_list = [t.strip() for t in tags.replace("，", ",").split(",") if t.strip()]
    tags_json = json.dumps(tags_list, ensure_ascii=False)

    # PDF 上传
    old_key = request.form.get("existing_pdf_key", "")
    pdf_key = old_key
    if "pdf_file" in request.files:
        file = request.files["pdf_file"]
        if file and file.filename:
            pdf_key = upload_pdf(file, old_key)

    conn = get_db()
    if read_id:
        q(conn, """UPDATE reads SET title=?, book=?, author=?, summary=?, key_points=?,
                   thoughts=?, action_items=?, category=?, tags=?, rating=?,
                   pdf_key=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
          (title, book, author, summary, key_points, thoughts, action_items, category, tags_json, rating, pdf_key, int(read_id)))
        flash("读后感已更新 ✓", "success")
    else:
        q(conn, """INSERT INTO reads (title, book, author, summary, key_points, thoughts, action_items, category, tags, rating, pdf_key)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
          (title, book, author, summary, key_points, thoughts, action_items, category, tags_json, rating, pdf_key))
        flash("读后感已添加 ✓", "success")
    conn.commit()
    conn.close()
    return redirect(url_for("read_list"))


@app.route("/reads/<int:read_id>/delete", methods=["POST"])
def read_delete(read_id):
    conn = get_db()
    read = q(conn, "SELECT pdf_key FROM reads WHERE id = ?", (read_id,)).fetchone()
    if read and read["pdf_key"]:
        delete_pdf(read["pdf_key"])
    q(conn, "DELETE FROM reads WHERE id = ?", (read_id,))
    conn.commit()
    conn.close()
    flash("读后感已删除", "info")
    return redirect(url_for("read_list"))


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    """本地模式：提供上传文件的访问"""
    from flask import send_from_directory
    return send_from_directory(UPLOAD_DIR, filename)


# ── 搜索 ──────────────────────────────────────────────
@app.route("/search")
def search():
    qs = request.args.get("q", "").strip()
    if not qs:
        return redirect(url_for("index"))

    conn = get_db()
    like = f"%{qs}%"
    link_results = q(conn, """SELECT * FROM links WHERE title LIKE ? OR summary LIKE ? OR thoughts LIKE ? OR tags LIKE ?
                              ORDER BY updated_at DESC LIMIT 20""",
                     (like, like, like, like)).fetchall()
    read_results = q(conn, """SELECT * FROM reads WHERE title LIKE ? OR book LIKE ? OR author LIKE ? OR summary LIKE ?
                              OR thoughts LIKE ? OR key_points LIKE ? OR tags LIKE ?
                              ORDER BY updated_at DESC LIMIT 20""",
                     (like, like, like, like, like, like, like)).fetchall()
    conn.close()
    return render_template("search.html", q=qs, link_results=link_results, read_results=read_results)


# ── 标签 ──────────────────────────────────────────────
@app.route("/tags")
def tags_page():
    return render_template("tags.html", all_tags=all_tags())


@app.route("/api/tags")
def api_tags():
    return jsonify(all_tags())


# ── 启动 ──────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    print("=" * 55)
    print("  Knowledge Hub started!")
    print(f"  URL:  http://127.0.0.1:5000")
    if USE_PG:
        print("  DB:   PostgreSQL (Supabase)")
    else:
        print(f"  DB:   SQLite -> {DB_PATH}")
    if USE_R2:
        print(f"  File: Cloudflare R2 -> {R2_BUCKET}")
    else:
        print(f"  File: Local -> {UPLOAD_DIR}")
    print("=" * 55)
    app.run(debug=True, host="0.0.0.0", port=5000)
