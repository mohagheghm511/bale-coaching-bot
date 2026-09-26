import uuid
from models.user import User
from models.payment import Payment, PaymentStatus, PaymentMethod
from models.discount import DiscountCode
from bot.sender import send_message, inline_keyboard
from bot.dispatcher import get_state, set_state, clear_state
from core.config import settings


def _gen_tracking():
    return "C" + str(uuid.uuid4()).replace("-","")[:9].upper()


def _card_info(db=None):
    card = ""
    owner = ""
    # اول از bot_settings بخون
    try:
        from bot.handlers.admin import bot_settings
        card = bot_settings.get("card_number", "")
        owner = bot_settings.get("card_owner", "")
    except:
        pass
    # اگه خالی بود از دیتابیس بخون
    if not card and db:
        try:
            from sqlalchemy import text as sqlt
            r = db.execute(sqlt("SELECT value FROM bot_settings WHERE key='card_number'")).fetchone()
            if r and r[0]:
                card = r[0]
                try:
                    from bot.handlers.admin import bot_settings
                    bot_settings["card_number"] = card
                except:
                    pass
            r2 = db.execute(sqlt("SELECT value FROM bot_settings WHERE key='card_owner'")).fetchone()
            if r2 and r2[0]:
                owner = r2[0]
                try:
                    from bot.handlers.admin import bot_settings
                    bot_settings["card_owner"] = owner
                except:
                    pass
        except:
            pass
    if card:
        text = f"💳 شماره کارت: {card}"
        if owner:
            text += f"\n👤 به نام: {owner}"
        return text
    return "💳 شماره کارت در تنظیمات ادمین ثبت نشده."


async def _notify_admins_with_photo(bot, file_id, caption, buttons):
    for admin_id in settings.admin_ids:
        try:
            await send_message(bot, admin_id, caption, reply_markup=buttons)
        except Exception as e:
            print(f"notify error {admin_id}: {e}")


# ==================== شروع پرداخت ====================

async def start_payment(bot, user, amount, db, reservation_id=None, product_id=None):
    set_state(user.bale_id, {
        "step": "payment_discount",
        "amount": amount,
        "original_amount": amount,
        "reservation_id": reservation_id,
        "product_id": product_id,
    })
    await send_message(bot, user.bale_id,
        f"💰 مبلغ قابل پرداخت: {amount:,} تومان\n\nآیا کد تخفیف داری؟",
        reply_markup=inline_keyboard([
            [{"text": "🎟 دارم، کد تخفیف وارد کن", "callback_data": "payment_enter_discount"}],
            [{"text": "💳 ندارم، ادامه پرداخت", "callback_data": "payment_no_discount"}],
        ]))


async def handle_enter_discount(bot, user):
    state = get_state(user.bale_id)
    set_state(user.bale_id, {**state, "step": "payment_waiting_discount"})
    await send_message(bot, user.bale_id, "🎟 کد تخفیف را وارد کن:")


async def handle_discount_code(bot, user, code, db):
    state = get_state(user.bale_id)
    original_amount = state.get("original_amount", state.get("amount", 0))

    discount = db.query(DiscountCode).filter(
        DiscountCode.code == code.strip().upper(),
        DiscountCode.is_active == True
    ).first()

    if not discount:
        await send_message(bot, user.bale_id, "❌ کد تخفیف نامعتبر است.",
            reply_markup=inline_keyboard([
                [{"text": "🔄 کد دیگری وارد کن", "callback_data": "payment_enter_discount"}],
                [{"text": "💳 بدون تخفیف ادامه بده", "callback_data": "payment_no_discount"}],
            ]))
        return

    if discount.max_uses > 0 and discount.used_count >= discount.max_uses:
        await send_message(bot, user.bale_id, "❌ این کد به حداکثر استفاده رسیده.",
            reply_markup=inline_keyboard([
                [{"text": "💳 بدون تخفیف ادامه بده", "callback_data": "payment_no_discount"}],
            ]))
        return

    new_amount = max(0, original_amount - discount.amount)
    set_state(user.bale_id, {
        **state,
        "step": "payment_discount",
        "amount": new_amount,
        "discount_amount": discount.amount,
        "discount_code": code.strip().upper(),
    })
    await send_message(bot, user.bale_id,
        f"✅ کد تخفیف اعمال شد!\n"
        f"💰 مبلغ اصلی: {original_amount:,} تومان\n"
        f"🎟 تخفیف: {discount.amount:,} تومان\n"
        f"💵 مبلغ نهایی: {new_amount:,} تومان",
        reply_markup=inline_keyboard([
            [{"text": "💳 ادامه پرداخت", "callback_data": "payment_no_discount"}],
        ]))


async def handle_no_discount(bot, user, db):
    state = get_state(user.bale_id)
    amount = state.get("amount", 0)
    tracking = state.get("tracking") or _gen_tracking()
    set_state(user.bale_id, {**state, "step": "payment_waiting_receipt", "tracking": tracking})

    card_text = _card_info(db)
    await send_message(bot, user.bale_id,
        f"💳 اطلاعات پرداخت\n━━━━━━━━━━━━━\n"
        f"{card_text}\n"
        f"━━━━━━━━━━━━━\n"
        f"💰 مبلغ: {amount:,} تومان\n"
        f"🔖 کد پیگیری: {tracking}\n\n"
        f"بعد از واریز، عکس فیش را ارسال کن 👇")


# ==================== دریافت فیش ====================

async def handle_receipt_upload(bot, user, photo, db):
    state = get_state(user.bale_id)
    # tracking همیشه از نو ساخته میشه تا تکراری نباشه
    old_tracking = state.get("tracking", "")
    tracking = old_tracking if old_tracking else _gen_tracking()
    # چک تکراری بودن
    existing = db.query(Payment).filter(Payment.tracking_code == tracking).first()
    if existing:
        tracking = _gen_tracking()
    file_id = getattr(photo, "file_id", None) or str(photo)
    discount_code = state.get("discount_code")
    discount_amount = state.get("discount_amount", 0)

    # اگه payment_id از قبل داریم (رزرو کوچینگ)
    existing_payment_id = state.get("payment_id")
    if existing_payment_id:
        payment = db.query(Payment).filter(Payment.id == existing_payment_id).first()
        if payment:
            payment.receipt_image = file_id
            payment.status = PaymentStatus.uploaded
            # ذخیره کد تخفیف
            if discount_code:
                from sqlalchemy import text as sqlt
                db.execute(sqlt("UPDATE payments SET discount_code=:c, discount_amount=:a, amount=:m WHERE id=:id"),
                    {"c": discount_code, "a": discount_amount,
                     "m": max(0, payment.amount - discount_amount), "id": payment.id})
            db.commit()
    # کم کردن ظرفیت موقع ارسال فیش
    if payment.reservation_id:
        try:
            from models.product import Reservation, CoachingPackage
            _res = db.query(Reservation).filter(Reservation.id == payment.reservation_id).first()
            if _res and _res.package_id and _res.session_number == 1:
                _pkg = db.query(CoachingPackage).filter(CoachingPackage.id == _res.package_id).first()
                if _pkg and _pkg.capacity > 0:
                    _pkg.capacity -= 1
                    if _pkg.capacity <= 0:
                        _pkg.is_active = False
                    db.commit()
        except:
            pass
            clear_state(user.bale_id)

            await send_message(bot, user.bale_id,
                f"✅ فیش دریافت شد و در انتظار تأیید ادمین است.\n🔖 {tracking}",
                reply_markup=inline_keyboard([[{"text": "🏠 منو اصلی", "callback_data": "goto_main"}]]))

            disc_text = f"\n🎟 تخفیف: {discount_amount:,} تومان (کد: {discount_code})" if discount_code else ""
            caption = (f"📸 فیش پرداخت\n👤 {user.full_name} | 📞 {user.phone or '-'}\n"
                      f"💰 {payment.amount:,} تومان{disc_text}\n🔖 {tracking}")
            btns = inline_keyboard([
                [{"text": "✅ تأیید پرداخت", "callback_data": f"admin_approve_pay_{payment.id}"},
                 {"text": "❌ رد پرداخت", "callback_data": f"admin_reject_pay_{payment.id}"}],
            ])
            await _notify_admins_with_photo(bot, file_id, caption, btns)
            return

    # پرداخت جدید
    amount = state.get("amount", 0)
    reservation_id = state.get("reservation_id")
    product_id = state.get("product_id")

    payment = Payment(
        user_id=user.id,
        reservation_id=reservation_id,
        product_id=product_id,
        amount=amount,
        method=PaymentMethod.card_transfer,
        status=PaymentStatus.uploaded,
        tracking_code=tracking,
        receipt_image=file_id,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    # ذخیره کد تخفیف با raw SQL
    if discount_code:
        from sqlalchemy import text as sqlt
        db.execute(sqlt("UPDATE payments SET discount_code=:c, discount_amount=:a WHERE id=:id"),
            {"c": discount_code, "a": discount_amount, "id": payment.id})
        db.commit()

    # کم کردن ظرفیت موقع ارسال فیش
    if payment.reservation_id:
        try:
            from models.product import Reservation, CoachingPackage
            _res = db.query(Reservation).filter(Reservation.id == payment.reservation_id).first()
            if _res and _res.package_id and _res.session_number == 1:
                _pkg = db.query(CoachingPackage).filter(CoachingPackage.id == _res.package_id).first()
                if _pkg and _pkg.capacity > 0:
                    _pkg.capacity -= 1
                    if _pkg.capacity <= 0:
                        _pkg.is_active = False
                    db.commit()
        except:
            pass
    clear_state(user.bale_id)

    await send_message(bot, user.bale_id,
        f"✅ فیش دریافت شد و در انتظار تأیید ادمین است.\n🔖 {tracking}",
        reply_markup=inline_keyboard([[{"text": "🏠 منو اصلی", "callback_data": "goto_main"}]]))

    disc_text = f"\n🎟 تخفیف: {discount_amount:,} تومان (کد: {discount_code})" if discount_code else ""
    caption = (f"📸 فیش جدید\n━━━━━━━━━━━━━\n"
               f"👤 {user.full_name} | 📞 {user.phone or '-'}\n"
               f"💰 {amount:,} تومان{disc_text}\n"
               f"🔖 {tracking}")
    btns = inline_keyboard([
        [{"text": "✅ تأیید پرداخت", "callback_data": f"admin_approve_pay_{payment.id}"},
         {"text": "❌ رد پرداخت", "callback_data": f"admin_reject_pay_{payment.id}"}],
    ])
    await _notify_admins_with_photo(bot, file_id, caption, btns)


# ==================== نمایش کارت برای پرداخت موجود ====================

async def show_payment_card(bot, user, payment_id, db):
    payment = db.query(Payment).filter(Payment.id == payment_id, Payment.user_id == user.id).first()
    if not payment:
        await send_message(bot, user.bale_id, "❌ پرداخت پیدا نشد.")
        return
    card_text = _card_info(db)
    tracking = payment.tracking_code
    state = get_state(user.bale_id)
    set_state(user.bale_id, {
        **state,
        "step": "payment_waiting_receipt",
        "tracking": tracking,
        "payment_id": payment_id,
    })
    await send_message(bot, user.bale_id,
        f"💳 اطلاعات پرداخت\n━━━━━━━━━━━━━\n"
        f"{card_text}\n"
        f"━━━━━━━━━━━━━\n"
        f"💰 مبلغ: {payment.amount:,} تومان\n"
        f"🔖 کد پیگیری: {tracking}\n\n"
        f"بعد از واریز، عکس فیش را ارسال کن 👇")


# ==================== تأیید / رد ادمین ====================

async def approve_payment(bot, payment_id, db):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        return
    payment.status = PaymentStatus.approved

    # آپدیت کد تخفیف با raw SQL
    try:
        from sqlalchemy import text as sqlt
        dc_row = db.execute(sqlt("SELECT discount_code FROM payments WHERE id=:id"), {"id": payment_id}).fetchone()
        discount_code = dc_row[0] if dc_row and dc_row[0] else None
        if discount_code:
            dc = db.query(DiscountCode).filter(DiscountCode.code == discount_code).first()
            if dc:
                dc.used_count += 1
                if dc.max_uses > 0 and dc.used_count >= dc.max_uses:
                    dc.is_active = False
    except:
        pass

    db.commit()

    msg = (f"✅ پرداخت شما تأیید شد!\n"
           f"🔖 {payment.tracking_code}\n"
           f"💰 {payment.amount:,} تومان\n\nممنون 🙏")

    if payment.reservation_id:
        from models.product import Reservation, CoachingPackage, ReservationStatus
        res = db.query(Reservation).filter(Reservation.id == payment.reservation_id).first()
        if res:
            res.status = "confirmed"
            # کم کردن ظرفیت پکیج
            if res.package_id and res.session_number == 1:
                pkg = db.query(CoachingPackage).filter(CoachingPackage.id == res.package_id).first()
                if pkg and pkg.capacity > 0:
                    pass  # ظرفیت با confirmed count چک میشه
            if res.package_id and res.session_number == 1:
                pkg_check = db.query(CoachingPackage).filter(CoachingPackage.id == res.package_id).first()
                if pkg_check:
                    confirmed_count = db.query(Reservation).filter(
                        Reservation.package_id == res.package_id,
                        Reservation.session_number == 1,
                        Reservation.status == ReservationStatus.confirmed
                    ).count()
                    if confirmed_count >= pkg_check.capacity:
                        pkg_check.is_active = False
            db.commit()

            # اقساط
            from models.product import CoachingPackage as CP
            pkg2 = db.query(CP).filter(CP.id == res.package_id).first()
            if pkg2 and payment.amount < pkg2.price:
                from models.installment import InstallmentPlan, Installment, UserInstallment
                plan = db.query(InstallmentPlan).filter(
                    InstallmentPlan.package_id == res.package_id,
                    InstallmentPlan.is_active == True
                ).first()
                if plan:
                    insts = db.query(Installment).filter(
                        Installment.plan_id == plan.id
                    ).order_by(Installment.number).all()
                    for inst in insts:
                        ui = UserInstallment(
                            user_id=payment.user_id,
                            plan_id=plan.id,
                            installment_id=inst.id,
                            status="pending"
                        )
                        db.add(ui)
                    db.commit()
                    msg += "\n\n💳 اقساط شما فعال شد. از منو اصلی بخش «اقساط من» را ببینید."

    if payment.product_id:
        from models.product import Product
        prod = db.query(Product).filter(Product.id == payment.product_id).first()
        if prod and prod.link:
            msg += f"\n\n🔗 لینک دسترسی:\n{prod.link}"

    await send_message(bot, payment.user.bale_id, msg,
        reply_markup=inline_keyboard([[{"text": "🏠 منو اصلی", "callback_data": "goto_main"}]]))


async def prompt_reject_reason(bot, admin_bale_id, payment_id):
    set_state(admin_bale_id, {"step": "admin_reject_reason", "payment_id": payment_id})
    await send_message(bot, admin_bale_id, "📝 دلیل رد پرداخت را بنویس:")


async def reject_payment_with_reason(bot, admin_bale_id, reason, db):
    state = get_state(admin_bale_id)
    payment_id = state.get("payment_id")
    clear_state(admin_bale_id)

    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        return
    payment.status = PaymentStatus.rejected
    # برگشت ظرفیت
    if payment.reservation_id:
        try:
            from models.product import Reservation, CoachingPackage
            _res = db.query(Reservation).filter(Reservation.id == payment.reservation_id).first()
            if _res and _res.package_id and _res.session_number == 1:
                _pkg = db.query(CoachingPackage).filter(CoachingPackage.id == _res.package_id).first()
                if _pkg:
                    _pkg.capacity += 1
                    _pkg.is_active = True
        except:
            pass
    db.commit()

    await send_message(bot, payment.user.bale_id,
        f"❌ پرداخت شما تأیید نشد.\n🔖 {payment.tracking_code}\n\n📝 دلیل: {reason}",
        reply_markup=inline_keyboard([[{"text": "🏠 منو اصلی", "callback_data": "goto_main"}]]))
    await send_message(bot, admin_bale_id, "✅ دلیل رد ارسال شد.")


async def reject_payment(bot, payment_id, db):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        return
    payment.status = PaymentStatus.rejected
    db.commit()
    await send_message(bot, payment.user.bale_id,
        f"❌ پرداخت شما تأیید نشد.\n🔖 {payment.tracking_code}",
        reply_markup=inline_keyboard([[{"text": "🏠 منو اصلی", "callback_data": "goto_main"}]]))
