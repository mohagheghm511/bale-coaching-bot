from sqlalchemy.orm import Session
from sqlalchemy import func
from models.user import User, UserStatus
from models.product import Reservation, ReservationStatus, TimeSlot, Product, ProductType, CoachingPackage
from models.payment import Payment, PaymentStatus, BroadcastMessage
from models.test import Test, Question, Option, ScoreRange, TestResult
from models.static_content import StaticContent, ContentType, MediaType
from models.discount import DiscountCode
from models.installment import InstallmentPlan, Installment
from bale import Bot
from bot.sender import send_message, inline_keyboard, send_photo
from bot.dispatcher import get_state, set_state, clear_state
from datetime import datetime, timedelta

bot_settings = {
    "welcome_message": "سلام! به ربات کوچینگ خوش آمدید",
    "card_number": "",
    "card_owner": "",
}

async def show_dashboard(bot, user, db):
    total_users = db.query(func.count(User.id)).scalar()
    pending_payments = db.query(func.count(Payment.id)).filter(Payment.status == PaymentStatus.uploaded).scalar()
    active_reservations = db.query(func.count(Reservation.id)).filter(Reservation.status == ReservationStatus.confirmed).scalar()
    total_income = db.query(func.sum(Payment.amount)).filter(Payment.status == PaymentStatus.approved).scalar() or 0
    total_tests = db.query(func.count(TestResult.id)).scalar()
    from models.review import Review
    pending_reviews = db.query(func.count(Review.id)).filter(Review.is_approved == False).scalar()
    msg = (
        "⚙️ داشبورد مدیریت\n━━━━━━━━━━━━━\n"
        f"👥 کل کاربران: {total_users:,}\n"
        f"📅 رزروهای فعال: {active_reservations:,}\n"
        f"💰 درآمد کل: {total_income:,} تومان\n"
        f"🧪 تست انجام شده: {total_tests:,}\n"
        f"💳 فیش در انتظار: {pending_payments}\n"
        f"⭐ نظر در انتظار: {pending_reviews}\n━━━━━━━━━━━━━"
    )
    await send_message(bot, user.bale_id, msg, reply_markup=inline_keyboard([
        [{"text": "💳 فیش‌های در انتظار", "callback_data": "admin_pending_payments"},
         {"text": "📅 مدیریت رزروها", "callback_data": "admin_reservations"}],
        [{"text": "👥 جستجوی کاربر", "callback_data": "admin_search_user"},
         {"text": "📢 پیام انبوه", "callback_data": "admin_broadcast"}],
        [{"text": "🧪 مدیریت تست‌ها", "callback_data": "admin_tests"},
         {"text": "🛍 مدیریت محصولات", "callback_data": "admin_products"}],
        [{"text": "➕ افزودن زمان آزاد", "callback_data": "admin_add_slot"},
         {"text": "📦 مدیریت پکیج‌ها", "callback_data": "admin_packages"}],
        [{"text": "⭐ تأیید نظرات", "callback_data": "admin_reviews"},
         {"text": "📊 گزارش مالی", "callback_data": "admin_report"}],
        [{"text": "📋 محتوای صفحات", "callback_data": "admin_static_content"},
         {"text": "📤 اکسل کاربران", "callback_data": "admin_export_users"}],
        [{"text": "🎟 کدهای تخفیف", "callback_data": "admin_discounts"},
         {"text": "⚙️ تنظیمات", "callback_data": "admin_settings"}],
    ]))

async def show_pending_payments(bot, admin, db):
    payments = db.query(Payment).filter(Payment.status == PaymentStatus.uploaded).order_by(Payment.created_at).all()
    if not payments:
        await send_message(bot, admin.bale_id, "✅ هیچ فیشی در انتظار تأیید نیست.")
        return
    await send_message(bot, admin.bale_id, f"💳 {len(payments)} فیش در انتظار تأیید:")
    for p in payments[:5]:
        elapsed = int((datetime.now() - p.created_at.replace(tzinfo=None)).total_seconds() / 60)
        msg = (
            "━━━━━━━━━━━━━\n"
            f"👤 {p.user.full_name} | 📞 {p.user.phone}\n"
            f"💰 {p.amount:,} تومان | 🔖 {p.tracking_code}\n"
            f"⏱ {elapsed} دقیقه پیش"
        )
        await send_message(bot, admin.bale_id, msg, reply_markup=inline_keyboard([
            [{"text": "✅ تأیید", "callback_data": f"admin_approve_pay_{p.id}"},
             {"text": "❌ رد", "callback_data": f"admin_reject_pay_{p.id}"}],
            [{"text": "👁 مشاهده فیش", "callback_data": f"admin_view_receipt_{p.id}"}],
        ]))

async def show_reservations(bot, admin, db):
    reservations = db.query(Reservation).filter(
        Reservation.status.in_([ReservationStatus.confirmed, ReservationStatus.rescheduled, ReservationStatus.pending])
    ).order_by(Reservation.created_at.desc()).limit(20).all()
    if not reservations:
        await send_message(bot, admin.bale_id, "رزرو فعالی وجود ندارد.")
        return
    await send_message(bot, admin.bale_id, f"رزروهای فعال: {len(reservations)}")
    for res in reservations:
        import jdatetime
        slot_date = "نامشخص"
        if res.time_slot:
            j = jdatetime.datetime.fromgregorian(datetime=res.time_slot.date)
            slot_date = j.strftime("%Y/%m/%d %H:%M")
        pkg_title = res.package.title if res.package else "-"
        phone = res.user.phone or "ثبت نشده"
        msg = (
            f"نام: {res.user.full_name}\n"
            f"شماره: {phone}\n"
            f"بله‌ایدی: {res.user.bale_id}\n"
            f"دوره: {pkg_title}\n"
            f"جلسه: {res.session_number}\n"
            f"تاریخ: {slot_date}"
        )
        await send_message(bot, admin.bale_id, msg, reply_markup=inline_keyboard([
            [{"text": "جابجایی", "callback_data": f"admin_reschedule_{res.id}"},
             {"text": "لغو", "callback_data": f"admin_cancel_res_{res.id}"}],
        ]))

async def prompt_search_user(bot, admin):
    set_state(admin.bale_id, {"step": "admin_search_user"})
    await send_message(bot, admin.bale_id, "👤 اسم یا شماره کاربر را بنویس:")

async def search_user(bot, admin, query, db):
    users = db.query(User).filter(
        (User.full_name.ilike(f"%{query}%")) |
        (User.phone.ilike(f"%{query}%")) |
        (User.username.ilike(f"%{query}%"))
    ).limit(5).all()
    clear_state(admin.bale_id)
    if not users:
        await send_message(bot, admin.bale_id, "کاربری پیدا نشد.")
        return
    for u in users:
        msg = f"👤 {u.full_name}\n📞 {u.phone or 'ثبت نشده'}\n🧪 {len(u.test_results)} تست | 📅 {len(u.reservations)} رزرو"
        await send_message(bot, admin.bale_id, msg, reply_markup=inline_keyboard([
            [{"text": "📋 پروفایل کامل", "callback_data": f"admin_user_{u.id}"},
             {"text": "💬 ارسال پیام", "callback_data": f"admin_msg_user_{u.id}"}],
            [{"text": "🚫 بلاک", "callback_data": f"admin_block_{u.id}"},
             {"text": "✅ آنبلاک", "callback_data": f"admin_unblock_{u.id}"}],
        ]))

async def show_user_profile(bot, admin, target_user_id, db):
    u = db.query(User).filter(User.id == target_user_id).first()
    if not u:
        return
    total_paid = sum(p.amount for p in u.payments if p.status == PaymentStatus.approved)
    last_test = u.test_results[-1].test.title if u.test_results and u.test_results[-1].test else "ندارد"
    msg = (
        "👤 پروفایل کامل\n━━━━━━━━━━━━━\n"
        f"نام: {u.full_name}\nموبایل: {u.phone or 'ثبت نشده'}\n"
        f"وضعیت: {'✅ فعال' if u.status == UserStatus.active else '🚫 بلاک'}\n"
        "━━━━━━━━━━━━━\n"
        f"🧪 تست‌ها: {len(u.test_results)}\n"
        f"📅 رزروها: {len(u.reservations)}\n"
        f"💰 مجموع خرید: {total_paid:,} تومان\n"
        f"📅 عضویت: {u.created_at.strftime('%Y/%m/%d')}"
    )
    await send_message(bot, admin.bale_id, msg, reply_markup=inline_keyboard([
        [{"text": "💬 ارسال پیام مستقیم", "callback_data": f"admin_msg_user_{u.id}"}],
        [{"text": "🚫 بلاک", "callback_data": f"admin_block_{u.id}"},
         {"text": "✅ آنبلاک", "callback_data": f"admin_unblock_{u.id}"}],
    ]))

async def prompt_direct_message(bot, admin, target_user_id):
    set_state(admin.bale_id, {"step": "admin_direct_msg", "target_user_id": target_user_id})
    await send_message(bot, admin.bale_id, "✍️ پیام را بنویس:")

async def send_direct_message(bot, admin, text, db):
    state = get_state(admin.bale_id)
    target_id = state.get("target_user_id")
    clear_state(admin.bale_id)
    target = db.query(User).filter(User.id == target_id).first()
    if not target:
        return
    await send_message(bot, target.bale_id, f"📩 پیام از مدیریت:\n\n{text}")
    await send_message(bot, admin.bale_id, f"✅ پیام به {target.full_name} ارسال شد.")

async def prompt_broadcast(bot, admin):
    set_state(admin.bale_id, {"step": "admin_broadcast"})
    await send_message(bot, admin.bale_id, "📢 متن پیام انبوه را بنویس:")

async def send_broadcast(bot, admin, text, db):
    clear_state(admin.bale_id)
    users = db.query(User).filter(User.status == UserStatus.active).all()
    await send_message(bot, admin.bale_id, f"⏳ در حال ارسال به {len(users)} کاربر...")
    sent = failed = 0
    for u in users:
        try:
            await send_message(bot, u.bale_id, text)
            sent += 1
        except:
            failed += 1
    log = BroadcastMessage(title="پیام انبوه", text=text, sent_count=sent, failed_count=failed)
    db.add(log)
    db.commit()
    await send_message(bot, admin.bale_id, f"✅ ارسال تمام شد\n📤 موفق: {sent} | ❌ ناموفق: {failed}")

async def export_users_excel(bot, admin, db):
    try:
        import openpyxl
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        import io, tempfile, os
        from datetime import datetime as dt

        users = db.query(User).order_by(User.created_at).all()
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "users"
        ws.sheet_view.rightToLeft = True

        header_fill = PatternFill(start_color="2E86AB", end_color="2E86AB", fill_type="solid")
        header_font = Font(name="Arial", bold=True, color="FFFFFF", size=11)
        center = Alignment(horizontal="center", vertical="center")
        thin = Side(style="thin", color="CCCCCC")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)
        even_fill = PatternFill(start_color="F0F8FF", end_color="F0F8FF", fill_type="solid")

        headers = ["row", "name", "phone", "username", "date"]
        widths = [8, 30, 18, 20, 20]
        for col, (h, w) in enumerate(zip(headers, widths), 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center
            cell.border = border
            ws.column_dimensions[cell.column_letter].width = w
        ws.row_dimensions[1].height = 25

        for i, u in enumerate(users, 1):
            row = i + 1
            date_str = str(u.created_at)[:10] if u.created_at else "-"
            data = [i, u.full_name or "-", u.phone or "-",
                    f"@{u.username}" if u.username else "-", date_str]
            for col, val in enumerate(data, 1):
                cell = ws.cell(row=row, column=col, value=val)
                cell.font = Font(name="Arial", size=10)
                cell.alignment = center
                cell.border = border
                if i % 2 == 0:
                    cell.fill = even_fill
            ws.row_dimensions[row].height = 20

        ws.freeze_panes = "A2"
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp.write(buf.read())
            tmp_path = tmp.name

        await send_message(bot, admin.bale_id, f"در حال آماده سازی اکسل {len(users)} کاربر...")
        from bale import InputFile
        with open(tmp_path, "rb") as f:
            file_bytes = f.read()
        os.unlink(tmp_path)
        await bot.send_document(
            admin.bale_id,
            InputFile(file_bytes, file_name="users.xlsx"),
            caption=f"users: {len(users)}\ndate: {dt.now().strftime('%Y-%m-%d')}"
        )
    except ImportError:
        await send_message(bot, admin.bale_id, "openpyxl not installed")
    except Exception as e:
        await send_message(bot, admin.bale_id, f"error: {e}")

TYPE_LABELS = {
    "vip": "🟣 پکیج VIP", "individual": "standard",
    "individual2": "intro", "group": "group", "all": "all",
}

async def prompt_add_slot(bot, admin):
    set_state(admin.bale_id, {"step": "admin_slot_type"})
    await send_message(bot, admin.bale_id, "➕ نوع کوچینگ را انتخاب کن:", reply_markup=inline_keyboard([
        [{"text": "🟣 پکیج VIP", "callback_data": "admin_slottype_vip"}],
        [{"text": "🟢 پکیج استاندارد", "callback_data": "admin_slottype_individual"}],
        [{"text": "🔵 پکیج آشنایی", "callback_data": "admin_slottype_individual2"}],
        [{"text": "👥 پکیج گروهی", "callback_data": "admin_slottype_group"}],
        [{"text": "🌐 همه انواع", "callback_data": "admin_slottype_all"}],
    ]))

async def prompt_add_slot_datetime(bot, admin, slot_type):
    set_state(admin.bale_id, {"step": "admin_slot_pkg_title", "slot_type": slot_type})
    await send_message(bot, admin.bale_id, f"نوع: {slot_type}\nعنوان پکیج را بنویس:")

async def slot_set_pkg_title(bot, admin, text):
    state = get_state(admin.bale_id)
    set_state(admin.bale_id, {**state, "step": "admin_slot_pkg_sessions", "pkg_title": text})
    await send_message(bot, admin.bale_id, "تعداد جلسات:\n(مثال: 4)")

async def slot_set_pkg_sessions(bot, admin, text):
    state = get_state(admin.bale_id)
    try:
        sessions = int(text.strip())
        set_state(admin.bale_id, {**state, "step": "admin_slot_pkg_duration", "pkg_sessions": sessions})
        await send_message(bot, admin.bale_id, "مدت هر جلسه (دقیقه):\n(مثال: 60)")
    except:
        await send_message(bot, admin.bale_id, "عدد صحیح وارد کن.")

async def slot_set_pkg_duration(bot, admin, text):
    state = get_state(admin.bale_id)
    try:
        duration = int(text.strip())
        set_state(admin.bale_id, {**state, "step": "admin_slot_pkg_price", "pkg_duration": duration})
        await send_message(bot, admin.bale_id, "قیمت پکیج (تومان):\n(مثال: 4800000)")
    except:
        await send_message(bot, admin.bale_id, "عدد صحیح وارد کن.")

async def slot_set_pkg_price(bot, admin, text, db):
    state = get_state(admin.bale_id)
    try:
        price = int(text.replace(",", "").strip())
        set_state(admin.bale_id, {**state, "step": "admin_slot_pkg_capacity", "pkg_price": price})
        await send_message(bot, admin.bale_id, "ظرفیت پکیج (نفر):\n(مثال: 1)")
    except:
        await send_message(bot, admin.bale_id, "قیمت اشتباه بود.")

async def slot_set_pkg_capacity(bot, admin, text, db):
    state = get_state(admin.bale_id)
    try:
        capacity = int(text.strip())
        price = state["pkg_price"]
        count = db.query(CoachingPackage).count()
        pkg = CoachingPackage(
            title=state["pkg_title"], session_type=state.get("slot_type", "individual"),
            session_count=state["pkg_sessions"], session_duration=state["pkg_duration"],
            price=price, capacity=capacity, is_active=True, order=count,
        )
        db.add(pkg)
        db.commit()
        db.refresh(pkg)
        slot_type = state.get("slot_type", "individual")
        is_group = slot_type == "group"
        if price > 0:
            set_state(admin.bale_id, {**state, "pkg_id_new": pkg.id, "capacity": capacity,
                                       "pkg_id": pkg.id, "is_group": is_group})
            await prompt_installment_question(bot, admin, "package", pkg.id, price)
        else:
            if is_group:
                set_state(admin.bale_id, {
                    **state, "step": "admin_slot_datetime", "pkg_id": pkg.id,
                    "current_session": 1, "current_person": 1,
                    "collected_slots": [], "capacity": capacity,
                    "total_slots": state["pkg_sessions"],
                    "is_group": True,
                })
                await send_message(bot, admin.bale_id,
                    f"گروهی ساخته شد!\nجلسه 1 از {state['pkg_sessions']}\nفرمت: 1405/05/20 16:00")
            else:
                total_slots = state["pkg_sessions"] * capacity
                set_state(admin.bale_id, {
                    **state, "step": "admin_slot_datetime", "pkg_id": pkg.id,
                    "current_session": 1, "current_person": 1,
                    "collected_slots": [], "capacity": capacity,
                    "total_slots": total_slots,
                })
                await send_message(bot, admin.bale_id,
                    f"پکیج ساخته شد!\nنفر 1 از {capacity}\nجلسه 1 از {state['pkg_sessions']}\nفرمت: 1405/05/20 16:00")
    except:
        await send_message(bot, admin.bale_id, "عدد صحیح وارد کن.")

async def add_time_slot(bot, admin, text, db):
    import jdatetime
    state = get_state(admin.bale_id)
    pkg_id = state.get("pkg_id")
    sessions_per_person = state.get("pkg_sessions", 1)
    capacity = state.get("capacity", 1)
    current_session = state.get("current_session", 1)
    current_person = state.get("current_person", 1)
    collected_slots = state.get("collected_slots", [])
    total_slots = state.get("total_slots", sessions_per_person * capacity)
    try:
        jalali_dt = jdatetime.datetime.strptime(text.strip(), "%Y/%m/%d %H:%M")
        gregorian_dt = jalali_dt.togregorian()
        from datetime import timedelta as _td
        conflict = db.query(TimeSlot).filter(
            TimeSlot.date >= gregorian_dt - _td(minutes=30),
            TimeSlot.date <= gregorian_dt + _td(minutes=30),
        ).first()
        if conflict:
            _pkg = conflict.package.title if conflict.package else "نامشخص"
            await send_message(bot, admin.bale_id,
                f"این تاریخ برای پکیج {_pkg} ثبت شده. تاریخ دیگری وارد کن:")
            return
        slot = TimeSlot(date=gregorian_dt, is_available=True, package_id=pkg_id)
        db.add(slot)
        db.commit()
        db.refresh(slot)
        collected_slots.append({"session": current_session, "person": current_person, "date": text, "slot_id": slot.id})
        total_done = len(collected_slots)
        if total_done < total_slots:
            next_session = current_session + 1
            next_person = current_person
            if next_session > sessions_per_person:
                next_session = 1
                next_person = current_person + 1
            set_state(admin.bale_id, {
                **state,
                "current_session": next_session,
                "current_person": next_person,
                "collected_slots": collected_slots,
            })
            await send_message(bot, admin.bale_id,
                f"ثبت شد: نفر {current_person} — جلسه {current_session}: {text}\n"
                f"نفر {next_person} از {capacity} | جلسه {next_session} از {sessions_per_person}\n"
                f"فرمت: 1404/05/20 16:00")
        else:
            clear_state(admin.bale_id)
            await send_message(bot, admin.bale_id,
                f"پکیج کامل شد! {total_slots} تایم برای {capacity} نفر ثبت شد.",
                reply_markup=inline_keyboard([
                    [{"text": "مدیریت پکیج‌ها", "callback_data": "admin_packages"}],
                ]))
    except Exception as e:
        await send_message(bot, admin.bale_id, f"خطا: {e}\nمثال: 1404/05/20 16:00")

async def cancel_reservation(bot, admin, res_id, db):
    res = db.query(Reservation).filter(Reservation.id == res_id).first()
    if not res:
        return
    res.status = ReservationStatus.cancelled
    if res.time_slot:
        res.time_slot.is_available = True
    db.commit()
    await send_message(bot, admin.bale_id, "رزرو لغو شد.")

async def prompt_reschedule(bot, admin, res_id, db):
    set_state(admin.bale_id, {"step": "admin_reschedule_datetime", "res_id": res_id})
    await send_message(bot, admin.bale_id,
        "تاریخ و ساعت جدید را وارد کن:\nفرمت: 1405/05/20 16:00")

async def reschedule_reservation(bot, admin, new_slot_id, db):
    state = get_state(admin.bale_id)
    res_id = state.get("res_id")
    clear_state(admin.bale_id)
    res = db.query(Reservation).filter(Reservation.id == res_id).first()
    new_slot = db.query(TimeSlot).filter(TimeSlot.id == new_slot_id).first()
    if not res or not new_slot:
        return
    if res.time_slot:
        res.time_slot.is_available = True
    res.time_slot_id = new_slot.id
    res.status = ReservationStatus.rescheduled
    new_slot.is_available = False
    db.commit()
    new_date = new_slot.date.strftime("%Y/%m/%d — %H:%M")
    await send_message(bot, res.user.bale_id, f"جلسه شما جابجا شد!\n{new_date}")
    await send_message(bot, admin.bale_id, f"رزرو جابجا شد به {new_date}")

async def show_tests_management(bot, admin, db):
    tests = db.query(Test).order_by(Test.order).all()
    if not tests:
        await send_message(bot, admin.bale_id, "هیچ تستی ثبت نشده.", reply_markup=inline_keyboard([
            [{"text": "➕ افزودن تست جدید", "callback_data": "admin_new_test"}],
        ]))
        return
    buttons = [[{"text": f"{'✅' if t.is_active else '❌'} {t.title}", "callback_data": f"admin_test_menu_{t.id}"}] for t in tests]
    buttons.append([{"text": "➕ افزودن تست جدید", "callback_data": "admin_new_test"}])
    await send_message(bot, admin.bale_id, "🧪 مدیریت تست‌ها:", reply_markup=inline_keyboard(buttons))

async def show_test_menu(bot, admin, test_id, db):
    test = db.query(Test).filter(Test.id == test_id).first()
    if not test:
        return
    result_count = db.query(func.count(TestResult.id)).filter(TestResult.test_id == test_id).scalar()
    atype = getattr(test, 'analysis_type', 'numeric') or 'numeric'
    tone = getattr(test, 'tone', 'friendly') or 'friendly'
    atype_fa = {"numeric": "عددی", "typology": "تیپی", "combined": "ترکیبی"}.get(atype, atype)
    tone_fa = {"friendly": "😊 صمیمی", "formal": "🎩 رسمی"}.get(tone, tone)
    msg = (
        f"🧪 {test.title}\n━━━━━━━━━━━━━\n"
        f"{'رایگان' if test.is_free else f'{test.price:,} تومان'}\n"
        f"نوع تحلیل: {atype_fa} | لحن: {tone_fa}\n"
        f"{len(test.questions)} سوال | {result_count} بار انجام شده\n"
        f"وضعیت: {'✅ فعال' if test.is_active else '❌ غیرفعال'}"
    )
    await send_message(bot, admin.bale_id, msg, reply_markup=inline_keyboard([
        [{"text": "🔄 فعال/غیرفعال", "callback_data": f"admin_toggle_test_{test_id}"},
         {"text": "🗑 حذف تست", "callback_data": f"admin_confirm_delete_test_{test_id}"}],
        [{"text": "🔓 نوع دسترسی", "callback_data": f"admin_test_access_{test_id}"},
         {"text": "📝 محتوای تحلیلی", "callback_data": f"admin_test_content_{test_id}"}],
        [{"text": "🔢 تغییر ترتیب", "callback_data": f"admin_test_order_{test_id}"},
         {"text": "📊 ویرایش بازه‌ها", "callback_data": f"admin_test_ranges_{test_id}"}],
        [{"text": "📊 نتایج", "callback_data": f"admin_test_results_{test_id}"}],
        [{"text": "🔙 بازگشت", "callback_data": "admin_tests"}],
    ]))

async def confirm_delete_test(bot, admin, test_id, db):
    test = db.query(Test).filter(Test.id == test_id).first()
    if not test:
        return
    result_count = db.query(func.count(TestResult.id)).filter(TestResult.test_id == test_id).scalar()
    await send_message(bot, admin.bale_id,
        f"آیا مطمئنی؟\nتست {test.title} با {len(test.questions)} سوال و {result_count} نتیجه حذف می‌شود.",
        reply_markup=inline_keyboard([
            [{"text": "بله حذف کن", "callback_data": f"admin_delete_test_{test_id}"},
             {"text": "انصراف", "callback_data": f"admin_test_menu_{test_id}"}],
        ]))

async def prompt_new_test(bot, admin):
    set_state(admin.bale_id, {"step": "admin_new_test_type"})
    await send_message(bot, admin.bale_id,
        "تست جدید - مرحله 1\nنوع تحلیل را انتخاب کن:",
        reply_markup=inline_keyboard([
            [{"text": "🔢 عددی (جمع امتیاز)", "callback_data": "admin_test_atype_numeric"}],
            [{"text": "🔤 تیپی / حروفی", "callback_data": "admin_test_atype_typology"}],
            [{"text": "🔀 ترکیبی (امتیاز + تیپ)", "callback_data": "admin_test_atype_combined"}],
        ]))

async def set_new_test_type(bot, admin, atype):
    set_state(admin.bale_id, {"step": "admin_new_test_tone", "analysis_type": atype})
    labels = {"numeric": "عددی", "typology": "تیپی", "combined": "ترکیبی"}
    await send_message(bot, admin.bale_id,
        f"نوع: {labels.get(atype,'')}\nمرحله 2: لحن متن را انتخاب کن:",
        reply_markup=inline_keyboard([
            [{"text": "😊 صمیمی", "callback_data": "admin_test_tone_friendly"}],
            [{"text": "🎩 رسمی", "callback_data": "admin_test_tone_formal"}],
        ]))

async def set_new_test_tone(bot, admin, tone):
    state = get_state(admin.bale_id)
    set_state(admin.bale_id, {**state, "step": "admin_new_test", "tone": tone})
    await send_message(bot, admin.bale_id, "مرحله 3: عنوان تست را بنویس:")

async def create_new_test(bot, admin, title, db):
    state = get_state(admin.bale_id)
    set_state(admin.bale_id, {**state, "step": "admin_test_importance", "test_title": title})
    await send_message(bot, admin.bale_id,
        f"عنوان: {title}\n"
        "اهمیت این تست را بنویس:\n"
        "(این متن قبل از شروع تست به کاربر نشون داده میشه)\n"
        "(برای رد: /skip)")

async def save_test_importance(bot, admin, importance, db):
    state = get_state(admin.bale_id)
    analysis_type = state.get("analysis_type", "numeric")
    tone = state.get("tone", "friendly")
    title = state.get("test_title", "")
    imp = None if importance.strip() == "/skip" else importance.strip()
    test = Test(title=title, is_free=True, is_active=False,
                analysis_type=analysis_type, tone=tone)
    db.add(test)
    db.commit()
    db.refresh(test)
    if imp:
        from sqlalchemy import text as sqlt
        try:
            db.execute(sqlt("UPDATE tests SET importance=:v WHERE id=:id"), {"v": imp, "id": test.id})
            db.commit()
        except: pass
    set_state(admin.bale_id, {"step": "admin_add_question", "test_id": test.id, "q_index": 1})
    await send_message(bot, admin.bale_id,
        f"تست {title} ساخته شد.\nسوال 1 را بنویس:\n(وقتی تمام شد /done بزن)")

async def add_question(bot, admin, text, db):
    state = get_state(admin.bale_id)
    test_id = state.get("test_id")
    if not test_id:
        await send_message(bot, admin.bale_id, "خطا: تست پیدا نشد.")
        clear_state(admin.bale_id)
        return
    if text == "/done":
        test = db.query(Test).filter(Test.id == test_id).first()
        set_state(admin.bale_id, {"step": "admin_add_score_range", "test_id": test_id, "range_index": 1})
        await send_message(bot, admin.bale_id,
            f"{len(test.questions)} سوال ذخیره شد.\n\nحالا بازه‌های امتیاز را وارد کن:\n"
            "فرمت: حداقل | حداکثر | عنوان | متن تحلیل\n\n"
            "مثال:\n0 | 10 | سطح پایین | نیاز به تقویت دارید\n"
            "10 | 20 | سطح متوسط | عملکرد قابل قبول است\n\n"
            "وقتی تمام شد /done بزن")
        return
    q = Question(test_id=test_id, text=text, order=state.get("q_index", 1)-1)
    db.add(q)
    db.commit()
    db.refresh(q)
    set_state(admin.bale_id, {**state, "step": "admin_add_question_analysis", "question_id": q.id})
    await send_message(bot, admin.bale_id,
        "سوال ذخیره شد.\nتحلیل این سوال را بنویس:\n(برای رد کردن /skip بزن)")

async def save_question_analysis(bot, admin, text, db):
    state = get_state(admin.bale_id)
    question_id = state.get("question_id")
    if question_id and text != "/skip":
        q = db.query(Question).filter(Question.id == question_id).first()
        if q:
            q.analysis = text
            db.commit()
    set_state(admin.bale_id, {**state, "step": "admin_add_options", "opt_index": 1})
    await send_message(bot, admin.bale_id,
        "گزینه‌ها را وارد کن:\n"
        "عددی: متن | امتیاز\n"
        "تیپی: متن | تیپ\n"
        "ترکیبی: متن | امتیاز | تیپ\n\n"
        "وقتی تمام شد /next بزن")

async def add_option(bot, admin, text, db):
    state = get_state(admin.bale_id)
    if text == "/next":
        q_index = state["q_index"] + 1
        set_state(admin.bale_id, {**state, "step": "admin_add_question", "q_index": q_index})
        await send_message(bot, admin.bale_id,
            f"سوال {q_index} را بنویس:\n(وقتی تمام شد /done بزن)")
        return
    try:
        parts = [p.strip() for p in text.split("|")]
        opt_text = parts[0]
        score = 0.0
        type_label = None
        if len(parts) >= 2:
            try:
                score = float(parts[1])
            except:
                type_label = parts[1]
        if len(parts) >= 3:
            type_label = parts[2]
        opt = Option(question_id=state["question_id"], text=opt_text,
                     score=score, type_label=type_label, order=state["opt_index"]-1)
        db.add(opt)
        db.commit()
        set_state(admin.bale_id, {**state, "opt_index": state["opt_index"] + 1})
        label_info = f" | تیپ: {type_label}" if type_label else ""
        await send_message(bot, admin.bale_id,
            f"گزینه اضافه شد: {opt_text} (امتیاز: {score}{label_info})\nگزینه بعدی یا /next")
    except:
        await send_message(bot, admin.bale_id, "فرمت اشتباه.")

async def add_score_range(bot, admin, text, db):
    state = get_state(admin.bale_id)
    test_id = state.get("test_id")
    if text == "/done":
        clear_state(admin.bale_id)
        test = db.query(Test).filter(Test.id == test_id).first()
        count = db.query(ScoreRange).filter(ScoreRange.test_id == test_id).count()
        await send_message(bot, admin.bale_id,
            f"تست {test.title} با {len(test.questions)} سوال و {count} بازه ذخیره شد.",
            reply_markup=inline_keyboard([
                [{"text": "🔄 فعال کردن تست", "callback_data": f"admin_toggle_test_{test_id}"}],
                [{"text": "🔙 مدیریت تست‌ها", "callback_data": "admin_tests"}],
            ]))
        return
    try:
        parts = [p.strip() for p in text.split("|")]
        if len(parts) < 4:
            raise ValueError("فرمت ناقص")
        min_score = float(parts[0])
        max_score = float(parts[1])
        title = parts[2]
        analysis = "|".join(parts[3:]).strip()
        sr = ScoreRange(test_id=test_id, min_score=min_score, max_score=max_score,
                        title=title, analysis=analysis)
        db.add(sr)
        db.commit()
        idx = state.get("range_index", 1)
        set_state(admin.bale_id, {**state, "range_index": idx + 1})
        await send_message(bot, admin.bale_id,
            f"بازه {idx}: {min_score} تا {max_score} - {title}\nبازه بعدی یا /done")
    except Exception as e:
        await send_message(bot, admin.bale_id,
            f"فرمت اشتباه: {e}\nمثال: 0 | 10 | سطح پایین | متن تحلیل")

async def toggle_test(bot, admin, test_id, db):
    test = db.query(Test).filter(Test.id == test_id).first()
    if not test:
        return
    test.is_active = not test.is_active
    db.commit()
    await send_message(bot, admin.bale_id, f"تست {'فعال' if test.is_active else 'غیرفعال'} شد.")

async def delete_test(bot, admin, test_id, db):
    test = db.query(Test).filter(Test.id == test_id).first()
    if not test:
        return
    title = test.title
    db.delete(test)
    db.commit()
    await send_message(bot, admin.bale_id, f"تست {title} حذف شد.", reply_markup=inline_keyboard([
        [{"text": "🔙 مدیریت تست‌ها", "callback_data": "admin_tests"}],
    ]))

async def show_products_management(bot, admin, db):
    products = db.query(Product).order_by(Product.order).all()
    buttons = [[{"text": f"{'✅' if p.is_active else '❌'} {p.title}", "callback_data": f"admin_product_menu_{p.id}"}] for p in products]
    buttons.append([{"text": "➕ افزودن محصول", "callback_data": "admin_new_product"}])
    await send_message(bot, admin.bale_id, "🛍 مدیریت محصولات:", reply_markup=inline_keyboard(buttons))

async def show_product_menu(bot, admin, product_id, db):
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        return
    msg = (
        f"{p.title}\n━━━━━━━━━━━━━\n"
        f"{'رایگان' if p.price == 0 else f'{p.price:,} تومان'}\n"
        f"{'🔗 ' + p.link if p.link else ''}\n"
        f"وضعیت: {'✅ فعال' if p.is_active else '❌ غیرفعال'}"
    )
    await send_message(bot, admin.bale_id, msg, reply_markup=inline_keyboard([
        [{"text": "🔄 فعال/غیرفعال", "callback_data": f"admin_toggle_product_{product_id}"},
         {"text": "🗑 حذف محصول", "callback_data": f"admin_delete_product_{product_id}"}],
        [{"text": "🔙 بازگشت", "callback_data": "admin_products"}],
    ]))

async def toggle_product(bot, admin, product_id, db):
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        return
    p.is_active = not p.is_active
    db.commit()
    await send_message(bot, admin.bale_id, f"محصول {'فعال' if p.is_active else 'غیرفعال'} شد.")

async def delete_product(bot, admin, product_id, db):
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        return
    title = p.title
    db.delete(p)
    db.commit()
    await send_message(bot, admin.bale_id, f"محصول {title} حذف شد.", reply_markup=inline_keyboard([
        [{"text": "🔙 مدیریت محصولات", "callback_data": "admin_products"}],
    ]))

async def prompt_new_product(bot, admin):
    set_state(admin.bale_id, {"step": "admin_new_product_type"})
    await send_message(bot, admin.bale_id, "نوع محصول:", reply_markup=inline_keyboard([
        [{"text": "🎓 دوره", "callback_data": "admin_ptype_course"},
         {"text": "🎧 پادکست", "callback_data": "admin_ptype_podcast"}],
        [{"text": "📡 وبینار", "callback_data": "admin_ptype_webinar"},
         {"text": "📢 کانال", "callback_data": "admin_ptype_channel"}],
    ]))

async def set_product_type(bot, admin, ptype):
    set_state(admin.bale_id, {"step": "admin_new_product_title", "ptype": ptype})
    await send_message(bot, admin.bale_id, "عنوان محصول:")

async def set_product_title(bot, admin, title):
    state = get_state(admin.bale_id)
    set_state(admin.bale_id, {**state, "step": "admin_new_product_price", "title": title})
    await send_message(bot, admin.bale_id, "قیمت (تومان):\n(برای رایگان: 0)")

async def set_product_price(bot, admin, price_text, db):
    state = get_state(admin.bale_id)
    try:
        price = int(price_text.replace(",", ""))
        set_state(admin.bale_id, {**state, "step": "admin_new_product_capacity", "price": price})
        await send_message(bot, admin.bale_id, "ظرفیت:\n(برای نامحدود: 0)")
    except:
        await send_message(bot, admin.bale_id, "قیمت اشتباه بود.")

async def set_product_capacity(bot, admin, cap_text, db):
    state = get_state(admin.bale_id)
    try:
        capacity = int(cap_text.strip())
        product = Product(title=state["title"], type=ProductType(state["ptype"]),
                          price=state["price"], capacity=capacity, is_active=True)
        db.add(product)
        db.commit()
        db.refresh(product)
        if state.get("price", 0) > 0:
            await prompt_installment_question(bot, admin, "product", product.id, state.get("price", 0))
        else:
            set_state(admin.bale_id, {"step": "admin_product_link", "product_id": product.id})
            await send_message(bot, admin.bale_id, "لینک یا توضیح:\n(برای رد: /skip)")
    except:
        await send_message(bot, admin.bale_id, "عدد اشتباه بود.")

async def set_product_link(bot, admin, text, db):
    state = get_state(admin.bale_id)
    clear_state(admin.bale_id)
    if text != "/skip":
        product = db.query(Product).filter(Product.id == state["product_id"]).first()
        if product:
            product.link = text
            db.commit()
    await send_message(bot, admin.bale_id, "محصول در دسترس کاربران است.", reply_markup=inline_keyboard([
        [{"text": "🔙 مدیریت محصولات", "callback_data": "admin_products"}],
    ]))

async def show_pending_reviews(bot, admin, db):
    from models.review import Review
    reviews = db.query(Review).filter(Review.is_approved == False).limit(5).all()
    if not reviews:
        await send_message(bot, admin.bale_id, "نظر در انتظاری وجود ندارد.")
        return
    for r in reviews:
        subject = r.test.title if r.test else (r.product.title if r.product else "نامشخص")
        msg = f"⭐ {r.score}/5\n👤 {r.user.full_name}\n📌 {subject}\n💬 {r.text or 'بدون متن'}"
        await send_message(bot, admin.bale_id, msg, reply_markup=inline_keyboard([
            [{"text": "تأیید", "callback_data": f"admin_approve_review_{r.id}"},
             {"text": "رد", "callback_data": f"admin_reject_review_{r.id}"}],
        ]))

async def approve_review(bot, admin, review_id, db):
    from models.review import Review
    r = db.query(Review).filter(Review.id == review_id).first()
    if r:
        r.is_approved = True
        r.allow_publish = True
        db.commit()
    await send_message(bot, admin.bale_id, "نظر منتشر شد.")

async def reject_review(bot, admin, review_id, db):
    from models.review import Review
    r = db.query(Review).filter(Review.id == review_id).first()
    if r:
        db.delete(r)
        db.commit()
    await send_message(bot, admin.bale_id, "نظر حذف شد.")

async def show_financial_report(bot, admin, db):
    today = datetime.now()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    def income(since=None):
        q = db.query(func.sum(Payment.amount)).filter(Payment.status == PaymentStatus.approved)
        if since:
            q = q.filter(Payment.updated_at >= since)
        return q.scalar() or 0
    msg = (
        "گزارش مالی\n━━━━━━━━━━━━━\n"
        f"امروز: {income(today.replace(hour=0,minute=0)):,} تومان\n"
        f"این هفته: {income(week_ago):,} تومان\n"
        f"این ماه: {income(month_ago):,} تومان\n"
        f"━━━━━━━━━━━━━\nکل: {income():,} تومان"
    )
    await send_message(bot, admin.bale_id, msg)

async def show_settings(bot, admin, db):
    card_info = ""
    if bot_settings.get("card_number"):
        card_info = f"\nشماره کارت: {bot_settings['card_number']}"
        if bot_settings.get("card_owner"):
            card_info += f"\nبه نام: {bot_settings['card_owner']}"
    await send_message(bot, admin.bale_id, f"تنظیمات ربات:{card_info}", reply_markup=inline_keyboard([
        [{"text": "✏️ ویرایش پیام خوش‌آمدگویی", "callback_data": "admin_edit_welcome"}],
        [{"text": "💳 ویرایش شماره کارت", "callback_data": "admin_edit_card"}],
        [{"text": "👤 ویرایش نام صاحب کارت", "callback_data": "admin_edit_card_owner"}],
        [{"text": "📢 تنظیم کانال اجباری", "callback_data": "admin_edit_channel"}],
    ]))

async def prompt_edit_welcome(bot, admin):
    set_state(admin.bale_id, {"step": "admin_edit_welcome"})
    await send_message(bot, admin.bale_id,
        f"پیام فعلی:\n\n{bot_settings.get('welcome_message','')}\n\nپیام جدید را بنویس:")

async def save_welcome_message(bot, admin, text):
    clear_state(admin.bale_id)
    bot_settings["welcome_message"] = text
    await send_message(bot, admin.bale_id, "پیام ذخیره شد.", reply_markup=inline_keyboard([
        [{"text": "🎟 کدهای تخفیف", "callback_data": "admin_discounts"},
         {"text": "⚙️ تنظیمات", "callback_data": "admin_settings"}],
    ]))

async def prompt_edit_card(bot, admin):
    set_state(admin.bale_id, {"step": "admin_edit_card"})
    await send_message(bot, admin.bale_id,
        f"کارت فعلی: {bot_settings.get('card_number','ثبت نشده')}\nشماره کارت جدید:")

async def save_card_number(bot, admin, text):
    clear_state(admin.bale_id)
    bot_settings["card_number"] = text.strip()
    await send_message(bot, admin.bale_id, f"کارت ذخیره شد.", reply_markup=inline_keyboard([
        [{"text": "🎟 کدهای تخفیف", "callback_data": "admin_discounts"},
         {"text": "⚙️ تنظیمات", "callback_data": "admin_settings"}],
    ]))

async def prompt_edit_card_owner(bot, admin):
    set_state(admin.bale_id, {"step": "admin_edit_card_owner"})
    await send_message(bot, admin.bale_id,
        f"نام فعلی: {bot_settings.get('card_owner','ثبت نشده')}\nنام جدید:")

async def save_card_owner(bot, admin, text):
    clear_state(admin.bale_id)
    bot_settings["card_owner"] = text.strip()
    await send_message(bot, admin.bale_id, f"نام ذخیره شد.", reply_markup=inline_keyboard([
        [{"text": "🎟 کدهای تخفیف", "callback_data": "admin_discounts"},
         {"text": "⚙️ تنظیمات", "callback_data": "admin_settings"}],
    ]))

async def show_packages_management(bot, admin, db):
    packages = db.query(CoachingPackage).order_by(CoachingPackage.order).all()
    buttons = [[{"text": f"{'✅' if p.is_active else '❌'} {p.title}", "callback_data": f"admin_pkg_menu_{p.id}"}] for p in packages]
    buttons.append([{"text": "➕ افزودن پکیج جدید", "callback_data": "admin_new_package"}])
    await send_message(bot, admin.bale_id, "📦 مدیریت پکیج‌های کوچینگ:", reply_markup=inline_keyboard(buttons))

async def show_package_menu(bot, admin, pkg_id, db):
    p = db.query(CoachingPackage).filter(CoachingPackage.id == pkg_id).first()
    if not p:
        return
    msg = (
        f"{p.title}\n━━━━━━━━━━━━━\n"
        f"{p.session_count} جلسه - {p.session_duration} دقیقه\n"
        f"{p.price:,} تومان\n"
        f"وضعیت: {'✅ فعال' if p.is_active else '❌ غیرفعال'}"
    )
    await send_message(bot, admin.bale_id, msg, reply_markup=inline_keyboard([
        [{"text": "🔄 فعال/غیرفعال", "callback_data": f"admin_toggle_pkg_{pkg_id}"},
         {"text": "🗑 حذف", "callback_data": f"admin_delete_pkg_{pkg_id}"}],
        [{"text": "🔙 بازگشت", "callback_data": "admin_packages"}],
    ]))

async def toggle_package(bot, admin, pkg_id, db):
    p = db.query(CoachingPackage).filter(CoachingPackage.id == pkg_id).first()
    if p:
        p.is_active = not p.is_active
        db.commit()
        await send_message(bot, admin.bale_id, f"پکیج {'فعال' if p.is_active else 'غیرفعال'} شد.")

async def delete_package(bot, admin, pkg_id, db):
    p = db.query(CoachingPackage).filter(CoachingPackage.id == pkg_id).first()
    if p:
        title = p.title
        # حذف پلن‌های اقساط
        from models.installment import InstallmentPlan, Installment
        plans = db.query(InstallmentPlan).filter(InstallmentPlan.package_id == pkg_id).all()
        for plan in plans:
            db.query(Installment).filter(Installment.plan_id == plan.id).delete()
            db.delete(plan)
        db.commit()
        db.delete(p)
        db.commit()
        await send_message(bot, admin.bale_id, f"پکیج {title} حذف شد.")

async def prompt_new_package(bot, admin):
    set_state(admin.bale_id, {"step": "admin_new_package_title"})
    await send_message(bot, admin.bale_id, "عنوان پکیج جدید:")

async def set_package_title(bot, admin, text):
    state = get_state(admin.bale_id)
    set_state(admin.bale_id, {**state, "step": "admin_new_package_sessions", "pkg_title": text})
    await send_message(bot, admin.bale_id, "تعداد جلسات:")

async def set_package_sessions(bot, admin, text):
    state = get_state(admin.bale_id)
    try:
        sessions = int(text)
        set_state(admin.bale_id, {**state, "step": "admin_new_package_duration", "pkg_sessions": sessions})
        await send_message(bot, admin.bale_id, "مدت هر جلسه (دقیقه):")
    except:
        await send_message(bot, admin.bale_id, "عدد وارد کن.")

async def set_package_duration(bot, admin, text):
    state = get_state(admin.bale_id)
    try:
        duration = int(text)
        set_state(admin.bale_id, {**state, "step": "admin_new_package_price", "pkg_duration": duration})
        await send_message(bot, admin.bale_id, "قیمت کل (تومان):")
    except:
        await send_message(bot, admin.bale_id, "عدد وارد کن.")

async def set_package_price(bot, admin, text, db):
    state = get_state(admin.bale_id)
    try:
        price = int(text.replace(",", ""))
        count = db.query(CoachingPackage).count()
        pkg = CoachingPackage(title=state["pkg_title"], session_count=state["pkg_sessions"],
                              session_duration=state["pkg_duration"], price=price,
                              is_active=True, order=count)
        db.add(pkg)
        db.commit()
        db.refresh(pkg)
        set_state(admin.bale_id, {**state, "pkg_id_new": pkg.id})
        if price > 0:
            await prompt_installment_question(bot, admin, "package", pkg.id, price)
        else:
            clear_state(admin.bale_id)
            await send_message(bot, admin.bale_id, "پکیج ساخته شد!", reply_markup=inline_keyboard([
                [{"text": "مدیریت پکیج‌ها", "callback_data": "admin_packages"}],
            ]))
    except:
        await send_message(bot, admin.bale_id, "قیمت اشتباه بود.")

CONTENT_TYPE_LABELS = {"review": "⭐ رضایت مشتریان", "intro": "👤 معرفی من", "faq": "❓ سوالات متداول"}
MEDIA_TYPE_LABELS = {
    "text": "📝 متن", "photo": "🖼 عکس", "video": "🎬 ویدیو",
    "voice": "صدا", "audio": "🎧 فایل صوتی", "document": "فایل", "link": "🔗 لینک"
}

async def show_static_content_menu(bot, admin, db):
    await send_message(bot, admin.bale_id, "📋 مدیریت محتوای صفحات:", reply_markup=inline_keyboard([
        [{"text": "⭐ رضایت مشتریان", "callback_data": "admin_sc_list_review"},
         {"text": "👤 معرفی من", "callback_data": "admin_sc_list_intro"}],
        [{"text": "❓ سوالات متداول", "callback_data": "admin_sc_list_faq"}],
        [{"text": "🔙 بازگشت", "callback_data": "admin_dashboard"}],
    ]))

async def show_sc_list(bot, admin, ctype, db):
    items = db.query(StaticContent).filter(StaticContent.content_type == ctype).order_by(StaticContent.order).all()
    label = CONTENT_TYPE_LABELS.get(ctype, ctype)
    buttons = []
    for item in items:
        preview = item.question or item.text or item.link_url or f"آیتم {item.id}"
        preview = (preview[:28] + "...") if len(preview) > 28 else preview
        status = "✅" if item.is_active else "❌"
        mtype = MEDIA_TYPE_LABELS.get(item.media_type, "")
        buttons.append([{"text": f"{status} {mtype} - {preview}", "callback_data": f"admin_sc_item_{item.id}"}])
    buttons.append([{"text": "➕ افزودن", "callback_data": f"admin_sc_add_{ctype}"}])
    buttons.append([{"text": "🔙 بازگشت", "callback_data": "admin_static_content"}])
    await send_message(bot, admin.bale_id, f"{label} - {len(items)} آیتم:", reply_markup=inline_keyboard(buttons))

async def show_sc_item(bot, admin, item_id, db):
    item = db.query(StaticContent).filter(StaticContent.id == item_id).first()
    if not item:
        return
    label = CONTENT_TYPE_LABELS.get(item.content_type, "")
    mtype = MEDIA_TYPE_LABELS.get(item.media_type, "")
    preview = item.question or item.text or item.link_url or "-"
    preview = (preview[:50] + "...") if len(preview) > 50 else preview
    msg = f"{label} - {mtype}\n{preview}\nوضعیت: {'✅ فعال' if item.is_active else '❌ غیرفعال'}"
    await send_message(bot, admin.bale_id, msg, reply_markup=inline_keyboard([
        [{"text": "🔄 فعال/غیرفعال", "callback_data": f"admin_sc_toggle_{item_id}"},
         {"text": "🗑 حذف", "callback_data": f"admin_sc_delete_{item_id}"}],
        [{"text": "🔙 بازگشت", "callback_data": f"admin_sc_list_{item.content_type}"}],
    ]))

async def toggle_sc_item(bot, admin, item_id, db):
    item = db.query(StaticContent).filter(StaticContent.id == item_id).first()
    if item:
        item.is_active = not item.is_active
        db.commit()
        await send_message(bot, admin.bale_id, f"{'فعال' if item.is_active else 'غیرفعال'} شد.")

async def delete_sc_item(bot, admin, item_id, db):
    item = db.query(StaticContent).filter(StaticContent.id == item_id).first()
    if item:
        ctype = item.content_type
        db.delete(item)
        db.commit()
        await send_message(bot, admin.bale_id, "حذف شد.", reply_markup=inline_keyboard([
            [{"text": "🔙 بازگشت", "callback_data": f"admin_sc_list_{ctype}"}],
        ]))

async def prompt_add_sc(bot, admin, ctype):
    label = CONTENT_TYPE_LABELS.get(ctype, ctype)
    set_state(admin.bale_id, {"step": "admin_sc_choose_media", "sc_ctype": ctype})
    await send_message(bot, admin.bale_id,
        f"افزودن به {label}\nنوع محتوا را انتخاب کن:",
        reply_markup=inline_keyboard([
            [{"text": "📝 متن", "callback_data": "admin_sc_media_text"},
             {"text": "🔗 لینک", "callback_data": "admin_sc_media_link"}],
            [{"text": "🖼 عکس", "callback_data": "admin_sc_media_photo"},
             {"text": "🎬 ویدیو", "callback_data": "admin_sc_media_video"}],
            [{"text": "🎤 صدا (voice)", "callback_data": "admin_sc_media_voice"},
             {"text": "🎧 فایل صوتی", "callback_data": "admin_sc_media_audio"}],
            [{"text": "📎 فایل / سند", "callback_data": "admin_sc_media_document"}],
        ]))

async def sc_set_media_type(bot, admin, mtype):
    state = get_state(admin.bale_id)
    ctype = state.get("sc_ctype", "review")
    if ctype == "faq":
        set_state(admin.bale_id, {**state, "step": "admin_sc_faq_question", "sc_mtype": mtype})
        await send_message(bot, admin.bale_id, "متن سوال را بنویس:")
    elif mtype == "text":
        set_state(admin.bale_id, {**state, "step": "admin_sc_text_input", "sc_mtype": mtype})
        await send_message(bot, admin.bale_id, "متن را بنویس:")
    elif mtype == "link":
        set_state(admin.bale_id, {**state, "step": "admin_sc_link_url", "sc_mtype": mtype})
        await send_message(bot, admin.bale_id, "لینک را وارد کن:")
    else:
        set_state(admin.bale_id, {**state, "step": "admin_sc_await_file", "sc_mtype": mtype})
        hint = {"photo": "🖼 عکس", "video": "🎬 ویدیو", "voice": "پیام صوتی",
                "audio": "🎧 فایل صوتی", "document": "فایل"}.get(mtype, "فایل")
        await send_message(bot, admin.bale_id, f"{hint} را بفرست:")

async def sc_save_text(bot, admin, text, db):
    state = get_state(admin.bale_id)
    clear_state(admin.bale_id)
    ctype = state.get("sc_ctype")
    count = db.query(StaticContent).filter(StaticContent.content_type == ctype).count()
    db.add(StaticContent(content_type=ctype, media_type="text", text=text, is_active=True, order=count))
    db.commit()
    await send_message(bot, admin.bale_id, "ثبت شد.", reply_markup=inline_keyboard([
        [{"text": "🔙 بازگشت", "callback_data": f"admin_sc_list_{ctype}"}],
    ]))

async def sc_save_faq_question(bot, admin, text):
    state = get_state(admin.bale_id)
    set_state(admin.bale_id, {**state, "step": "admin_sc_faq_answer", "sc_question": text})
    await send_message(bot, admin.bale_id, "جواب این سوال را بنویس:")

async def sc_save_faq_answer(bot, admin, text, db):
    state = get_state(admin.bale_id)
    clear_state(admin.bale_id)
    count = db.query(StaticContent).filter(StaticContent.content_type == "faq").count()
    db.add(StaticContent(content_type="faq", media_type="text",
                         question=state.get("sc_question"), text=text, is_active=True, order=count))
    db.commit()
    await send_message(bot, admin.bale_id, "سوال و جواب ثبت شد.", reply_markup=inline_keyboard([
        [{"text": "🔙 بازگشت", "callback_data": "admin_sc_list_faq"}],
    ]))

async def sc_save_link_url(bot, admin, url):
    state = get_state(admin.bale_id)
    set_state(admin.bale_id, {**state, "step": "admin_sc_link_label", "sc_link_url": url})
    await send_message(bot, admin.bale_id, "لیبل دکمه را بنویس:")

async def sc_save_link(bot, admin, label, db):
    state = get_state(admin.bale_id)
    clear_state(admin.bale_id)
    ctype = state.get("sc_ctype")
    count = db.query(StaticContent).filter(StaticContent.content_type == ctype).count()
    db.add(StaticContent(content_type=ctype, media_type="link",
                         link_url=state.get("sc_link_url"), link_label=label, is_active=True, order=count))
    db.commit()
    await send_message(bot, admin.bale_id, "لینک ثبت شد.", reply_markup=inline_keyboard([
        [{"text": "🔙 بازگشت", "callback_data": f"admin_sc_list_{ctype}"}],
    ]))

async def sc_save_file(bot, admin, file_id, caption, db):
    state = get_state(admin.bale_id)
    clear_state(admin.bale_id)
    ctype = state.get("sc_ctype")
    mtype = state.get("sc_mtype", "document")
    count = db.query(StaticContent).filter(StaticContent.content_type == ctype).count()
    db.add(StaticContent(content_type=ctype, media_type=mtype, file_id=file_id,
                         text=caption or None, is_active=True, order=count))
    db.commit()
    label = CONTENT_TYPE_LABELS.get(ctype, "")
    await send_message(bot, admin.bale_id, f"فایل به {label} اضافه شد.", reply_markup=inline_keyboard([
        [{"text": "🔙 بازگشت", "callback_data": f"admin_sc_list_{ctype}"}],
    ]))

async def show_discounts(bot, admin, db):
    codes = db.query(DiscountCode).order_by(DiscountCode.created_at.desc()).all()
    buttons = []
    for c in codes:
        status = "✅" if c.is_active else "❌"
        uses = f"{c.used_count}" + (f"/{c.max_uses}" if c.max_uses > 0 else "")
        buttons.append([{"text": f"{status} {c.code} — {c.amount:,} تومان | {uses} بار", "callback_data": f"admin_discount_{c.id}"}])
    buttons.append([{"text": "➕ کد جدید", "callback_data": "admin_new_discount"}])
    await send_message(bot, admin.bale_id, f"🎟 کدهای تخفیف ({len(codes)} کد):", reply_markup=inline_keyboard(buttons))

async def prompt_new_discount(bot, admin):
    set_state(admin.bale_id, {"step": "admin_discount_code"})
    await send_message(bot, admin.bale_id, "کد تخفیف را بنویس:\n(مثال: SPRING10)")

async def discount_set_code(bot, admin, text):
    state = get_state(admin.bale_id)
    set_state(admin.bale_id, {**state, "step": "admin_discount_amount", "disc_code": text.strip().upper()})
    await send_message(bot, admin.bale_id, "مبلغ تخفیف (تومان):\n(مثال: 100000)")

async def discount_set_amount(bot, admin, text):
    state = get_state(admin.bale_id)
    try:
        amount = int(text.replace(",", ""))
        set_state(admin.bale_id, {**state, "step": "admin_discount_maxuses", "disc_amount": amount})
        await send_message(bot, admin.bale_id, "حداکثر تعداد استفاده:\n(0 برای نامحدود)")
    except:
        await send_message(bot, admin.bale_id, "عدد وارد کن.")

async def discount_set_maxuses(bot, admin, text, db):
    state = get_state(admin.bale_id)
    clear_state(admin.bale_id)
    try:
        max_uses = int(text.strip())
        dc = DiscountCode(code=state["disc_code"], amount=state["disc_amount"], max_uses=max_uses)
        db.add(dc)
        db.commit()
        await send_message(bot, admin.bale_id,
            f"✅ کد {state['disc_code']} با تخفیف {state['disc_amount']:,} تومان ساخته شد.",
            reply_markup=inline_keyboard([[{"text": "🔙 کدهای تخفیف", "callback_data": "admin_discounts"}]]))
    except Exception as e:
        await send_message(bot, admin.bale_id, f"خطا: {e}")

async def show_discount_item(bot, admin, dc_id, db):
    dc = db.query(DiscountCode).filter(DiscountCode.id == dc_id).first()
    if not dc:
        return
    uses = f"{dc.used_count}" + (f" از {dc.max_uses}" if dc.max_uses > 0 else " (نامحدود)")
    msg = (f"🎟 {dc.code}\n━━━━━━━━━━━━━\n"
           f"💰 تخفیف: {dc.amount:,} تومان\n"
           f"📊 استفاده: {uses}\n"
           f"وضعیت: {'✅ فعال' if dc.is_active else '❌ غیرفعال'}")
    await send_message(bot, admin.bale_id, msg, reply_markup=inline_keyboard([
        [{"text": "🔄 فعال/غیرفعال", "callback_data": f"admin_toggle_discount_{dc_id}"},
         {"text": "🗑 حذف", "callback_data": f"admin_delete_discount_{dc_id}"}],
        [{"text": "🔙 بازگشت", "callback_data": "admin_discounts"}],
    ]))

async def toggle_discount(bot, admin, dc_id, db):
    dc = db.query(DiscountCode).filter(DiscountCode.id == dc_id).first()
    if dc:
        dc.is_active = not dc.is_active
        db.commit()
        await send_message(bot, admin.bale_id, f"{'✅ فعال' if dc.is_active else '❌ غیرفعال'} شد.")

async def delete_discount(bot, admin, dc_id, db):
    dc = db.query(DiscountCode).filter(DiscountCode.id == dc_id).first()
    if dc:
        db.delete(dc)
        db.commit()
        await send_message(bot, admin.bale_id, "🗑 کد حذف شد.", reply_markup=inline_keyboard([
            [{"text": "🔙 کدهای تخفیف", "callback_data": "admin_discounts"}],
        ]))

async def prompt_reject_payment(bot, admin, payment_id):
    from bot.handlers.payment import prompt_reject_reason
    await prompt_reject_reason(bot, admin.bale_id, payment_id)

async def prompt_installment_setup(bot, admin, entity_type, entity_id, price):
    """شروع تنظیم اقساط برای محصول/پکیج"""
    set_state(admin.bale_id, {
        "step": "admin_installment_first",
        "inst_type": entity_type,
        "inst_id": entity_id,
        "inst_price": price,
    })
    await send_message(bot, admin.bale_id,
        f"اقساط برای این آیتم\nمبلغ کل: {price:,} تومان\n\nمبلغ پرداخت اولیه (تومان):")

async def installment_set_first(bot, admin, text):
    state = get_state(admin.bale_id)
    try:
        first = int(text.replace(",", ""))
        set_state(admin.bale_id, {**state, "step": "admin_installment_count", "inst_first": first})
        await send_message(bot, admin.bale_id, "تعداد اقساط بعد از پرداخت اولیه:")
    except:
        await send_message(bot, admin.bale_id, "عدد وارد کن.")

async def installment_set_count(bot, admin, text):
    state = get_state(admin.bale_id)
    try:
        count = int(text.strip())
        set_state(admin.bale_id, {**state, "step": "admin_installment_details",
                                   "inst_count": count, "inst_current": 1, "inst_data": []})
        await send_message(bot, admin.bale_id,
            f"قسط 1 از {count}\nفرمت: مبلغ | تاریخ\nمثال: 500000 | 1404/06/01")
    except:
        await send_message(bot, admin.bale_id, "عدد وارد کن.")

async def installment_add_detail(bot, admin, text, db):
    state = get_state(admin.bale_id)
    count = state.get("inst_count", 1)
    current = state.get("inst_current", 1)
    inst_data = state.get("inst_data", [])
    try:
        import jdatetime
        parts = [p.strip() for p in text.split("|")]
        amount = int(parts[0].replace(",", ""))
        jalali_dt = jdatetime.datetime.strptime(parts[1].strip(), "%Y/%m/%d")
        due_date = jalali_dt.togregorian()
        inst_data.append({"amount": amount, "due_date": due_date, "number": current})
        if current < count:
            set_state(admin.bale_id, {**state, "inst_current": current+1, "inst_data": inst_data})
            await send_message(bot, admin.bale_id,
                f"قسط {current} ثبت شد.\nقسط {current+1} از {count}\nفرمت: مبلغ | تاریخ")
        else:
            # ذخیره پلن
            clear_state(admin.bale_id)
            plan = InstallmentPlan(
                product_id=state.get("inst_id") if state.get("inst_type") == "product" else None,
                package_id=state.get("inst_id") if state.get("inst_type") == "package" else None,
                first_payment=state.get("inst_first"),
                total_count=count,
            )
            db.add(plan)
            db.commit()
            db.refresh(plan)
            for d in inst_data:
                inst = Installment(
                    plan_id=plan.id, number=d["number"],
                    amount=d["amount"], due_date=d["due_date"]
                )
                db.add(inst)
            db.commit()
            await send_message(bot, admin.bale_id,
                f"پلن اقساطی با {count} قسط ذخیره شد.",
                reply_markup=inline_keyboard([[{"text": "🔙 داشبورد", "callback_data": "admin_dashboard"}]]))
    except Exception as e:
        await send_message(bot, admin.bale_id, f"خطا: {e}\nمثال: 500000 | 1404/06/01")

async def approve_installment_admin(bot, admin, ui_id, db):
    from bot.handlers.installment import approve_installment
    await approve_installment(bot, ui_id, db)
    await send_message(bot, admin.bale_id, "قسط تأیید شد.")

async def reject_installment_admin(bot, admin, ui_id):
    from bot.handlers.installment import prompt_reject_installment
    await prompt_reject_installment(bot, admin.bale_id, ui_id)


# ==================== اقساط ====================

async def prompt_installment_question(bot, admin, entity_type, entity_id, price):
    state = get_state(admin.bale_id)
    set_state(admin.bale_id, {
        **state,
        "step": "admin_installment_yn",
        "inst_type": entity_type,
        "inst_id": entity_id,
        "inst_price": price,
    })
    await send_message(bot, admin.bale_id,
        f"آیا این آیتم اقساط دارد؟",
        reply_markup=inline_keyboard([
            [{"text": "بله، اقساط دارد", "callback_data": "admin_inst_yes"}],
            [{"text": "خیر، نقدی است", "callback_data": "admin_inst_no"}],
        ]))

async def handle_inst_yes(bot, admin):
    state = get_state(admin.bale_id)
    set_state(admin.bale_id, {**state, "step": "admin_inst_first_payment"})
    await send_message(bot, admin.bale_id,
        f"مبلغ کل: {state.get('inst_price',0):,} تومان\nمبلغ پرداخت اولیه (تومان):")

async def handle_inst_no(bot, admin, db):
    state = get_state(admin.bale_id)
    entity_type = state.get("inst_type")
    entity_id = state.get("inst_id")
    is_group = state.get("is_group", False)
    if entity_type == "package":
        from models.installment import InstallmentPlan, Installment
        existing_plan = db.query(InstallmentPlan).filter(InstallmentPlan.package_id == entity_id).first()
        if existing_plan:
            db.query(Installment).filter(Installment.plan_id == existing_plan.id).delete()
            db.delete(existing_plan)
            db.commit()
    if entity_type == "package":
        pkg = db.query(CoachingPackage).filter(CoachingPackage.id == entity_id).first()
        if pkg:
            capacity = state.get("capacity", 1)
            sessions = pkg.session_count
            total_slots = sessions if is_group else sessions * capacity
            set_state(admin.bale_id, {
                **state, "step": "admin_slot_datetime", "pkg_id": pkg.id,
                "current_session": 1, "current_person": 1,
                "collected_slots": [], "capacity": capacity,
                "total_slots": total_slots, "pkg_sessions": sessions,
                "is_group": is_group,
            })
            if is_group:
                await send_message(bot, admin.bale_id,
                    f"گروهی بدون اقساط.\nجلسه 1 از {sessions}\nفرمت: 1405/05/20 16:00")
            else:
                await send_message(bot, admin.bale_id,
                    f"بدون اقساط.\nنفر 1 از {capacity}\nجلسه 1 از {sessions}\nفرمت: 1405/05/20 16:00")
    elif entity_type == "product":
        set_state(admin.bale_id, {"step": "admin_product_link", "product_id": entity_id})
        await send_message(bot, admin.bale_id, "لینک یا توضیح:\n(برای رد: /skip)")

async def inst_set_first_payment(bot, admin, text):
    state = get_state(admin.bale_id)
    try:
        first = int(text.replace(",", ""))
        set_state(admin.bale_id, {**state, "step": "admin_inst_count", "inst_first": first})
        await send_message(bot, admin.bale_id, "تعداد اقساط (بعد از پرداخت اولیه):")
    except:
        await send_message(bot, admin.bale_id, "عدد وارد کن.")

async def inst_set_count(bot, admin, text):
    state = get_state(admin.bale_id)
    try:
        count = int(text.strip())
        set_state(admin.bale_id, {**state, "step": "admin_inst_details",
                                   "inst_count": count, "inst_current": 1, "inst_data": [],
                                   "inst_person": 1, "all_person_data": {}})
        await send_message(bot, admin.bale_id,
            f"قسط 1 از {count}\nفرمت: مبلغ | تاریخ\nمثال: 500000 | 1404/06/01")
    except:
        await send_message(bot, admin.bale_id, "عدد وارد کن.")

async def inst_add_detail(bot, admin, text, db):
    state = get_state(admin.bale_id)
    count = state.get("inst_count", 1)
    current = state.get("inst_current", 1)
    inst_data = state.get("inst_data", [])
    current_person = state.get("inst_person", 1)
    capacity = state.get("capacity", 1)
    all_person_data = state.get("all_person_data", {})
    try:
        import jdatetime
        parts = [p.strip() for p in text.split("|")]
        amount = int(parts[0].replace(",", ""))
        jalali_dt = jdatetime.datetime.strptime(parts[1].strip(), "%Y/%m/%d")
        due_date = jalali_dt.togregorian()
        inst_data.append({"amount": amount, "due_date": due_date, "number": current})
        if current < count:
            set_state(admin.bale_id, {**state, "inst_current": current+1, "inst_data": inst_data})
            await send_message(bot, admin.bale_id,
                f"قسط {current} نفر {current_person} ثبت شد.\nقسط {current+1} از {count}\nفرمت: مبلغ | تاریخ")
        else:
            # اقساط این نفر تموم شد
            all_person_data[str(current_person)] = inst_data
            if current_person < capacity:
                # برو نفر بعدی
                next_person = current_person + 1
                set_state(admin.bale_id, {
                    **state,
                    "inst_current": 1,
                    "inst_data": [],
                    "inst_person": next_person,
                    "all_person_data": all_person_data,
                })
                await send_message(bot, admin.bale_id,
                    f"اقساط نفر {current_person} ثبت شد.\n\nنفر {next_person} از {capacity}\nقسط 1 از {count}\nفرمت: مبلغ | تاریخ")
            else:
                # همه نفرات تموم شد — ذخیره پلن‌ها
                entity_type = state.get("inst_type")
                entity_id = state.get("inst_id")
                is_group = state.get("is_group", False)
                from models.installment import InstallmentPlan, Installment
                # گروهی: یه پلن برای همه
                if is_group:
                    all_person_data["1"] = inst_data
                for person_num, person_insts in all_person_data.items():
                    plan = InstallmentPlan(
                        product_id=entity_id if entity_type == "product" else None,
                        package_id=entity_id if entity_type == "package" else None,
                        first_payment=state.get("inst_first"),
                        total_count=count,
                    )
                    db.add(plan)
                    db.commit()
                    db.refresh(plan)
                    for d in person_insts:
                        inst = Installment(plan_id=plan.id, number=d["number"],
                                           amount=d["amount"], due_date=d["due_date"])
                        db.add(inst)
                db.commit()
                if state.get("inst_type") == "package":
                    pkg_id = state.get("inst_id")
                    pkg2 = db.query(CoachingPackage).filter(CoachingPackage.id == pkg_id).first()
                    if pkg2:
                        sessions = pkg2.session_count
                        total_slots = sessions * capacity
                        set_state(admin.bale_id, {
                            **state, "step": "admin_slot_datetime", "pkg_id": pkg_id,
                            "current_session": 1, "current_person": 1,
                            "collected_slots": [], "capacity": capacity,
                            "total_slots": total_slots, "pkg_sessions": sessions,
                        })
                        await send_message(bot, admin.bale_id,
                            f"پلن اقساطی برای {capacity} نفر ذخیره شد.\nنفر 1 از {capacity}\nجلسه 1 از {sessions}\nفرمت: 1404/05/20 16:00")
                        return
                clear_state(admin.bale_id)
                await send_message(bot, admin.bale_id,
                    f"پلن اقساطی برای {capacity} نفر ذخیره شد.",
                    reply_markup=inline_keyboard([[{"text": "داشبورد", "callback_data": "admin_dashboard"}]]))
    except Exception as e:
        await send_message(bot, admin.bale_id, f"خطا: {e}\nمثال: 500000 | 1404/06/01")

async def prompt_edit_channel(bot, admin, db):
    try:
        from sqlalchemy import text as sqlt
        r = db.execute(sqlt("SELECT value FROM bot_settings WHERE key='force_channel'")).fetchone()
        current = r[0] if r and r[0] else "تنظیم نشده"
    except:
        current = "تنظیم نشده"
    set_state(admin.bale_id, {"step": "admin_edit_channel"})
    await send_message(bot, admin.bale_id,
        f"کانال فعلی: {current}\nآیدی کانال جدید را وارد کن:\n(مثال: @mychannel)\n(برای حذف: /remove)")

async def save_channel(bot, admin, text, db):
    clear_state(admin.bale_id)
    value = "" if text.strip() == "/remove" else text.strip()
    try:
        from sqlalchemy import text as sqlt
        db.execute(sqlt("INSERT INTO bot_settings (key,value) VALUES ('force_channel',:v) ON CONFLICT(key) DO UPDATE SET value=:v"), {"v": value})
        db.commit()
        msg = "کانال اجباری حذف شد." if not value else f"کانال {value} تنظیم شد."
    except Exception as e:
        msg = f"خطا: {e}"
    await send_message(bot, admin.bale_id, msg, reply_markup=inline_keyboard([
        [{"text": "⚙️ تنظیمات", "callback_data": "admin_settings"}],
    ]))

async def show_test_access_menu(bot, admin, test_id, db):
    from models.test import Test
    test = db.query(Test).filter(Test.id == test_id).first()
    if not test:
        return
    access = getattr(test, 'access_type', 'free') or 'free'
    labels = {"free": "رایگان", "invite": "دعوتی", "paid": "پولی"}
    await send_message(bot, admin.bale_id,
        f"نوع دسترسی: {labels.get(access, access)}",
        reply_markup=inline_keyboard([
            [{"text": "🆓 رایگان", "callback_data": f"admin_set_access_{test_id}_free"}],
            [{"text": "🎁 دعوتی (۳ نفر)", "callback_data": f"admin_set_access_{test_id}_invite"}],
            [{"text": "💰 پولی (فیش)", "callback_data": f"admin_set_access_{test_id}_paid"}],
            [{"text": "🔙 بازگشت", "callback_data": f"admin_test_menu_{test_id}"}],
        ]))

async def set_test_access(bot, admin, test_id, access_type, db):
    try:
        from sqlalchemy import text as sqlt
        db.execute(sqlt("UPDATE tests SET access_type=:a WHERE id=:id"), {"a": access_type, "id": test_id})
        db.commit()
        labels = {"free": "رایگان", "invite": "دعوتی", "paid": "پولی"}
        await send_message(bot, admin.bale_id, f"نوع دسترسی به {labels.get(access_type)} تغییر کرد.")
    except Exception as e:
        await send_message(bot, admin.bale_id, f"خطا: {e}")

async def prompt_test_content(bot, admin, test_id):
    set_state(admin.bale_id, {"step": "admin_test_content", "test_id": test_id})
    await send_message(bot, admin.bale_id,
        "محتوای تحلیلی تست را وارد کن:\n(این متن بعد از نمایش نتیجه ارسال میشه)\n(برای حذف: /remove)")

async def save_test_content(bot, admin, text, db):
    state = get_state(admin.bale_id)
    test_id = state.get("test_id")
    clear_state(admin.bale_id)
    value = None if text.strip() == "/remove" else text.strip()
    try:
        from sqlalchemy import text as sqlt
        db.execute(sqlt("UPDATE tests SET analysis_content=:v WHERE id=:id"), {"v": value, "id": test_id})
        db.commit()
        await send_message(bot, admin.bale_id, "محتوای تحلیلی ذخیره شد.", reply_markup=inline_keyboard([
            [{"text": "🔙 بازگشت", "callback_data": f"admin_test_menu_{test_id}"}],
        ]))
    except Exception as e:
        await send_message(bot, admin.bale_id, f"خطا: {e}")


async def prompt_test_order(bot, admin, test_id):
    set_state(admin.bale_id, {"step": "admin_test_order", "test_id": test_id})
    await send_message(bot, admin.bale_id, "شماره ترتیب جدید را وارد کن:\n(مثال: 1 برای اول)")

async def save_test_order(bot, admin, text, db):
    state = get_state(admin.bale_id)
    test_id = state.get("test_id")
    clear_state(admin.bale_id)
    try:
        order = int(text.strip()) - 1
        from sqlalchemy import text as sqlt
        db.execute(sqlt("UPDATE tests SET \"order\"=:o WHERE id=:id"), {"o": order, "id": test_id})
        db.commit()
        await send_message(bot, admin.bale_id, f"ترتیب تست به {text.strip()} تغییر کرد.", reply_markup=inline_keyboard([
            [{"text": "🔙 مدیریت تست‌ها", "callback_data": "admin_tests"}],
        ]))
    except Exception as e:
        await send_message(bot, admin.bale_id, f"خطا: {e}")

async def prompt_test_analysis_content(bot, admin, test_id, db):
    """گرفتن تحلیل‌های بازه‌ای از ادمین"""
    from models.test import ScoreRange
    ranges = db.query(ScoreRange).filter(ScoreRange.test_id == test_id).order_by(ScoreRange.min_score).all()
    if not ranges:
        await send_message(bot, admin.bale_id, "این تست بازه‌ای ندارد. اول بازه‌های امتیاز را تنظیم کن.")
        return
    set_state(admin.bale_id, {"step": "admin_test_range_content", "test_id": test_id, "range_index": 0, "range_ids": [r.id for r in ranges]})
    r = ranges[0]
    await send_message(bot, admin.bale_id,
        f"تحلیل بازه {r.min_score} تا {r.max_score} ({r.title}) را بنویس:\n(برای رد: /skip)")

async def save_test_range_content(bot, admin, text, db):
    state = get_state(admin.bale_id)
    test_id = state.get("test_id")
    range_ids = state.get("range_ids", [])
    idx = state.get("range_index", 0)

    if text.strip() != "/skip":
        from models.test import ScoreRange
        r = db.query(ScoreRange).filter(ScoreRange.id == range_ids[idx]).first()
        if r:
            r.analysis = text.strip()
            db.commit()

    next_idx = idx + 1
    if next_idx < len(range_ids):
        set_state(admin.bale_id, {**state, "range_index": next_idx})
        from models.test import ScoreRange
        r = db.query(ScoreRange).filter(ScoreRange.id == range_ids[next_idx]).first()
        await send_message(bot, admin.bale_id,
            f"تحلیل بازه {r.min_score} تا {r.max_score} ({r.title}) را بنویس:\n(برای رد: /skip)")
    else:
        clear_state(admin.bale_id)
        await send_message(bot, admin.bale_id, "همه تحلیل‌های بازه‌ای ذخیره شدن.", reply_markup=inline_keyboard([
            [{"text": "🔙 بازگشت به تست", "callback_data": f"admin_test_menu_{test_id}"}],
        ]))


async def show_test_ranges(bot, admin, test_id, db):
    from models.test import ScoreRange
    ranges = db.query(ScoreRange).filter(ScoreRange.test_id == test_id).order_by(ScoreRange.min_score).all()
    buttons = []
    for r in ranges:
        buttons.append([{"text": f"{int(r.min_score)} تا {int(r.max_score)} — {r.title}", "callback_data": f"admin_edit_range_{r.id}"}])
    buttons.append([{"text": "➕ افزودن بازه جدید", "callback_data": f"admin_add_range_{test_id}"}])
    buttons.append([{"text": "🔙 بازگشت", "callback_data": f"admin_test_menu_{test_id}"}])
    await send_message(bot, admin.bale_id, f"{len(ranges)} بازه:", reply_markup=inline_keyboard(buttons))

async def prompt_add_range(bot, admin, test_id):
    set_state(admin.bale_id, {"step": "admin_add_range", "test_id": test_id})
    await send_message(bot, admin.bale_id,
        "بازه جدید را وارد کن:\nفرمت: حداقل | حداکثر | عنوان | متن تحلیل\nمثال: 15 | 35 | واقع‌گرا | متن تحلیل شما...")

async def save_new_range(bot, admin, text, db):
    state = get_state(admin.bale_id)
    test_id = state.get("test_id")
    clear_state(admin.bale_id)
    try:
        parts = [p.strip() for p in text.split("|")]
        min_s = float(parts[0])
        max_s = float(parts[1])
        title = parts[2]
        analysis = "|".join(parts[3:]).strip()
        from models.test import ScoreRange
        r = ScoreRange(test_id=test_id, min_score=min_s, max_score=max_s, title=title, analysis=analysis)
        db.add(r)
        db.commit()
        await send_message(bot, admin.bale_id, f"بازه {int(min_s)} تا {int(max_s)} اضافه شد.",
            reply_markup=inline_keyboard([[{"text": "📊 بازه‌ها", "callback_data": f"admin_test_ranges_{test_id}"}]]))
    except Exception as e:
        await send_message(bot, admin.bale_id, f"خطا: {e}\nمثال: 15 | 35 | واقع‌گرا | متن تحلیل")

async def show_edit_range(bot, admin, range_id, db):
    from models.test import ScoreRange
    r = db.query(ScoreRange).filter(ScoreRange.id == range_id).first()
    if not r:
        return
    preview = r.analysis[:60] + "..." if len(r.analysis) > 60 else r.analysis
    await send_message(bot, admin.bale_id,
        f"بازه: {int(r.min_score)} تا {int(r.max_score)}\nعنوان: {r.title}\nتحلیل: {preview}",
        reply_markup=inline_keyboard([
            [{"text": "✏️ ویرایش", "callback_data": f"admin_update_range_{range_id}"},
             {"text": "🗑 حذف", "callback_data": f"admin_delete_range_{range_id}"}],
            [{"text": "🔙 بازگشت", "callback_data": f"admin_test_ranges_{r.test_id}"}],
        ]))

async def prompt_update_range(bot, admin, range_id, db):
    from models.test import ScoreRange
    r = db.query(ScoreRange).filter(ScoreRange.id == range_id).first()
    set_state(admin.bale_id, {"step": "admin_update_range", "range_id": range_id, "test_id": r.test_id if r else 0})
    await send_message(bot, admin.bale_id,
        f"بازه فعلی: {int(r.min_score)} تا {int(r.max_score)}\nبازه جدید را وارد کن:\nفرمت: حداقل | حداکثر | عنوان | متن تحلیل")

async def save_update_range(bot, admin, text, db):
    state = get_state(admin.bale_id)
    range_id = state.get("range_id")
    test_id = state.get("test_id")
    clear_state(admin.bale_id)
    try:
        parts = [p.strip() for p in text.split("|")]
        from models.test import ScoreRange
        r = db.query(ScoreRange).filter(ScoreRange.id == range_id).first()
        if r:
            r.min_score = float(parts[0])
            r.max_score = float(parts[1])
            r.title = parts[2]
            r.analysis = "|".join(parts[3:]).strip()
            db.commit()
        await send_message(bot, admin.bale_id, "بازه ویرایش شد.",
            reply_markup=inline_keyboard([[{"text": "📊 بازه‌ها", "callback_data": f"admin_test_ranges_{test_id}"}]]))
    except Exception as e:
        await send_message(bot, admin.bale_id, f"خطا: {e}")

async def delete_range(bot, admin, range_id, db):
    from models.test import ScoreRange
    r = db.query(ScoreRange).filter(ScoreRange.id == range_id).first()
    if r:
        test_id = r.test_id
        db.delete(r)
        db.commit()
        await send_message(bot, admin.bale_id, "بازه حذف شد.",
            reply_markup=inline_keyboard([[{"text": "📊 بازه‌ها", "callback_data": f"admin_test_ranges_{test_id}"}]]))

async def handle_admin_action(bot, admin, data, db):
    if data == "admin_pending_payments":
        await show_pending_payments(bot, admin, db)
    elif data == "admin_reservations":
        await show_reservations(bot, admin, db)
    elif data == "admin_search_user":
        await prompt_search_user(bot, admin)
    elif data == "admin_broadcast":
        await prompt_broadcast(bot, admin)
    elif data == "admin_add_slot":
        await prompt_add_slot(bot, admin)
    elif data == "admin_dashboard":
        await show_dashboard(bot, admin, db)
    elif data.startswith("admin_slottype_"):
        await prompt_add_slot_datetime(bot, admin, data.replace("admin_slottype_", ""))
    elif data == "admin_tests":
        await show_tests_management(bot, admin, db)
    elif data == "admin_products":
        await show_products_management(bot, admin, db)
    elif data == "admin_packages":
        await show_packages_management(bot, admin, db)
    elif data == "admin_new_package":
        await prompt_new_package(bot, admin)
    elif data.startswith("admin_pkg_menu_"):
        await show_package_menu(bot, admin, int(data.split("_")[-1]), db)
    elif data.startswith("admin_toggle_pkg_"):
        await toggle_package(bot, admin, int(data.split("_")[-1]), db)
    elif data.startswith("admin_delete_pkg_"):
        await delete_package(bot, admin, int(data.split("_")[-1]), db)
    elif data == "admin_reviews":
        await show_pending_reviews(bot, admin, db)
    elif data == "admin_report":
        await show_financial_report(bot, admin, db)
    elif data == "admin_settings":
        await show_settings(bot, admin, db)
    elif data == "admin_new_test":
        await prompt_new_test(bot, admin)
    elif data.startswith("admin_test_atype_"):
        await set_new_test_type(bot, admin, data.replace("admin_test_atype_", ""))
    elif data.startswith("admin_test_tone_"):
        await set_new_test_tone(bot, admin, data.replace("admin_test_tone_", ""))
    elif data == "admin_new_product":
        await prompt_new_product(bot, admin)
    elif data == "admin_edit_welcome":
        await prompt_edit_welcome(bot, admin)
    elif data == "admin_edit_card":
        await prompt_edit_card(bot, admin)
    elif data == "admin_edit_card_owner":
        await prompt_edit_card_owner(bot, admin)
    elif data == "admin_export_users":
        await export_users_excel(bot, admin, db)
    elif data == "admin_static_content":
        await show_static_content_menu(bot, admin, db)
    elif data.startswith("admin_sc_list_"):
        await show_sc_list(bot, admin, data.replace("admin_sc_list_", ""), db)
    elif data.startswith("admin_sc_item_"):
        await show_sc_item(bot, admin, int(data.split("_")[-1]), db)
    elif data.startswith("admin_sc_toggle_"):
        await toggle_sc_item(bot, admin, int(data.split("_")[-1]), db)
    elif data.startswith("admin_sc_delete_"):
        await delete_sc_item(bot, admin, int(data.split("_")[-1]), db)
    elif data.startswith("admin_sc_add_"):
        await prompt_add_sc(bot, admin, data.replace("admin_sc_add_", ""))
    elif data.startswith("admin_sc_media_"):
        await sc_set_media_type(bot, admin, data.replace("admin_sc_media_", ""))
    elif data.startswith("admin_approve_pay_"):
        from bot.handlers.payment import approve_payment
        await approve_payment(bot, int(data.split("_")[-1]), db)
        await send_message(bot, admin.bale_id, "✅ پرداخت تأیید شد.")
    elif data.startswith("admin_reject_pay_"):
        await prompt_reject_payment(bot, admin, int(data.split("_")[-1]))
    elif data == "admin_discounts":
        await show_discounts(bot, admin, db)
    elif data == "admin_new_discount":
        await prompt_new_discount(bot, admin)
    elif data.startswith("admin_discount_"):
        await show_discount_item(bot, admin, int(data.split("_")[-1]), db)
    elif data.startswith("admin_toggle_discount_"):
        await toggle_discount(bot, admin, int(data.split("_")[-1]), db)
    elif data.startswith("admin_delete_discount_"):
        await delete_discount(bot, admin, int(data.split("_")[-1]), db)
    elif data.startswith("admin_view_receipt_"):
        p = db.query(Payment).filter(Payment.id == int(data.split("_")[-1])).first()
        if p and p.receipt_image:
            await send_photo(bot, admin.bale_id, p.receipt_image, f"فیش {p.tracking_code}")
    elif data.startswith("admin_user_"):
        await show_user_profile(bot, admin, int(data.split("_")[-1]), db)
    elif data.startswith("admin_msg_user_"):
        await prompt_direct_message(bot, admin, int(data.split("_")[-1]))
    elif data.startswith("admin_block_"):
        u = db.query(User).filter(User.id == int(data.split("_")[-1])).first()
        if u:
            u.status = UserStatus.blocked
            db.commit()
            await send_message(bot, admin.bale_id, f"{u.full_name} بلاک شد.")
    elif data.startswith("admin_unblock_"):
        u = db.query(User).filter(User.id == int(data.split("_")[-1])).first()
        if u:
            u.status = UserStatus.active
            db.commit()
            await send_message(bot, admin.bale_id, f"{u.full_name} آنبلاک شد.")
    elif data.startswith("admin_cancel_res_"):
        await cancel_reservation(bot, admin, int(data.split("_")[-1]), db)
    elif data.startswith("admin_reschedule_"):
        await prompt_reschedule(bot, admin, int(data.split("_")[-1]), db)
    elif data.startswith("admin_newslot_"):
        await reschedule_reservation(bot, admin, int(data.split("_")[-1]), db)
    elif data.startswith("admin_test_menu_"):
        await show_test_menu(bot, admin, int(data.split("_")[-1]), db)
    elif data.startswith("admin_toggle_test_"):
        await toggle_test(bot, admin, int(data.split("_")[-1]), db)
    elif data.startswith("admin_confirm_delete_test_"):
        await confirm_delete_test(bot, admin, int(data.split("_")[-1]), db)
    elif data.startswith("admin_delete_test_"):
        await delete_test(bot, admin, int(data.split("_")[-1]), db)
    elif data.startswith("admin_product_menu_"):
        await show_product_menu(bot, admin, int(data.split("_")[-1]), db)
    elif data.startswith("admin_toggle_product_"):
        await toggle_product(bot, admin, int(data.split("_")[-1]), db)
    elif data.startswith("admin_delete_product_"):
        await delete_product(bot, admin, int(data.split("_")[-1]), db)
    elif data.startswith("admin_ptype_"):
        await set_product_type(bot, admin, data.replace("admin_ptype_", ""))
    elif data.startswith("admin_approve_review_"):
        await approve_review(bot, admin, int(data.split("_")[-1]), db)
    elif data.startswith("admin_reject_review_"):
        await reject_review(bot, admin, int(data.split("_")[-1]), db)
    elif data.startswith("admin_approve_installment_"):
        await approve_installment_admin(bot, admin, int(data.split("_")[-1]), db)
    elif data.startswith("admin_reject_installment_"):
        await reject_installment_admin(bot, admin, int(data.split("_")[-1]))
    elif data == "admin_edit_channel":
        await prompt_edit_channel(bot, admin, db)
    elif data.startswith("admin_test_access_"):
        await show_test_access_menu(bot, admin, int(data.split("_")[-1]), db)
    elif data.startswith("admin_set_access_"):
        parts = data.split("_")
        await set_test_access(bot, admin, int(parts[3]), parts[4], db)
    elif data.startswith("admin_test_ranges_"):
        await show_test_ranges(bot, admin, int(data.split("_")[-1]), db)
    elif data.startswith("admin_add_range_"):
        await prompt_add_range(bot, admin, int(data.split("_")[-1]))
    elif data.startswith("admin_edit_range_"):
        await show_edit_range(bot, admin, int(data.split("_")[-1]), db)
    elif data.startswith("admin_update_range_"):
        await prompt_update_range(bot, admin, int(data.split("_")[-1]), db)
    elif data.startswith("admin_delete_range_"):
        await delete_range(bot, admin, int(data.split("_")[-1]), db)
    elif data.startswith("admin_test_order_"):
        await prompt_test_order(bot, admin, int(data.split("_")[-1]))
    elif data.startswith("admin_test_results_"):
        test_id = int(data.split("_")[-1])
        from models.test import Test, TestResult
        from sqlalchemy import func
        count = db.query(func.count(TestResult.id)).filter(TestResult.test_id == test_id).scalar()
        test = db.query(Test).filter(Test.id == test_id).first()
        results = db.query(TestResult).filter(TestResult.test_id == test_id).order_by(TestResult.created_at.desc()).limit(10).all()
        msg = f"نتایج تست {test.title if test else '-'}\n{count} بار انجام شده\n━━━━━━━━━━━━━"
        for r in results:
            msg += f"\n👤 {r.user.full_name if r.user else '-'} | امتیاز: {r.total_score:.1f} | نتیجه: {r.result_title or '-'}"
        await send_message(bot, admin.bale_id, msg, reply_markup=inline_keyboard([
            [{"text": "🔙 بازگشت", "callback_data": f"admin_test_menu_{test_id}"}],
        ]))
    elif data.startswith("admin_test_content_"):
        await prompt_test_analysis_content(bot, admin, int(data.split("_")[-1]), db)
    elif data == "admin_inst_yes":
        await handle_inst_yes(bot, admin)
    elif data == "admin_inst_no":
        await handle_inst_no(bot, admin, db)