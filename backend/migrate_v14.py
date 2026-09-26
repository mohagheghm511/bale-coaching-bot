"""
Migration: اضافه کردن capacity و session_type به جداول
اجرا: python migrate_v14.py
"""
import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(__file__), "coaching_bot.db")
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

changes = [
    ("coaching_packages", "session_type", "TEXT NOT NULL DEFAULT 'individual'"),
    ("coaching_packages", "capacity",     "INTEGER NOT NULL DEFAULT 1"),
    ("time_slots",        "package_id",   "INTEGER REFERENCES coaching_packages(id)"),
]

for table, col, typedef in changes:
    cur.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    if col not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typedef}")
        print(f"✅ {table}.{col} اضافه شد")
    else:
        print(f"ℹ️  {table}.{col} قبلاً وجود دارد")

conn.commit()
conn.close()
print("\n✅ Migration کامل شد. ربات را restart کن.")
