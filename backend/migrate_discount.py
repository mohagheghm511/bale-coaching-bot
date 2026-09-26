"""
migrate_discount.py
اجرا کن: python3 migrate_discount.py
"""
import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(__file__), "coaching_bot.db")
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.executescript("""
CREATE TABLE IF NOT EXISTS discount_codes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT NOT NULL UNIQUE,
    amount      INTEGER NOT NULL,
    max_uses    INTEGER NOT NULL DEFAULT 0,
    used_count  INTEGER NOT NULL DEFAULT 0,
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  DATETIME DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
);

-- اضافه کردن فیلد تخفیف و دلیل رد به پرداخت‌ها
""")

# اضافه کردن ستون‌های جدید به payments
for col_sql in [
    "ALTER TABLE payments ADD COLUMN discount_amount INTEGER DEFAULT 0",
    "ALTER TABLE payments ADD COLUMN discount_code TEXT",
    "ALTER TABLE payments ADD COLUMN reject_reason TEXT",
]:
    try:
        cur.execute(col_sql)
        print(f"✅ {col_sql[:50]}...")
    except Exception as e:
        print(f"⏭ رد شد: {e}")

conn.commit()
conn.close()
print("✅ Migration تمام شد.")
