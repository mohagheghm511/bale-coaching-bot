"""
migrate_installment.py
اجرا کن: python3 migrate_installment.py
"""
import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(__file__), "coaching_bot.db")
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.executescript("""
CREATE TABLE IF NOT EXISTS installment_plans (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id    INTEGER REFERENCES products(id),
    package_id    INTEGER REFERENCES coaching_packages(id),
    first_payment INTEGER NOT NULL,
    total_count   INTEGER NOT NULL,
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    DATETIME DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
);

CREATE TABLE IF NOT EXISTS installments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id    INTEGER NOT NULL REFERENCES installment_plans(id),
    number     INTEGER NOT NULL,
    amount     INTEGER NOT NULL,
    due_date   DATETIME NOT NULL,
    status     TEXT NOT NULL DEFAULT 'pending',
    created_at DATETIME DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
);

CREATE TABLE IF NOT EXISTS user_installments (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL REFERENCES users(id),
    plan_id        INTEGER NOT NULL REFERENCES installment_plans(id),
    installment_id INTEGER NOT NULL REFERENCES installments(id),
    payment_id     INTEGER REFERENCES payments(id),
    status         TEXT NOT NULL DEFAULT 'pending',
    created_at     DATETIME DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
);
""")

conn.commit()
conn.close()
print("✅ Migration اقساط تمام شد.")
