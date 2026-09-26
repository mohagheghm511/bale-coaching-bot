"""
اجرا کن: python migrate_capacity.py
این فایل ستون‌های capacity و sold_count را به جدول products اضافه می‌کند
"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "coaching_bot.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE products ADD COLUMN capacity INTEGER DEFAULT 0")
    print("✅ ستون capacity اضافه شد")
except Exception as e:
    print(f"capacity: {e}")

try:
    cursor.execute("ALTER TABLE products ADD COLUMN sold_count INTEGER DEFAULT 0")
    print("✅ ستون sold_count اضافه شد")
except Exception as e:
    print(f"sold_count: {e}")

conn.commit()
conn.close()
print("✅ Migration تمام شد")
