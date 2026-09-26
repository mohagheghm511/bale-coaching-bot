"""
migrate_static_content.py
اجرا کن: python migrate_static_content.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "coaching_bot.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.executescript("""
CREATE TABLE IF NOT EXISTS static_contents (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    content_type  TEXT NOT NULL,
    media_type    TEXT NOT NULL DEFAULT 'text',
    text          TEXT,
    question      TEXT,
    link_url      TEXT,
    link_label    TEXT,
    file_id       TEXT,
    is_active     INTEGER NOT NULL DEFAULT 1,
    "order"       INTEGER NOT NULL DEFAULT 0,
    created_at    DATETIME DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
);
""")

conn.commit()
conn.close()
print("✅ جدول static_contents ساخته شد.")
