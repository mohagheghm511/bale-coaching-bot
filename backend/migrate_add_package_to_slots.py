"""
Migration: اضافه کردن package_id به جدول time_slots
اجرا: python migrate_add_package_to_slots.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "coaching_bot.db")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# بررسی اینکه ستون قبلاً هست یا نه
cur.execute("PRAGMA table_info(time_slots)")
columns = [row[1] for row in cur.fetchall()]

if "package_id" not in columns:
    cur.execute("ALTER TABLE time_slots ADD COLUMN package_id INTEGER REFERENCES coaching_packages(id)")
    conn.commit()
    print("✅ ستون package_id به time_slots اضافه شد.")
else:
    print("ℹ️ ستون package_id قبلاً وجود دارد.")

conn.close()
