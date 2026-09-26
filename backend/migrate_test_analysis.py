"""
migrate_test_analysis.py
اجرا کن: python3 migrate_test_analysis.py
"""
import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(__file__), "coaching_bot.db")
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

migrations = [
    # نوع تحلیل تست: numeric / typology / combined
    "ALTER TABLE tests ADD COLUMN analysis_type TEXT NOT NULL DEFAULT 'numeric'",
    # لحن: formal / friendly
    "ALTER TABLE tests ADD COLUMN tone TEXT NOT NULL DEFAULT 'friendly'",
    # برچسب تیپ گزینه (برای تحلیل تیپی مثلاً A,B,C,D یا INTJ و...)
    "ALTER TABLE options ADD COLUMN type_label TEXT",
    # متن تحلیل ترکیبی بر اساس الگوی جواب‌ها (JSON)
    "ALTER TABLE score_ranges ADD COLUMN pattern_keys TEXT",
]

for sql in migrations:
    try:
        cur.execute(sql)
        print(f"✅ {sql[:60]}...")
    except sqlite3.OperationalError as e:
        print(f"⏭ رد شد (احتمالاً قبلاً اضافه شده): {e}")

conn.commit()
conn.close()
print("\n✅ Migration تمام شد.")
