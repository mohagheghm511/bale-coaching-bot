"""
رزرو جلسه کوچینگ
- انتخاب پکیج
- انتخاب تاریخ از تقویم ماهانه
- کنسلی با قانون ۴۸/۲۴ ساعت
"""
from sqlalchemy.orm import Session
from models.user import User
from models.product import TimeSlot, Reservation, ReservationStatus, CoachingPackage
from models.payment import Payment, PaymentStatus, PaymentMethod
from bale import Bot
from bot.sender import send_message, inline_keyboard
from bot.dispatcher import set_state, clear_state, get_state
from datetime import datetime, timedelta
from collections import defaultdict
import random, string
import jdatetime

WEEKDAYS_FA = {0: "دوشنبه", 1: "سه‌شنبه", 2: "چهارشنبه", 3: "پنج‌شنبه", 4: "جمعه", 5: "شنبه", 6: "یک‌شنبه"}

def to_jalali(dt: datetime) -> jdatetime.datetime:
    return jdatetime.datetime.fromgregorian(datetime=dt)

def jalali_str(dt: datetime) -> str:
    j = to_jalali(dt)
    return f"{j.year}/{j.month:02d}/{j.day:02d}"

def jalali_month_str(year: int, month: int) -> str:
    return f"{year}/{month:02d}"

# ==================== انتخاب پکیج ====================

TYPE_LABELS_USER = {
    "vip": "همراهی ویژه (VIP) 🟣",
    "individual": "تحول 🟢",
    "individual2": "آشنایی (تست کیفیت) 🔵",
    "group": "گروهی 👥",
    "all": "سایر 🌐",
}

async def show_coaching_types(bot: Bot, user: User, db: Session):
    """مرحله اول — انتخاب نوع کوچینگ"""

    types = [
        ("individual2", "آشنایی (تست کیفیت) 🔵"),
        ("individual",  "تحول 🟢"),
        ("vip",         "همراهی ویژه (VIP) 🟣"),
        ("group",       "گروهی 👥"),
        ("all",         "سایر 🌐"),
    ]

    msg = "🎯 نوع پکیج کوچینگ مورد نظرت رو انتخاب کن:"
    buttons = []
    for stype, label in types:
        buttons.append([{
            "text": label,
            "callback_data": f"coaching_type_{stype}"
        }])

    await send_message(bot, user.bale_id, msg, reply_markup=inline_keyboard(buttons))


async def show_packages(bot: Bot, user: User, db: Session, session_type: str = None):
    """نمایش پکیج‌های کوچینگ فیلتر شده بر اساس نوع"""
    query = db.query(CoachingPackage).filter(CoachingPackage.is_active == True)
    if session_type and session_type != "all":
        query = query.filter(CoachingPackage.session_type == session_type)
    packages = query.order_by(CoachingPackage.order).all()

    type_label = TYPE_LABELS_USER.get(session_type, "")

    if not packages:
        await send_message(bot, user.bale_id,
            f"⚠️ {type_label}\n\nفعلاً پکیجی برای این نوع کوچینگ موجود نیست.\nلطفاً بعداً مراجعه کنید.",
            reply_markup=inline_keyboard([
                [{"text": "🔙 بازگشت به انواع کوچینگ", "callback_data": "goto_reservation"}]
            ])
        )
        return

    msg = f"🎯 {type_label}\n━━━━━━━━━━━━━\nپکیج مورد نظرت رو انتخاب کن:\n"
    buttons = []
    icons = ["🔵", "🟢", "🟣", "🟠", "🔴"]
    for i, p in enumerate(packages):
        desc = f"{p.session_count} جلسه {p.session_duration} دقیقه‌ای"
        icon = icons[i % len(icons)]
        available = sum(1 for s in p.time_slots if s.is_available)
        bought = db.query(Reservation).filter(
            Reservation.package_id == p.id,
            Reservation.session_number == 1,
            Reservation.status.in_(["confirmed", "pending"])
        ).count()
        remaining = p.capacity - bought
        if remaining <= 0:
            avail_text = " | ⛔ ظرفیت تکمیل"
        else:
            avail_text = ""
        msg += f"\n{icon} {p.title}\n  {desc} — {p.price:,} تومان{avail_text}\n"
        buttons.append([{
            "text": f"{icon} {p.title} — {p.price:,} تومان",
            "callback_data": f"pkg_{p.id}"
        }])

    buttons.append([{"text": "🔙 بازگشت", "callback_data": "goto_reservation"}])
    await send_message(bot, user.bale_id, msg, reply_markup=inline_keyboard(buttons))

# ==================== نمایش جلسات پکیج ====================

async def show_package_sessions(bot: Bot, user: User, package_id: int, db: Session):
    """نمایش همه جلسات یک پکیج با تایم‌هایشان"""
    pkg = db.query(CoachingPackage).filter(CoachingPackage.id == package_id).first()
    if not pkg:
        await send_message(bot, user.bale_id, "❌ پکیج پیدا نشد.")
        return

    if pkg.session_type == "group":
        slots = sorted(pkg.time_slots, key=lambda s: s.date)
    else:
        slots = sorted(
            [s for s in pkg.time_slots if s.is_available],
            key=lambda s: s.date
        )

    if not slots:
        await send_message(bot, user.bale_id,
            f"📦 {pkg.title}\n\n"
            f"⚠️ در حال حاضر وقت آزادی برای این پکیج وجود ندارد.\n"
            f"لطفاً بعداً مراجعه کنید.",
            reply_markup=inline_keyboard([
                [{"text": "🔙 بازگشت به پکیج‌ها", "callback_data": "goto_reservation"}]
            ])
        )
        return

    msg = (
        f"📦 {pkg.title}\n"
        f"━━━━━━━━━━━━━\n"
        f"🔢 {pkg.session_count} جلسه {pkg.session_duration} دقیقه‌ای\n"
        f"💰 {pkg.price:,} تومان (کل پکیج)\n"
        f"━━━━━━━━━━━━━\n"
        f"📅 زمان‌بندی جلسات:\n\n"
    )
    my_slots = slots[:pkg.session_count]
    for i, slot in enumerate(my_slots):
        j = to_jalali(slot.date)
        weekday = WEEKDAYS_FA.get(slot.date.weekday(), "")
        time_str = slot.date.strftime("%H:%M")
        msg += f"  جلسه {i+1}: {weekday} {j.year}/{j.month:02d}/{j.day:02d} ساعت {time_str}\n"

    msg += f"\n✅ با خرید این پکیج، {pkg.session_count} جلسه برای شما رزرو می‌شود."

    await send_message(bot, user.bale_id, msg, reply_markup=inline_keyboard([
        [{"text": "✅ خرید این پکیج", "callback_data": f"buy_pkg_{package_id}"}],
        [{"text": "🔙 بازگشت به پکیج‌ها", "callback_data": "goto_reservation"}],
    ]))

# ==================== تقویم ماهانه ====================

async def show_calendar(bot: Bot, user: User, package_id: int, db: Session, year: int = None, month: int = None):
    """نمایش تقویم شمسی — ماه جاری با روزهای دارای وقت آزاد"""
    now = datetime.now()
    if not year or not month:
        j_now = to_jalali(now)
        year = j_now.year
        month = j_now.month

    j_start = jdatetime.datetime(year, month, 1)
    g_start = j_start.togregorian()
    if month < 7:
        days_in_month = 31
    elif month < 12:
        days_in_month = 30
    else:
        days_in_month = 29 if jdatetime.datetime(year, 1, 1).isleap() else 29
    j_end = jdatetime.datetime(year, month, days_in_month, 23, 59, 59)
    g_end = j_end.togregorian()

    slots = db.query(TimeSlot).filter(
        TimeSlot.is_available == True,
        TimeSlot.date > now,
        TimeSlot.date >= g_start,
        TimeSlot.date <= g_end,
    ).order_by(TimeSlot.date).all()

    days_with_slots = defaultdict(list)
    for slot in slots:
        j_slot = to_jalali(slot.date)
        days_with_slots[j_slot.day].append(slot)

    if not days_with_slots:
        next_month = month + 1 if month < 12 else 1
        next_year = year if month < 12 else year + 1
        await send_message(
            bot, user.bale_id,
            f"📅 در {jalali_month_str(year, month)} وقت آزادی نیست.",
            reply_markup=inline_keyboard([
                [{"text": f"← ماه بعد ({jalali_month_str(next_year, next_month)})", "callback_data": f"cal_{package_id}_{next_year}_{next_month}"}],
                [{"text": "🔙 بازگشت به پکیج‌ها", "callback_data": "goto_reservation"}],
            ])
        )
        return

    set_state(user.bale_id, {"step": "selecting_day", "package_id": package_id, "year": year, "month": month})

    buttons = []
    for day in sorted(days_with_slots.keys()):
        slot_count = len(days_with_slots[day])
        weekday = days_with_slots[day][0].date.weekday()
        day_name = WEEKDAYS_FA.get(weekday, "")
        buttons.append([{
            "text": f"{day_name} {day}/{month} ({slot_count} وقت)",
            "callback_data": f"day_{package_id}_{year}_{month}_{day}"
        }])

    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    buttons.append([
        {"text": f"→ {jalali_month_str(prev_year, prev_month)}", "callback_data": f"cal_{package_id}_{prev_year}_{prev_month}"},
        {"text": f"← {jalali_month_str(next_year, next_month)}", "callback_data": f"cal_{package_id}_{next_year}_{next_month}"},
    ])

    await send_message(
        bot, user.bale_id,
        f"📅 روز مورد نظرت رو انتخاب کن ({jalali_month_str(year, month)}):",
        reply_markup=inline_keyboard(buttons)
    )

async def show_day_slots(bot: Bot, user: User, package_id: int, year: int, month: int, day: int, db: Session):
    """نمایش ساعت‌های آزاد یک روز خاص — سال/ماه/روز شمسی"""
    j_start = jdatetime.datetime(year, month, day, 0, 0, 0)
    j_end   = jdatetime.datetime(year, month, day, 23, 59, 59)
    from_dt = j_start.togregorian()
    to_dt   = j_end.togregorian()

    slots = db.query(TimeSlot).filter(
        TimeSlot.is_available == True,
        TimeSlot.date >= from_dt,
        TimeSlot.date <= to_dt,
    ).order_by(TimeSlot.date).all()

    if not slots:
        await send_message(bot, user.bale_id, "این روز وقت آزادی نمونده!")
        return

    weekday = slots[0].date.weekday()
    day_name = WEEKDAYS_FA.get(weekday, "")

    buttons = []
    for slot in slots:
        time_str = slot.date.strftime("%H:%M")
        buttons.append([{
            "text": f"⏰ ساعت {time_str}",
            "callback_data": f"slot_{slot.id}_{package_id}"
        }])
    buttons.append([{"text": "🔙 بازگشت به تقویم", "callback_data": f"cal_{package_id}_{year}_{month}"}])

    await send_message(
        bot, user.bale_id,
        f"📅 {day_name} {day}/{month}/{year}\nساعت مورد نظرت رو انتخاب کن:",
        reply_markup=inline_keyboard(buttons)
    )

# ==================== خرید پکیج — رزرو همه جلسات ====================

async def confirm_slot(bot: Bot, user: User, slot_id: int, package_id: int, db: Session):
    """این تابع دیگه استفاده نمیشه — برای سازگاری با dispatcher نگه داشته شده"""
    await confirm_package_purchase(bot, user, package_id, db)

async def confirm_package_purchase(bot: Bot, user: User, package_id: int, db: Session):
    """خرید پکیج — همه جلسات یکجا رزرو میشن"""
    pkg = db.query(CoachingPackage).filter(CoachingPackage.id == package_id).first()
    if not pkg:
        await send_message(bot, user.bale_id, "❌ پکیج پیدا نشد.")
        return

    bought_count = db.query(Reservation).filter(
        Reservation.package_id == package_id,
        Reservation.session_number == 1,
        Reservation.status == ReservationStatus.confirmed
    ).count()

    if bought_count >= pkg.capacity:
        await send_message(bot, user.bale_id,
            f"⛔ ظرفیت پکیج «{pkg.title}» تکمیل شده است.\n"
            f"برای اطلاع از پکیج‌های بعدی منتظر اطلاع‌رسانی باشید.",
            reply_markup=inline_keyboard([[{"text": "🔙 بازگشت به پکیج‌ها", "callback_data": "goto_reservation"}]])
        )
        return

    existing = db.query(Reservation).filter(
        Reservation.user_id == user.id,
        Reservation.package_id == package_id,
        Reservation.status == ReservationStatus.confirmed
    ).first()
    if existing:
        await send_message(bot, user.bale_id,
            f"✅ شما قبلاً پکیج «{pkg.title}» را خریداری کرده‌اید.",
            reply_markup=inline_keyboard([[{"text": "🏠 منو اصلی", "callback_data": "goto_main"}]])
        )
        return

    if pkg.session_type == "group":
        slots = sorted(pkg.time_slots, key=lambda s: s.date)
    else:
        slots = sorted(
            [s for s in pkg.time_slots if s.is_available],
            key=lambda s: s.date
        )

    if len(slots) < pkg.session_count:
        await send_message(bot, user.bale_id,
            f"⚠️ تعداد وقت‌های آزاد این پکیج کافی نیست.\n"
            f"لطفاً بعداً مراجعه کنید.",
            reply_markup=inline_keyboard([[{"text": "🔙 بازگشت", "callback_data": "goto_reservation"}]])
        )
        return

    # چک پلن اقساط — به ترتیب (اولین پلن استفاده نشده)
    from models.installment import InstallmentPlan, Installment, UserInstallment
    # پیدا کردن پلن‌هایی که هنوز کسی ازشون استفاده نکرده
    used_plan_ids = [ui.plan_id for ui in db.query(UserInstallment).filter(
        UserInstallment.user_id != user.id
    ).all()]
    inst_plan = db.query(InstallmentPlan).filter(
        InstallmentPlan.package_id == package_id,
        InstallmentPlan.is_active == True,
        ~InstallmentPlan.id.in_(used_plan_ids) if used_plan_ids else True
    ).order_by(InstallmentPlan.id).first()
    # اگه پلن اقساط نبود، اولین پلن موجود رو بگیر
    if not inst_plan:
        inst_plan = db.query(InstallmentPlan).filter(
            InstallmentPlan.package_id == package_id,
            InstallmentPlan.is_active == True
        ).order_by(InstallmentPlan.id).first()

    tracking = "COACH-" + ''.join(random.choices(string.digits, k=5))
    payment = Payment(
        user_id=user.id,
        amount=pkg.price,
        method=PaymentMethod.card_transfer,
        status=PaymentStatus.pending,
        tracking_code=tracking
    )
    db.add(payment)
    db.flush()

    reservations = []
    for i, slot in enumerate(slots[:pkg.session_count]):
        res = Reservation(
            user_id=user.id,
            time_slot_id=slot.id,
            package_id=package_id,
            session_number=i + 1,
            price=pkg.price if i == 0 else 0,
            status=ReservationStatus.pending,
        )
        db.add(res)
        slot.is_available = False
        reservations.append(res)

    db.flush()
    payment.reservation_id = reservations[0].id
    db.commit()
    clear_state(user.bale_id)

    sessions_text = ""
    for i, slot in enumerate(slots[:pkg.session_count]):
        j = to_jalali(slot.date)
        wd = WEEKDAYS_FA.get(slot.date.weekday(), "")
        t = slot.date.strftime("%H:%M")
        sessions_text += f"  جلسه {i+1}: {wd} {j.year}/{j.month:02d}/{j.day:02d} ساعت {t}\n"

    msg = (
        f"📋 خلاصه خرید\n━━━━━━━━━━━━━\n"
        f"📦 پکیج: {pkg.title}\n"
        f"🔢 {pkg.session_count} جلسه {pkg.session_duration} دقیقه‌ای\n"
        f"━━━━━━━━━━━━━\n"
        f"📅 زمان‌بندی جلسات:\n{sessions_text}"
        f"━━━━━━━━━━━━━\n"
        f"💰 مبلغ کل: {pkg.price:,} تومان\n"
        f"🔖 کد پیگیری: {tracking}"
    )

    if inst_plan:
        # نمایش گزینه نقدی / اقساطی
        inst_list = db.query(Installment).filter(Installment.plan_id == inst_plan.id).order_by(Installment.number).all()
        inst_text = ""
        for inst in inst_list:
            due = inst.due_date.strftime("%Y/%m/%d") if inst.due_date else "-"
            inst_text += f"  قسط {inst.number}: {inst.amount:,} تومان — سررسید: {due}\n"
        msg += (
            f"\n━━━━━━━━━━━━━\n"
            f"💳 پرداخت اولیه (اقساطی): {inst_plan.first_payment:,} تومان\n"
            f"📋 اقساط بعدی:\n{inst_text}"
        )
        await send_message(bot, user.bale_id, msg, reply_markup=inline_keyboard([
            [{"text": "💵 پرداخت نقدی", "callback_data": f"pay_{payment.id}"}],
            [{"text": "📋 پرداخت اقساطی", "callback_data": f"pay_installment_plan_{inst_plan.id}_{payment.id}"}],
            [{"text": "🏠 منو اصلی", "callback_data": "goto_main"}],
        ]))
    else:
        await send_message(bot, user.bale_id, msg, reply_markup=inline_keyboard([
            [{"text": "💳 پرداخت", "callback_data": f"pay_{payment.id}"}],
            [{"text": "🏠 منو اصلی", "callback_data": "goto_main"}],
        ]))

# ==================== کنسلی ====================

async def show_my_reservations_for_cancel(bot: Bot, user: User, db: Session):
    """نمایش رزروهای فعال برای کنسل کردن"""
    reservations = db.query(Reservation).filter(
        Reservation.user_id == user.id,
        Reservation.status == ReservationStatus.confirmed
    ).order_by(Reservation.created_at.desc()).all()

    if not reservations:
        await send_message(bot, user.bale_id, "رزرو فعالی نداری.")
        return

    now = datetime.now()
    buttons = []
    for res in reservations:
        if not res.time_slot:
            continue
        slot_date = res.time_slot.date
        hours_left = (slot_date - now).total_seconds() / 3600
        date_str = slot_date.strftime("%Y/%m/%d %H:%M")

        if hours_left < 0:
            continue

        if hours_left < 24:
            label = f"🔴 {date_str} (زیر ۲۴ ساعت — هزینه سوخت)"
        elif hours_left < 48:
            label = f"🟡 {date_str} (بین ۲۴-۴۸ ساعت)"
        else:
            label = f"🟢 {date_str} (قابل کنسل)"

        buttons.append([{"text": label, "callback_data": f"cancel_res_{res.id}"}])

    if not buttons:
        await send_message(bot, user.bale_id, "رزرو قابل کنسلی نداری.")
        return

    await send_message(
        bot, user.bale_id,
        "📅 کدوم رزرو رو می‌خوای کنسل کنی?\n\n"
        "🟢 بدون هزینه | 🟡 بدون هزینه | 🔴 هزینه سوخت",
        reply_markup=inline_keyboard(buttons)
    )

async def cancel_reservation_user(bot: Bot, user: User, res_id: int, db: Session):
    """کنسلی توسط کاربر با قانون زمانی"""
    res = db.query(Reservation).filter(
        Reservation.id == res_id,
        Reservation.user_id == user.id
    ).first()

    if not res or not res.time_slot:
        await send_message(bot, user.bale_id, "❌ رزرو پیدا نشد.")
        return

    now = datetime.now()
    slot_date = res.time_slot.date
    hours_left = (slot_date - now).total_seconds() / 3600

    if hours_left < 0:
        await send_message(bot, user.bale_id, "❌ این جلسه قبلاً برگزار شده.")
        return

    if hours_left < 24:
        cancel_count = db.query(Reservation).filter(
            Reservation.user_id == user.id,
            Reservation.status == ReservationStatus.cancelled,
            Reservation.cancel_reason == "late_cancel"
        ).count()

        if cancel_count >= 1:
            await send_message(
                bot, user.bale_id,
                "❌ قبلاً یک بار کنسلی زیر ۲۴ ساعت داشتی.\n"
                "امکان کنسل مجدد وجود نداره.",
                reply_markup=inline_keyboard([
                    [{"text": "📞 تماس با پشتیبانی", "callback_data": "goto_support"}],
                ])
            )
            return

        await send_message(
            bot, user.bale_id,
            "⚠️ توجه!\nکنسلی کمتر از ۲۴ ساعت قبل از جلسه، هزینه سوخت می‌شه.\n\n"
            "مطمئنی می‌خوای کنسل کنی؟",
            reply_markup=inline_keyboard([
                [{"text": "✅ بله، کنسل کن (هزینه سوخت)", "callback_data": f"confirm_cancel_{res_id}_late"}],
                [{"text": "❌ خیر، برگشت", "callback_data": "goto_main"}],
            ])
        )
        return

    elif hours_left < 48:
        await send_message(
            bot, user.bale_id,
            "⚠️ بین ۲۴ تا ۴۸ ساعت مونده به جلسه.\n"
            "کنسل می‌کنی؟ (بدون هزینه)",
            reply_markup=inline_keyboard([
                [{"text": "✅ بله، کنسل کن", "callback_data": f"confirm_cancel_{res_id}_free"}],
                [{"text": "❌ خیر، برگشت", "callback_data": "goto_main"}],
            ])
        )
        return

    else:
        await do_cancel(bot, user, res, db, is_late=False)

async def do_cancel(bot: Bot, user: User, res: Reservation, db: Session, is_late: bool):
    """اجرای کنسلی"""
    res.status = ReservationStatus.cancelled
    res.cancel_reason = "late_cancel" if is_late else "user_cancel"

    if res.time_slot:
        res.time_slot.is_available = True

    db.commit()

    if is_late:
        msg = "❌ رزرو کنسل شد.\n⚠️ چون کمتر از ۲۴ ساعت مونده بود، هزینه جلسه سوخت."
    else:
        msg = "✅ رزرو با موفقیت کنسل شد.\n\nبرای رزرو مجدد می‌تونی از منو استفاده کنی."

    await send_message(
        bot, user.bale_id, msg,
        reply_markup=inline_keyboard([
            [{"text": "📅 رزرو جدید", "callback_data": "goto_reservation"}],
            [{"text": "🏠 منو اصلی", "callback_data": "goto_main"}],
        ])
    )

    from core.config import settings
    from bot.sender import send_message as sm
    slot_date = res.time_slot.date.strftime("%Y/%m/%d %H:%M") if res.time_slot else "نامشخص"
    await bot.send_message(
        settings.ADMIN_BALE_ID,
        f"{'⚠️' if is_late else '❌'} کنسلی رزرو\n"
        f"👤 {user.full_name}\n"
        f"📅 {slot_date}\n"
        f"{'💸 هزینه سوخت شد' if is_late else '✅ بدون هزینه'}"
    )

# ==================== alias برای dispatcher ====================
async def show_types(bot: Bot, user: User, db: Session):
    await show_packages(bot, user, db)