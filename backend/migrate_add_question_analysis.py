"""
Migration: افزودن ستون analysis به جدول questions
اجرا: python migrate_add_question_analysis.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "coaching_bot.db")

def run():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # بررسی وجود ستون
    cursor.execute("PRAGMA table_info(questions)")
    columns = [row[1] for row in cursor.fetchall()]

    if "analysis" not in columns:
        cursor.execute("ALTER TABLE questions ADD COLUMN analysis TEXT")
        conn.commit()
        print("✅ ستون analysis به جدول questions اضافه شد.")
    else:
        print("ℹ️ ستون analysis قبلاً وجود دارد.")

    conn.close()

if __name__ == "__main__":
    run()
