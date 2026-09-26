from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

scheduler = AsyncIOScheduler()

def start_scheduler():
    # هر ساعت چک کن
    scheduler.add_job(send_reminders, IntervalTrigger(hours=1))
    scheduler.start()
    print("✅ Scheduler started")

async def send_reminders():
    from core.database import SessionLocal
    from models.product import Reservation, ReservationStatus
    from datetime import datetime, timedelta
    import jdatetime

    db = SessionLocal()
    try:
        now = datetime.now()
        one_day_later = now + timedelta(hours=24)
        one_hour_later = now + timedelta(hours=1)

        reservations = db.query(Reservation).filter(
            Reservation.status.in_([ReservationStatus.confirmed, ReservationStatus.rescheduled]),
        ).all()

        from main import bot
        from core.config import settings

        for res in reservations:
            if not res.time_slot:
                continue

            slot_dt = res.time_slot.date
            diff = (slot_dt - now).total_seconds() / 3600  # ساعت

            try:
                j = jdatetime.datetime.fromgregorian(datetime=slot_dt)
                slot_date_fa = j.strftime("%Y/%m/%d %H:%M")
            except:
                slot_date_fa = slot_dt.strftime("%Y/%m/%d %H:%M")

            pkg_title = res.package.title if res.package else "کوچینگ"
            user_name = res.user.full_name or "کاربر"

            # یه روز قبل (بین ۲۳ تا ۲۵ ساعت)
            if 23 <= diff <= 25 and not res.reminder_sent:
                msg_user = (
                    f"🔔 یادآوری جلسه کوچینگ\n\n"
                    f"سلام {user_name} عزیز!\n"
                    f"جلسه «{pkg_title}» شما فردا است:\n"
                    f"📅 {slot_date_fa}\n\n"
                    f"لطفاً آماده باشید 🌱"
                )
                msg_admin = (
                    f"🔔 یادآوری جلسه فردا\n"
                    f"👤 {user_name} | 📞 {res.user.phone or '-'}\n"
                    f"📦 {pkg_title} | جلسه {res.session_number}\n"
                    f"📅 {slot_date_fa}"
                )
                try:
                    await bot.send_message(res.user.bale_id, msg_user)
                    for admin_id in settings.admin_ids:
                        await bot.send_message(admin_id, msg_admin)
                    res.reminder_sent = True
                    db.commit()
                except Exception as e:
                    print(f"reminder error: {e}")

            # یه ساعت قبل (بین ۰.۸ تا ۱.۲ ساعت)
            elif 0.8 <= diff <= 1.2:
                msg_user = (
                    f"⏰ جلسه شما یک ساعت دیگر است!\n\n"
                    f"👤 {user_name} عزیز\n"
                    f"📦 {pkg_title} | جلسه {res.session_number}\n"
                    f"📅 {slot_date_fa}\n\n"
                    f"آماده باشید 💪"
                )
                msg_admin = (
                    f"⏰ جلسه یک ساعت دیگر\n"
                    f"👤 {user_name} | 📞 {res.user.phone or '-'}\n"
                    f"📦 {pkg_title} | جلسه {res.session_number}\n"
                    f"📅 {slot_date_fa}"
                )
                try:
                    await bot.send_message(res.user.bale_id, msg_user)
                    for admin_id in settings.admin_ids:
                        await bot.send_message(admin_id, msg_admin)
                except Exception as e:
                    print(f"reminder 1h error: {e}")

    finally:
        db.close()


async def notify_cancellation(reservation, db):
    from main import bot
    from bot.sender import inline_keyboard
    slot_date = "نامشخص"
    if reservation.time_slot:
        import jdatetime
        try:
            j = jdatetime.datetime.fromgregorian(datetime=reservation.time_slot.date)
            slot_date = j.strftime("%Y/%m/%d %H:%M")
        except:
            slot_date = reservation.time_slot.date.strftime("%Y/%m/%d %H:%M")

    await bot.send_message(reservation.user.bale_id,
        f"❌ جلسه شما در تاریخ {slot_date} لغو شد.\n\n"
        f"لطفاً زمان جدیدی انتخاب کنید 👇",
        components=inline_keyboard([
            [{"text": "📅 انتخاب زمان جدید", "callback_data": "goto_reservation"}]
        ])
    )
