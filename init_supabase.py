"""Initialize Supabase database tables"""
import psycopg2

url = "postgresql://postgres:Zp2nFVyQxbmNapeg@db.sujhbmkrmonjrcbcpxqb.supabase.co:5432/postgres"
conn = psycopg2.connect(url)

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

# Enable RLS
conn.execute("ALTER TABLE links ENABLE ROW LEVEL SECURITY")
conn.execute("ALTER TABLE reads ENABLE ROW LEVEL SECURITY")

# Public policies - anyone can do anything
for table in ["links", "reads"]:
    for op, verb in [("SELECT", "read"), ("INSERT", "insert"), ("UPDATE", "update"), ("DELETE", "delete")]:
        try:
            conn.execute(f"CREATE POLICY public_{verb} ON {table} FOR {op} USING (true) WITH CHECK (true)")
        except Exception:
            pass  # policy already exists

conn.commit()
print("Tables + RLS policies created!")

for table in ["links", "reads"]:
    cur = conn.execute(f"SELECT COUNT(*) FROM {table}")
    print(f"  {table}: {cur.fetchone()[0]} rows")

conn.close()
print("Done!")
