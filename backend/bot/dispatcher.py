from bale import Bot, Message, CallbackQuery
from sqlalchemy.orm import Session
from models.user import User, UserStatus
from core.config import settings

user_states: dict = {}

def get_state(bale_id: str) -> dict:
    return user_states.get(str(bale_id), {})

def set_state(bale_id: str, state: dict):
    user_states[str(bale_id)] = state

def clear_state(bale_id: str):
    user_states.pop(str(bale_id), None)

def is_admin(bale_id: str) -> bool:
    return str(bale_id) in settings.admin_ids

async def process_message(bot: Bot, message: Message, db: Session):
    bale_id = str(message.author.user_id)
    text = (message.content or "").strip()
    contact = getattr(message, "contact", None)
    photo = getattr(message, "document", None) or getattr(message, "photo", None)

    user = get_or_create_user(bale_id, message.author, db)
    if user.status == UserStatus.blocked:
        return

    state = get_state(bale_id)

    # شماره تلفن
    if contact and state.get("step") == "waiting_phone":
        phone = contact.phone_number if hasattr(contact, "phone_number") else str(contact)
        user.phone = phone
        db.commit()
        clear_state(bale_id)
        from bot.handlers.start import show_main_menu
        await show_main_menu(bot, user, db)
        return

    # پرداخت موفق
    successful_payment = getattr(message, "successful_payment", None)
    if successful_payment:
        from bot.handlers.payment import handle_successful_payment
        await handle_successful_payment(bot, user, successful_payment, db)
        return

    # آپلود فیش تست پولی
    if state.get("step") == "test_waiting_receipt" and photo:
        from bot.handlers.tests import handle_test_receipt
        await handle_test_receipt(bot, user, photo, db)
        return

    # آپلود فیش قسط
    if state.get("step") == "installment_waiting_receipt" and photo:
        from bot.handlers.installment import handle_installment_receipt
        await handle_installment_receipt(bot, user, photo, db)
        return

    # آپلود فیش کارت به کارت
    if state.get("step") == "payment_waiting_receipt" and photo:
        from bot.handlers.payment import handle_receipt_upload
        await handle_receipt_upload(bot, user, photo, db)
        return

    # آپلود فیش قدیمی (برای سازگاری)
    if state.get("step") == "waiting_receipt" and photo:
        from bot.handlers.payment import handle_receipt_upload
        await handle_receipt_upload(bot, user, photo, db)
        return

    # ادمین — آپلود فایل برای محتوای صفحات
    if is_admin(bale_id) and state.get("step") == "admin_sc_await_file" and photo:
        await _handle_admin_file_upload(bot, user, photo, message, state, db)
        return

    # state ادمین (متن)
    if is_admin(bale_id) and state.get("step", "").startswith("admin_"):
        await process_admin_state(bot, user, text, state, db)
        return

    # منوی اصلی
    if text and text.startswith("/start"):
        clear_state(bale_id)
        parts = text.split()
        if len(parts) > 1 and parts[1].startswith("ref_"):
            try:
                ref_parts = parts[1].split("_")
                inviter_id = int(ref_parts[1])
                test_id = int(ref_parts[2]) if len(ref_parts) > 2 else None
                if test_id and inviter_id != user.id:
                    from bot.handlers.tests import handle_referral
                    await handle_referral(bot, user, inviter_id, test_id, db)
            except:
                pass
        from bot.handlers.start import handle_start
        await handle_start(bot, user, db)
    elif text == "🧪جعبه‌ی سیاهِ شخصیت‌شناسی":
        from bot.handlers.tests import show_list
        await show_list(bot, user, db)
    elif text == "📅 رزرو جلسه کوچینگ":
        from bot.handlers.reservation import show_coaching_types
        await show_coaching_types(bot, user, db)
    elif text == "🎓 دوره‌ها و آموزش‌ها":
        from bot.handlers.products import show_courses
        await show_courses(bot, user, db)
    elif text == "🎧 پادکست‌ها":
        from bot.handlers.products import show_podcasts
        await show_podcasts(bot, user, db)
    elif text == "❓ سوالات شما":
        from bot.handlers.static_pages import show_faq
        await show_faq(bot, user, db)
    elif text == "⭐ رضایت مشتریان":
        from bot.handlers.static_pages import show_reviews_content
        await show_reviews_content(bot, user, db)
    elif text == "👤 معرفی من":
        from bot.handlers.static_pages import show_intro
        await show_intro(bot, user, db)
    elif text == "📞 پشتیبانی":
        from bot.handlers.support import start_support
        await start_support(bot, user)
    elif text == "💳 اقساط من":
        from bot.handlers.installment import show_my_installments
        await show_my_installments(bot, user, db)
    elif text == "👤 پروفایل من":
        from bot.handlers.profile import show
        await show(bot, user, db)
    elif text == "⚙️ پنل مدیریت" and is_admin(bale_id):
        from bot.handlers.admin import show_dashboard
        await show_dashboard(bot, user, db)
    else:
        await process_state_input(bot, user, text, state, db)

async def _handle_admin_file_upload(bot: Bot, admin: User, file_obj, message: Message, state: dict, db: Session):
    """استخراج file_id از هر نوع فایل و ذخیره در محتوا"""
    from bot.handlers.admin import sc_save_file
    caption = getattr(message, "caption", "") or ""

    file_id = None
    if hasattr(file_obj, "file_id"):
        file_id = file_obj.file_id
    elif hasattr(file_obj, "id"):
        file_id = str(file_obj.id)
    elif isinstance(file_obj, str):
        file_id = file_obj

    if file_id:
        await sc_save_file(bot, admin, file_id, caption, db)
    else:
        from bot.sender import send_message
        await send_message(bot, admin.bale_id, "❌ فایل دریافت نشد. دوباره امتحان کن.")

async def process_admin_state(bot: Bot, admin: User, text: str, state: dict, db: Session):
    step = state.get("step")
    from bot.handlers import admin as admin_handler
    if step == "admin_search_user":
        await admin_handler.search_user(bot, admin, text, db)
    elif step == "admin_direct_msg":
        await admin_handler.send_direct_message(bot, admin, text, db)
    elif step == "admin_broadcast":
        await admin_handler.send_broadcast(bot, admin, text, db)
    elif step == "admin_slot_datetime":
        await admin_handler.add_time_slot(bot, admin, text, db)
    elif step == "admin_slot_pkg_title":
        await admin_handler.slot_set_pkg_title(bot, admin, text)
    elif step == "admin_slot_pkg_sessions":
        await admin_handler.slot_set_pkg_sessions(bot, admin, text)
    elif step == "admin_slot_pkg_duration":
        await admin_handler.slot_set_pkg_duration(bot, admin, text)
    elif step == "admin_slot_pkg_price":
        await admin_handler.slot_set_pkg_price(bot, admin, text, db)
    elif step == "admin_slot_pkg_capacity":
        await admin_handler.slot_set_pkg_capacity(bot, admin, text, db)
    elif step == "admin_new_test_type":
        pass  # این مرحله callback هست نه text
    elif step == "admin_new_test_tone":
        pass  # این مرحله callback هست نه text
    elif step == "admin_add_range":
        await admin_handler.save_new_range(bot, admin, text, db)
    elif step == "admin_update_range":
        await admin_handler.save_update_range(bot, admin, text, db)
    elif step == "admin_test_order":
        await admin_handler.save_test_order(bot, admin, text, db)
    elif step == "admin_test_range_content":
        await admin_handler.save_test_range_content(bot, admin, text, db)
    elif step == "admin_test_content":
        await admin_handler.save_test_content(bot, admin, text, db)
    elif step == "admin_edit_channel":
        await admin_handler.save_channel(bot, admin, text, db)
    elif step == "admin_test_importance":
        await admin_handler.save_test_importance(bot, admin, text, db)
    elif step == "admin_add_range":
        await admin_handler.save_new_range(bot, admin, text, db)
    elif step == "admin_update_range":
        await admin_handler.save_update_range(bot, admin, text, db)
    elif step == "admin_test_order":
        await admin_handler.save_test_order(bot, admin, text, db)
    elif step == "admin_test_range_content":
        await admin_handler.save_test_range_content(bot, admin, text, db)
    elif step == "admin_test_content":
        await admin_handler.save_test_content(bot, admin, text, db)
    elif step == "admin_edit_channel":
        await admin_handler.save_channel(bot, admin, text, db)
    elif step == "test_waiting_receipt":
        pass  # photo handler handles this
    elif step == "admin_new_test":
        await admin_handler.create_new_test(bot, admin, text, db)
    elif step == "admin_add_score_range":
        await admin_handler.add_score_range(bot, admin, text, db)
    elif step == "admin_discount_code":
        await admin_handler.discount_set_code(bot, admin, text)
    elif step == "admin_discount_amount":
        await admin_handler.discount_set_amount(bot, admin, text)
    elif step == "admin_discount_maxuses":
        await admin_handler.discount_set_maxuses(bot, admin, text, db)
    elif step == "admin_reject_reason":
        from bot.handlers.payment import reject_payment_with_reason
        await reject_payment_with_reason(bot, admin.bale_id, text, db)
    elif step == "admin_installment_first":
        await admin_handler.installment_set_first(bot, admin, text)
    elif step == "admin_installment_count":
        await admin_handler.installment_set_count(bot, admin, text)
    elif step == "admin_installment_details":
        await admin_handler.installment_add_detail(bot, admin, text, db)
    elif step == "admin_inst_first_payment":
        await admin_handler.inst_set_first_payment(bot, admin, text)
    elif step == "admin_inst_count":
        await admin_handler.inst_set_count(bot, admin, text)
    elif step == "admin_inst_details":
        await admin_handler.inst_add_detail(bot, admin, text, db)
    elif step == "admin_reject_installment_reason":
        from bot.handlers.installment import reject_installment_with_reason
        await reject_installment_with_reason(bot, admin.bale_id, text, db)
    elif step == "admin_new_product_title":
        await admin_handler.set_product_title(bot, admin, text)
    elif step == "admin_new_product_price":
        await admin_handler.set_product_price(bot, admin, text, db)
    elif step == "admin_new_product_capacity":
        await admin_handler.set_product_capacity(bot, admin, text, db)
    elif step == "admin_product_link":
        await admin_handler.set_product_link(bot, admin, text, db)
    elif step == "admin_add_question":
        await admin_handler.add_question(bot, admin, text, db)
    elif step == "admin_add_question_analysis":
        await admin_handler.save_question_analysis(bot, admin, text, db)
    elif step == "admin_add_options":
        await admin_handler.add_option(bot, admin, text, db)
    elif step == "admin_add_score_range":
        await admin_handler.add_score_range(bot, admin, text, db)
    elif step == "admin_discount_code":
        await admin_handler.discount_set_code(bot, admin, text)
    elif step == "admin_discount_amount":
        await admin_handler.discount_set_amount(bot, admin, text)
    elif step == "admin_discount_maxuses":
        await admin_handler.discount_set_maxuses(bot, admin, text, db)
    elif step == "admin_reschedule_datetime":
        import jdatetime as jdt
        try:
            res_id = state.get("res_id")
            jalali_dt = jdt.datetime.strptime(text.strip(), "%Y/%m/%d %H:%M")
            gregorian_dt = jalali_dt.togregorian()
            from models.product import TimeSlot, Reservation, ReservationStatus
            res = db.query(Reservation).filter(Reservation.id == res_id).first()
            if res:
                if res.time_slot:
                    res.time_slot.is_available = True
                new_slot = TimeSlot(date=gregorian_dt, is_available=False, package_id=res.package_id)
                db.add(new_slot)
                db.commit()
                db.refresh(new_slot)
                res.time_slot_id = new_slot.id
                res.status = ReservationStatus.rescheduled
                db.commit()
                clear_state(admin.bale_id)
                from bot.sender import send_message as sm2
                await sm2(bot, res.user.bale_id, f"جلسه شما جابجا شد!\nتاریخ جدید: {text.strip()}")
                await sm2(bot, admin.bale_id, f"جابجایی انجام شد: {text.strip()}")
        except Exception as e:
            from bot.sender import send_message as sm2
            await sm2(bot, admin.bale_id, f"خطا: {e}\nمثال: 1404/05/20 16:00")
    elif step == "admin_reject_reason":
        from bot.handlers.payment import reject_payment_with_reason
        await reject_payment_with_reason(bot, admin.bale_id, text, db)
    elif step == "admin_installment_first":
        await admin_handler.installment_set_first(bot, admin, text)
    elif step == "admin_installment_count":
        await admin_handler.installment_set_count(bot, admin, text)
    elif step == "admin_installment_details":
        await admin_handler.installment_add_detail(bot, admin, text, db)
    elif step == "admin_inst_first_payment":
        await admin_handler.inst_set_first_payment(bot, admin, text)
    elif step == "admin_inst_count":
        await admin_handler.inst_set_count(bot, admin, text)
    elif step == "admin_inst_details":
        await admin_handler.inst_add_detail(bot, admin, text, db)
    elif step == "admin_reject_installment_reason":
        from bot.handlers.installment import reject_installment_with_reason
        await reject_installment_with_reason(bot, admin.bale_id, text, db)
    elif step == "admin_edit_welcome":
        await admin_handler.save_welcome_message(bot, admin, text)
    elif step == "admin_edit_card":
        await admin_handler.save_card_number(bot, admin, text)
    elif step == "admin_edit_card_owner":
        await admin_handler.save_card_owner(bot, admin, text)
    elif step == "admin_new_package_title":
        await admin_handler.set_package_title(bot, admin, text)
    elif step == "admin_new_package_sessions":
        await admin_handler.set_package_sessions(bot, admin, text)
    elif step == "admin_new_package_duration":
        await admin_handler.set_package_duration(bot, admin, text)
    elif step == "admin_new_package_price":
        await admin_handler.set_package_price(bot, admin, text, db)
    elif step == "admin_reply_ticket":
        from bot.handlers.support import handle_admin_reply_text
        await handle_admin_reply_text(bot, admin, text)
    # ---- محتوای صفحات ثابت ----
    elif step == "admin_sc_text_input":
        await admin_handler.sc_save_text(bot, admin, text, db)
    elif step == "admin_sc_faq_question":
        await admin_handler.sc_save_faq_question(bot, admin, text)
    elif step == "admin_sc_faq_answer":
        await admin_handler.sc_save_faq_answer(bot, admin, text, db)
    elif step == "admin_sc_link_url":
        await admin_handler.sc_save_link_url(bot, admin, text)
    elif step == "admin_sc_link_label":
        await admin_handler.sc_save_link(bot, admin, text, db)

async def process_state_input(bot: Bot, user: User, text: str, state: dict, db: Session):
    step = state.get("step")
    from bot.sender import send_message
    if step == "waiting_name":
        user.full_name = text
        db.commit()
        set_state(user.bale_id, {"step": "waiting_phone"})
        await send_message(bot, user.bale_id, "ممنون! 📞 شماره موبایلت رو بنویس:")
    elif step == "waiting_phone":
        user.phone = text
        db.commit()
        clear_state(user.bale_id)
        from bot.handlers.start import show_main_menu
        await show_main_menu(bot, user, db)
    elif step == "waiting_support_message":
        from bot.handlers.support import handle_support_message
        await handle_support_message(bot, user, text, db)
    elif step == "payment_waiting_discount":
        from bot.handlers.payment import handle_discount_code
        await handle_discount_code(bot, user, text, db)
    elif step == "waiting_review_text":
        review_id = state.get("review_id")
        clear_state(user.bale_id)
        if text != "/skip" and review_id:
            from models.review import Review
            r = db.query(Review).filter(Review.id == review_id).first()
            if r:
                r.text = text
                db.commit()
        await send_message(bot, user.bale_id, "✅ نظرت ثبت شد. ممنون! 🙏")

async def process_callback(bot: Bot, callback: CallbackQuery, db: Session):
    data = callback.data or ""
    bale_id = str(callback.from_user.user_id)

    user = get_or_create_user(bale_id, callback.from_user, db)
    if user.status == UserStatus.blocked:
        return

    if data.startswith("reply_ticket_") and is_admin(bale_id):
        ticket_id = data.replace("reply_ticket_", "")
        from bot.handlers.support import handle_admin_reply_callback
        await handle_admin_reply_callback(bot, user, ticket_id)

    elif data.startswith("admin_") and is_admin(bale_id):
        from bot.handlers.admin import handle_admin_action
        await handle_admin_action(bot, user, data, db)

    # ==================== تست ====================
    elif data.startswith("test_") and not data.startswith("test_results"):
        from bot.handlers.tests import show_test_intro
        await show_test_intro(bot, user, int(data.split("_")[1]), db)
    elif data.startswith("start_test_"):
        from bot.handlers.tests import start_test
        await start_test(bot, user, int(data.split("_")[-1]), db)
    elif data.startswith("answer_"):
        _, test_id, question_id, option_id = data.split("_")
        from bot.handlers.tests import handle_answer
        await handle_answer(bot, user, int(test_id), int(question_id), int(option_id), db)
    elif data.startswith("next_question_"):
        parts = data.split("_")
        test_id, question_id = int(parts[2]), int(parts[3])
        from bot.handlers.tests import handle_next_question
        await handle_next_question(bot, user, test_id, question_id, db)
    elif data.startswith("finish_test_"):
        test_id = int(data.split("_")[-1])
        from bot.handlers.tests import handle_finish_test
        await handle_finish_test(bot, user, test_id, db)

    # ==================== رزرو ====================
    elif data.startswith("buy_pkg_"):
        from bot.handlers.reservation import confirm_package_purchase
        await confirm_package_purchase(bot, user, int(data.split("_")[-1]), db)
    elif data.startswith("pkg_"):
        from bot.handlers.reservation import show_package_sessions
        await show_package_sessions(bot, user, int(data.split("_")[1]), db)
    elif data.startswith("cal_"):
        _, pkg_id, year, month = data.split("_")
        from bot.handlers.reservation import show_calendar
        await show_calendar(bot, user, int(pkg_id), db, int(year), int(month))
    elif data.startswith("day_"):
        parts = data.split("_")
        from bot.handlers.reservation import show_day_slots
        await show_day_slots(bot, user, int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4]), db)
    elif data.startswith("slot_"):
        parts = data.split("_")
        from bot.handlers.reservation import confirm_slot
        await confirm_slot(bot, user, int(parts[1]), int(parts[2]) if len(parts) > 2 else None, db)
    elif data.startswith("cancel_res_"):
        from bot.handlers.reservation import cancel_reservation_user
        await cancel_reservation_user(bot, user, int(data.split("_")[-1]), db)
    elif data.startswith("confirm_cancel_"):
        parts = data.split("_")
        res_id = int(parts[2])
        is_late = parts[3] == "late"
        from bot.handlers.reservation import do_cancel
        from models.product import Reservation
        res = db.query(Reservation).filter(Reservation.id == res_id, Reservation.user_id == user.id).first()
        if res:
            await do_cancel(bot, user, res, db, is_late)

    # ==================== پرداخت ====================
    elif data.startswith("pay_"):
        from bot.handlers.payment import show_payment_info
        await show_payment_info(bot, user, int(data.split("_")[1]), db)

    # ==================== محصولات ====================
    elif data.startswith("product_"):
        from bot.handlers.products import show_product
        await show_product(bot, user, int(data.split("_")[1]), db)

    # ==================== پروفایل ====================
    elif data == "my_tests":
        from bot.handlers.profile import show_my_tests
        await show_my_tests(bot, user, db)
    elif data == "my_reservations":
        from bot.handlers.profile import show_my_reservations
        await show_my_reservations(bot, user, db)
    elif data == "my_courses":
        from bot.handlers.profile import show_my_courses
        await show_my_courses(bot, user, db)
    elif data == "my_cancel_res":
        from bot.handlers.reservation import show_my_reservations_for_cancel
        await show_my_reservations_for_cancel(bot, user, db)

    # ==================== ناوبری ====================
    elif data == "my_installments":
        from bot.handlers.installment import show_my_installments
        await show_my_installments(bot, user, db)
    elif data.startswith("show_result_after_join_"):
        from bot.handlers.tests import show_result_after_join
        await show_result_after_join(bot, user, int(data.split("_")[-1]), db)
    elif data.startswith("check_join_"):
        from bot.handlers.tests import show_test_intro
        await show_test_intro(bot, user, int(data.split("_")[-1]), db)
    elif data.startswith("invite_test_"):
        from bot.handlers.tests import show_invite_link
        await show_invite_link(bot, user, int(data.split("_")[-1]), db)
    elif data.startswith("pay_test_receipt_"):
        from bot.handlers.tests import handle_pay_test_receipt
        await handle_pay_test_receipt(bot, user, int(data.split("_")[-1]), db)
    elif data.startswith("buy_test_"):
        from bot.handlers.tests import handle_pay_test_receipt
        await handle_pay_test_receipt(bot, user, int(data.split("_")[-1]), db)
    elif data.startswith("pay_installment_plan_"):
        # پرداخت اولیه اقساطی: pay_installment_plan_{plan_id}_{payment_id}
        parts = data.split("_")
        plan_id = int(parts[3])
        payment_id = int(parts[4])
        from models.installment import InstallmentPlan, Installment
        from bot.handlers.payment import show_payment_card
        plan = db.query(InstallmentPlan).filter(InstallmentPlan.id == plan_id).first()
        if plan:
            from models.payment import Payment
            p = db.query(Payment).filter(Payment.id == payment_id).first()
            if p:
                p.amount = plan.first_payment
                db.commit()
            await show_payment_card(bot, user, payment_id, db)
    elif data.startswith("pay_installment_"):
        from bot.handlers.installment import start_installment_payment
        await start_installment_payment(bot, user, int(data.split("_")[-1]), db)
    elif data == "payment_enter_discount":
        from bot.handlers.payment import handle_enter_discount
        await handle_enter_discount(bot, user)
    elif data == "payment_no_discount":
        from bot.handlers.payment import handle_no_discount
        await handle_no_discount(bot, user, db)
    elif data == "goto_main":
        from bot.handlers.start import show_main_menu
        await show_main_menu(bot, user, db)
    elif data == "goto_reservation":
        from bot.handlers.reservation import show_coaching_types
        await show_coaching_types(bot, user, db)
    elif data.startswith("coaching_type_"):
        stype = data.replace("coaching_type_", "")
        from bot.handlers.reservation import show_packages
        await show_packages(bot, user, db, session_type=stype)
    elif data == "goto_tests":
        from bot.handlers.tests import show_list
        await show_list(bot, user, db)
    elif data == "goto_support":
        from bot.handlers.support import start_support
        await start_support(bot, user)

    # ==================== نظرات ====================
    elif data.startswith("review_test_"):
        parts = data.split("_")
        await save_review(bot, user, test_id=int(parts[2]), score=float(parts[3]), db=db)

    # noop — دکمه‌های تزئینی
    elif data.startswith("noop_"):
        pass

async def save_review(bot: Bot, user: User, score: float, db: Session, test_id=None, product_id=None):
    from models.review import Review
    from bot.sender import send_message
    review = Review(user_id=user.id, test_id=test_id, product_id=product_id, score=score)
    db.add(review)
    db.commit()
    set_state(user.bale_id, {"step": "waiting_review_text", "review_id": review.id})
    await send_message(bot, user.bale_id, f"ممنون! امتیاز {score}/5 ثبت شد ⭐\nیه نظر هم بنویس (یا /skip بزن):")

def get_or_create_user(bale_id: str, from_user, db: Session) -> User:
    user = db.query(User).filter(User.bale_id == bale_id).first()
    if not user:
        full_name = ""
        if hasattr(from_user, "first_name"):
            full_name = (from_user.first_name or "") + " " + (from_user.last_name or "")
        user = User(bale_id=bale_id, username=getattr(from_user, "username", None),
                    full_name=full_name.strip() or None)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user
