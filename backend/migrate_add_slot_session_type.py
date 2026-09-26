"""
Migration: افزودن ستون session_type به جدول time_slots
اجرا: python migrate_add_slot_session_type.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "coaching_bot.db")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # بررسی وجود ستون
    cursor.execute("PRAGMA table_info(time_slots)")
    columns = [row[1] for row in cursor.fetchall()]

    if "session_type" not in columns:
        cursor.execute("ALTER TABLE time_slots ADD COLUMN session_type VARCHAR(50)")
        conn.commit()
        print("✅ ستون session_type به جدول time_slots اضافه شد.")
    else:
        print("ℹ️ ستون session_type از قبل وجود دارد.")

    conn.close()

if __name__ == "__main__":
    migrate()
