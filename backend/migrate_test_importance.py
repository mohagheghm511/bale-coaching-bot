"""
migrate_test_importance.py
اجرا کن: python3 migrate_test_importance.py
"""
import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(__file__), "coaching_bot.db")
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

try:
    cur.execute("ALTER TABLE tests ADD COLUMN importance TEXT")
    print("✅ ستون importance اضافه شد.")
except Exception as e:
    print(f"⏭ رد شد: {e}")

conn.commit()
conn.close()
print("✅ Migration تمام شد.")
