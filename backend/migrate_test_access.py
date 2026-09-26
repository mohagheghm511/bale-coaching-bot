"""
migrate_test_access.py
اجرا کن: python3 migrate_test_access.py
"""
import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(__file__), "coaching_bot.db")
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

for col_sql in [
    "ALTER TABLE tests ADD COLUMN access_type TEXT DEFAULT 'free'",
    "ALTER TABLE tests ADD COLUMN analysis_content TEXT",
    "CREATE TABLE IF NOT EXISTS test_invites (id INTEGER PRIMARY KEY AUTOINCREMENT, inviter_user_id INTEGER NOT NULL, invited_user_id INTEGER NOT NULL, test_id INTEGER NOT NULL, created_at DATETIME DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now')))",
    "CREATE TABLE IF NOT EXISTS bot_settings (key TEXT PRIMARY KEY, value TEXT)",
]:
    try:
        cur.execute(col_sql)
        print(f"✅ {col_sql[:60]}...")
    except Exception as e:
        print(f"⏭ رد شد: {e}")

conn.commit()
conn.close()
print("✅ Migration تمام شد.")