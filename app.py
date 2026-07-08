r"""
知识共享库 — Flask Web 应用（Supabase 云端版）
数据库：Supabase PostgreSQL（2GB 免费）
PDF存储：Supabase Storage（1GB 免费）
打开浏览器就能直接浏览、添加、编辑、删除，无需注册。
"""
import os
import io
from datetime import datetime

from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash
from supabase import create_client

# ── Supabase 配置 ──────────────────────────────────────
SUPABASE_URL = "https://sujhbmkrmonjrcbcpxqb.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InN1amhibWtybW9uanJjYmNweHFiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODM0MTg2MTUsImV4cCI6MjA5ODk5NDYxNX0.ieQVLlbZCh8O1SBLrwHnZ-cwA0LgjHuL9eFHcZ63YWA"
SUPABASE_BUCKET = "pdfs"

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

PDF_MAX_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {"pdf"}

# Flask
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24).hex())

CATEGORIES = ["科研学习", "工具便利", "其他"]

# ── 辅助函数 ──────────────────────────────────────────
def format_date(dt_str):
    if not dt_str:
        return ""
    try:
        if isinstance(dt_str, datetime):
            return dt_str.strftime("%Y-%m-%d")
        s = str(dt_str)
        # Handle ISO format from Supabase
        if "T" in s:
            return s[:10]
        return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return str(dt_str)[:10] if dt_str else ""


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def pdf_public_url(key):
    """生成 PDF 公开访问 URL"""
    if not key:
        return ""
    return f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{key}"


# Jinja 过滤器
app.jinja_env.filters["format_date"] = format_date
app.jinja_env.filters["pdf_url"] = pdf_public_url


# ── 文件上传 ──────────────────────────────────────────
def upload_pdf(file, old_key=""):
    if not file or not file.filename or not allowed_file(file.filename):
        return old_key
    filename = secure_filename(file.filename)
    name, ext = os.path.splitext(filename)
    key = f"{name}_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
    file_bytes = file.read()
    sb.storage.from_(SUPABASE_BUCKET).upload(
        key, file_bytes, {"content-type": "application/pdf"}
    )
    if old_key:
        try:
            sb.storage.from_(SUPABASE_BUCKET).remove([old_key])
        except Exception:
            pass
    return key


def delete_pdf(key):
    if not key:
        return
    try:
        sb.storage.from_(SUPABASE_BUCKET).remove([key])
    except Exception:
        pass


# ── 首页 ──────────────────────────────────────────────
@app.route("/")
def index():
    links = sb.table("links").select("*", count="exact").order("updated_at", desc=True).limit(3).execute()
    reads = sb.table("reads").select("*", count="exact").order("updated_at", desc=True).limit(3).execute()
    link_count = links.count if links.count else 0
    read_count = reads.count if reads.count else 0
    return render_template("index.html",
                           link_count=link_count, read_count=read_count,
                           recent_links=links.data or [], recent_reads=reads.data or [],
                           categories=CATEGORIES)


# ── 网址收藏 ──────────────────────────────────────────
@app.route("/links")
def link_list():
    cat = request.args.get("category", "")
    q = sb.table("links").select("*").order("updated_at", desc=True)
    if cat:
        q = q.eq("category", cat)
    result = q.execute()
    return render_template("links.html", links=result.data or [],
                           current_category=cat, categories=CATEGORIES)


@app.route("/links/add")
def link_add():
    return render_template("link_form.html", link=None, categories=CATEGORIES)


@app.route("/links/<int:link_id>/edit")
def link_edit(link_id):
    result = sb.table("links").select("*").eq("id", link_id).execute()
    if not result.data:
        flash("网址不存在", "error")
        return redirect(url_for("link_list"))
    return render_template("link_form.html", link=result.data[0], categories=CATEGORIES)


@app.route("/links/save", methods=["POST"])
def link_save():
    link_id = request.form.get("id", "")
    title = request.form["title"].strip()
    u = request.form["url"].strip()
    author = request.form.get("author", "").strip()
    summary = request.form.get("summary", "").strip()
    category = request.form.get("category", "其他").strip()

    data = {
        "title": title,
        "url": u,
        "thoughts": author,
        "summary": summary,
        "category": category,
        "updated_at": datetime.now().isoformat(),
    }

    if link_id:
        sb.table("links").update(data).eq("id", int(link_id)).execute()
        flash("网址已更新 ✓", "success")
    else:
        sb.table("links").insert(data).execute()
        flash("网址已添加 ✓", "success")
    return redirect(url_for("link_list"))


@app.route("/links/<int:link_id>/delete", methods=["POST"])
def link_delete(link_id):
    sb.table("links").delete().eq("id", link_id).execute()
    flash("网址已删除", "info")
    return redirect(url_for("link_list"))


# ── PDF ──────────────────────────────────────────────
@app.route("/reads")
def read_list():
    cat = request.args.get("category", "")
    q = sb.table("reads").select("*").order("updated_at", desc=True)
    if cat:
        q = q.eq("category", cat)
    result = q.execute()
    return render_template("reads.html", reads=result.data or [],
                           current_category=cat, categories=CATEGORIES)


@app.route("/reads/add")
def read_add():
    return render_template("read_form.html", read=None, categories=CATEGORIES)


@app.route("/reads/<int:read_id>/edit")
def read_edit(read_id):
    result = sb.table("reads").select("*").eq("id", read_id).execute()
    if not result.data:
        flash("PDF 不存在", "error")
        return redirect(url_for("read_list"))
    return render_template("read_form.html", read=result.data[0], categories=CATEGORIES)


@app.route("/reads/save", methods=["POST"])
def read_save():
    read_id = request.form.get("id", "")
    title = request.form["title"].strip()
    author = request.form.get("author", "").strip()
    summary = request.form.get("summary", "").strip()
    category = request.form.get("category", "其他").strip()

    old_key = request.form.get("existing_pdf_key", "")
    pdf_key = old_key
    if "pdf_file" in request.files:
        file = request.files["pdf_file"]
        if file and file.filename:
            pdf_key = upload_pdf(file, old_key)

    data = {
        "title": title,
        "author": author,
        "summary": summary,
        "category": category,
        "pdf_key": pdf_key,
        "updated_at": datetime.now().isoformat(),
    }

    if read_id:
        sb.table("reads").update(data).eq("id", int(read_id)).execute()
        flash("PDF 已更新 ✓", "success")
    else:
        sb.table("reads").insert(data).execute()
        flash("PDF 已添加 ✓", "success")
    return redirect(url_for("read_list"))


@app.route("/reads/<int:read_id>/delete", methods=["POST"])
def read_delete(read_id):
    result = sb.table("reads").select("pdf_key").eq("id", read_id).execute()
    if result.data and result.data[0].get("pdf_key"):
        delete_pdf(result.data[0]["pdf_key"])
    sb.table("reads").delete().eq("id", read_id).execute()
    flash("PDF 已删除", "info")
    return redirect(url_for("read_list"))


# ── 搜索 ──────────────────────────────────────────────
@app.route("/search")
def search():
    qs = request.args.get("q", "").strip()
    if not qs:
        return redirect(url_for("index"))
    like = f"%{qs}%"
    links = sb.table("links").select("*").or_(f"title.ilike.{like},summary.ilike.{like}") \
        .order("updated_at", desc=True).limit(20).execute()
    reads = sb.table("reads").select("*").or_(f"title.ilike.{like},author.ilike.{like},summary.ilike.{like}") \
        .order("updated_at", desc=True).limit(20).execute()
    return render_template("search.html", q=qs, links=links.data or [], reads=reads.data or [])


# ── 启动 ──────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  知识共享库 — Supabase 云端版")
    print(f"  数据库: Supabase PostgreSQL (2GB 免费)")
    print(f"  PDF  : Supabase Storage (1GB 免费)")
    print(f"  访问 : http://127.0.0.1:5000")
    print("=" * 55)
    app.run(debug=True, host="0.0.0.0", port=5000)
