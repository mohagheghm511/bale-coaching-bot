from bale import Bot
from sqlalchemy.orm import Session
from core.database import get_db, engine, Base
from core.config import settings
from services.scheduler import start_scheduler

from models import user, test, product, payment, review

Base.metadata.create_all(bind=engine)

def run_migrations():
    import sqlite3, os
    db_url = settings.DATABASE_URL
    db_path = db_url.replace("sqlite:///", "")
    if not os.path.isabs(db_path):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(base_dir, db_path.lstrip("./"))
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        for table, col, coltype in [
            ("products", "capacity", "INTEGER DEFAULT 0"),
            ("products", "sold_count", "INTEGER DEFAULT 0"),
            ("time_slots", "session_type", "VARCHAR(50)"),
        ]:
            cursor.execute(f"PRAGMA table_info({table})")
            cols = [r[1] for r in cursor.fetchall()]
            if col not in cols:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")
                conn.commit()
        conn.close()
    except Exception as e:
        print(f"Migration warning: {e}")

run_migrations()

bot = Bot(token=settings.BALE_BOT_TOKEN)

@bot.event
async def on_ready():
    start_scheduler()
    print("✅ ربات کوچینگ آماده است")

@bot.event
async def on_message(message):
    if not message.author:
        return
    db = next(get_db())
    try:
        from bot.dispatcher import process_message
        await process_message(bot, message, db)
    except Exception as e:
        print(f"Error: {e}")
        import traceback; traceback.print_exc()
    finally:
        db.close()

@bot.event
async def on_callback(callback):
    if not callback.from_user:
        return
    db = next(get_db())
    try:
        from bot.dispatcher import process_callback
        await process_callback(bot, callback, db)
    except Exception as e:
        print(f"Error: {e}")
        import traceback; traceback.print_exc()
    finally:
        db.close()

@bot.event
async def on_successful_payment(successful_payment):
    """
    successful_payment = SuccessfulPayment object
    فقط invoice_payload داره — کاربر رو از payment_id توی payload پیدا میکنیم
    """
    db = next(get_db())
    try:
        payload = getattr(successful_payment, 'invoice_payload', None)
        if not payload or not payload.startswith("payment_"):
            print(f"Invalid payload: {payload}")
            return

        payment_id = int(payload.replace("payment_", ""))

        from models.payment import Payment, PaymentStatus
        from models.user import User

        pmt = db.query(Payment).filter(Payment.id == payment_id).first()
        if not pmt:
            print(f"Payment {payment_id} not found")
            return

        # کاربر رو از payment پیدا کن
        user_obj = db.query(User).filter(User.id == pmt.user_id).first()
        if not user_obj:
            print(f"User not found for payment {payment_id}")
            return

        print(f"✅ Successful payment: {payload} | user: {user_obj.full_name}")

        from bot.handlers.payment import handle_successful_payment
        await handle_successful_payment(bot, user_obj, successful_payment, db)

    except Exception as e:
        print(f"SuccessfulPayment Error: {e}")
        import traceback; traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    bot.run()
