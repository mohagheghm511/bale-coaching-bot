"""
Migration: اضافه کردن session_type به coaching_packages
اجرا: python migrate_add_session_type.py
"""
import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(__file__), "coaching_bot.db")
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("PRAGMA table_info(coaching_packages)")
cols = [r[1] for r in cur.fetchall()]

if "session_type" not in cols:
    cur.execute("ALTER TABLE coaching_packages ADD COLUMN session_type TEXT NOT NULL DEFAULT 'individual'")
    conn.commit()
    print("✅ ستون session_type به coaching_packages اضافه شد.")
else:
    print("ℹ️ session_type قبلاً وجود دارد.")

conn.close()
