from sqlalchemy.orm import Session
from models.user import User
from models.test import Test, Question, Option, TestResult, ScoreRange
from bale import Bot
from bot.sender import send_message, inline_keyboard
from bot.dispatcher import get_state, set_state, clear_state


def _get_channel_id(db):
    try:
        from sqlalchemy import text as sqlt
        r = db.execute(sqlt("SELECT value FROM bot_settings WHERE key='force_channel'")).fetchone()
        return r[0] if r and r[0] else None
    except:
        return None


async def _check_channel_membership(bot, user_bale_id, channel_id):
    """چک عضویت در کانال"""
    if not channel_id:
        return True
    try:
        member = await bot.get_chat_member(channel_id, user_bale_id)
        return member is not None
    except:
        return False


# ==================== لیست تست‌ها ====================

async def show_list(bot: Bot, user: User, db: Session):
    tests = db.query(Test).filter(Test.is_active == True).order_by(Test.order).all()
    if not tests:
        await send_message(bot, user.bale_id, "در حال حاضر تستی موجود نیست.")
        return
    buttons = []
    for t in tests:
        access = getattr(t, 'access_type', 'free') or 'free'
        if access == 'free':
            tag = "🆓 رایگان"
            icon = "🔵"
        elif access == 'invite':
            tag = "🎁 دعوت از ۲ نفر"
            icon = "🟡"
        else:
            tag = f"💰 {t.price:,} تومان"
            icon = "🟣"
        buttons.append([{"text": f"{icon} {t.title} — {tag}", "callback_data": f"test_{t.id}"}])
    await send_message(bot, user.bale_id, "تست مورد نظرت رو انتخاب کن 👇", reply_markup=inline_keyboard(buttons))


async def show_test_intro(bot: Bot, user: User, test_id: int, db: Session):
    test = db.query(Test).filter(Test.id == test_id).first()
    if not test:
        return
    importance = getattr(test, 'importance', None)
    if importance:
        msg = f"\U0001F9EA {test.title}\n\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\U0001F4CC \u0627\u0647\u0645\u06CC\u062A \u0627\u06CC\u0646 \u062A\u0633\u062A:\n\n{importance}\n\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
    else:
        msg = f"\U0001F9EA {test.title}\n\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\u0622\u0645\u0627\u062F\u0647\u200C\u0627\u06CC \u0634\u0631\u0648\u0639 \u06A9\u0646\u06CC\u061F"
    buttons = [
        [{"text": "\u25B6\uFE0F \u0634\u0631\u0648\u0639 \u062A\u0633\u062A", "callback_data": f"start_test_{test_id}"}],
        [{"text": "\U0001F519 \u0628\u0627\u0632\u06AF\u0634\u062A", "callback_data": "goto_tests"}],
    ]
    await send_message(bot, user.bale_id, msg, reply_markup=inline_keyboard(buttons))

def _get_invite_count(user_id, test_id, db):
    try:
        from sqlalchemy import text as sqlt
        r = db.execute(sqlt("SELECT COUNT(*) FROM test_invites WHERE inviter_user_id=:u AND test_id=:t"),
                       {"u": user_id, "t": test_id}).fetchone()
        return r[0] if r else 0
    except:
        return 0


def _has_paid_for_test(user_id, test_id, db):
    try:
        from sqlalchemy import text as sqlt
        r = db.execute(sqlt("SELECT COUNT(*) FROM payments WHERE user_id=:u AND product_id=:t AND status='approved'"),
                       {"u": user_id, "t": test_id}).fetchone()
        return (r[0] if r else 0) > 0
    except:
        return False


async def show_invite_link(bot, user, test_id, db):
    from core.config import settings
    bot_username = getattr(settings, 'bot_username', 'Drsaeideh123bot')
    link = f"https://ble.ir/{bot_username}?start=ref_{user.id}_{test_id}"
    invite_count = _get_invite_count(user.id, test_id, db)
    remaining = 2 - invite_count
    if invite_count >= 2:
        status = "قفل باز شد!"
    else:
        status = f"{remaining} نفر دیگه لازمه"
    # پیام اول: توضیح
    info_msg = (
        "برای دیدن نتیجه تست، پیام زیر را برای ۲ نفر فوروارد کن.\n"
        "به محض اینکه دوستات وارد بشن، نتیجه همین‌جا برات میاد.\n\n"
        f"حالت: {invite_count}/2 — {status}"
    )
    buttons = []
    if invite_count >= 2:
        buttons.append([{"text": "شروع تست", "callback_data": f"start_test_{test_id}"}])
    buttons.append([{"text": "بررسی مجدد", "callback_data": f"invite_test_{test_id}"}])
    buttons.append([{"text": "بازگشت", "callback_data": f"test_{test_id}"}])
    await send_message(bot, user.bale_id, info_msg, reply_markup=inline_keyboard(buttons))

    # پیام دوم: قابل فوروارد
    if invite_count < 2:
        share_msg = (
            "بیا تست شخصیت‌شناسی بده، تحلیلش عالیه! 🧠✨\n\n"
            f"{link}"
        )
        await send_message(bot, user.bale_id, share_msg)

async def handle_referral(bot: Bot, new_user: User, inviter_id: int, test_id: int, db: Session):
    """ثبت دعوت و چک قفل"""
    try:
        from sqlalchemy import text as sqlt
        # چک تکراری نبودن
        r = db.execute(sqlt("SELECT COUNT(*) FROM test_invites WHERE inviter_user_id=:inv AND invited_user_id=:new AND test_id=:t"),
                       {"inv": inviter_id, "new": new_user.id, "t": test_id}).fetchone()
        if r and r[0] > 0:
            return
        db.execute(sqlt("INSERT INTO test_invites (inviter_user_id, invited_user_id, test_id) VALUES (:inv, :new, :t)"),
                   {"inv": inviter_id, "new": new_user.id, "t": test_id})
        db.commit()
        # چک قفل
        count = _get_invite_count(inviter_id, test_id, db)
        if count >= 2:
            inviter = db.query(User).filter(User.id == inviter_id).first()
            if inviter:
                await send_message(bot, inviter.bale_id,
                    f"🎉 قفل باز شد! ۳ نفر با لینک شما وارد ربات شدن.\n"
                    f"الان می‌تونی تست رو شروع کنی 👇",
                    reply_markup=inline_keyboard([
                        [{"text": "▶️ شروع تست", "callback_data": f"start_test_{test_id}"}],
                    ]))
    except Exception as e:
        print(f"referral error: {e}")


async def handle_pay_test_receipt(bot: Bot, user: User, test_id: int, db: Session):
    """شروع پرداخت با فیش برای تست پولی"""
    test = db.query(Test).filter(Test.id == test_id).first()
    if not test:
        return
    from bot.handlers.admin import bot_settings
    card = bot_settings.get("card_number", "")
    owner = bot_settings.get("card_owner", "")
    if not card:
        try:
            from sqlalchemy import text as sqlt
            r = db.execute(sqlt("SELECT value FROM bot_settings WHERE key='card_number'")).fetchone()
            if r and r[0]: card = r[0]
            r2 = db.execute(sqlt("SELECT value FROM bot_settings WHERE key='card_owner'")).fetchone()
            if r2 and r2[0]: owner = r2[0]
        except: pass
    card_text = f"💳 {card}" if card else "💳 شماره کارت در تنظیمات ادمین ثبت نشده."
    if owner:
        card_text += f"\n👤 به نام: {owner}"

    set_state(user.bale_id, {"step": "test_waiting_receipt", "test_id": test_id})
    await send_message(bot, user.bale_id,
        f"💰 هزینه تست: {test.price:,} تومان\n━━━━━━━━━━━━━\n{card_text}\n\nبعد از واریز، عکس فیش را ارسال کن 👇")


async def handle_test_receipt(bot: Bot, user: User, photo, db: Session):
    """دریافت فیش تست"""
    state = get_state(user.bale_id)
    test_id = state.get("test_id")
    clear_state(user.bale_id)

    file_id = getattr(photo, "file_id", None) or str(photo)
    test = db.query(Test).filter(Test.id == test_id).first()

    # ذخیره پرداخت با product_id = test_id
    import uuid
    tracking = "T" + str(uuid.uuid4()).replace("-", "")[:9].upper()
    from models.payment import Payment, PaymentStatus, PaymentMethod
    payment = Payment(
        user_id=user.id,
        product_id=test_id,
        amount=test.price if test else 0,
        method=PaymentMethod.card_transfer,
        status=PaymentStatus.uploaded,
        tracking_code=tracking,
        receipt_image=file_id,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    await send_message(bot, user.bale_id,
        f"✅ فیش دریافت شد.\n🔖 {tracking}\nبعد از تأیید ادمین، تست برات باز میشه.",
        reply_markup=inline_keyboard([[{"text": "🏠 منو اصلی", "callback_data": "goto_main"}]]))

    # ارسال برای ادمین
    from core.config import settings
    for admin_id in settings.admin_ids:
        try:
            await bot.send_document(admin_id, file_id,
                caption=f"📸 فیش تست\n👤 {user.full_name}\n🧪 {test.title if test else '-'}\n💰 {test.price:,} تومان\n🔖 {tracking}")
            await send_message(bot, admin_id, "انتخاب کن:", reply_markup=inline_keyboard([
                [{"text": "✅ تأیید", "callback_data": f"admin_approve_pay_{payment.id}"},
                 {"text": "❌ رد", "callback_data": f"admin_reject_pay_{payment.id}"}],
            ]))
        except Exception as e:
            print(f"notify error: {e}")


# ==================== شروع تست ====================

async def start_test(bot: Bot, user: User, test_id: int, db: Session):
    test = db.query(Test).filter(Test.id == test_id).first()
    if not test:
        return
    questions = test.questions
    if not questions:
        await send_message(bot, user.bale_id, "این تست هنوز سوالی نداره.")
        return
    set_state(user.bale_id, {"step": "taking_test", "test_id": test_id, "question_index": 0, "answers": {}})
    await send_question(bot, user, questions[0])


# ==================== نمایش سوال ====================

async def send_question(bot: Bot, user: User, question: Question):
    total = len(question.test.questions)
    header = f"📝 سوال {question.order + 1} از {total}\n━━━━━━━━━━━━━\n{question.text}"
    buttons = [
        [{"text": opt.text, "callback_data": f"answer_{question.test_id}_{question.id}_{opt.id}"}]
        for opt in question.options
    ]
    await send_message(bot, user.bale_id, header, reply_markup=inline_keyboard(buttons))


# ==================== پردازش جواب ====================

async def handle_answer(bot: Bot, user: User, test_id: int, question_id: int, option_id: int, db: Session):
    state = get_state(user.bale_id)
    if not state or state.get("step") != "taking_test":
        return
    state["answers"][str(question_id)] = option_id
    state["question_index"] += 1
    test = db.query(Test).filter(Test.id == test_id).first()
    questions = test.questions
    is_last = state["question_index"] >= len(questions)
    if is_last:
        clear_state(user.bale_id)
        await calculate_result(bot, user, test, state["answers"], db)
    else:
        set_state(user.bale_id, state)
        await send_question(bot, user, questions[state["question_index"]])


async def handle_next_question(bot: Bot, user: User, test_id: int, question_id: int, db: Session):
    state = get_state(user.bale_id)
    if not state or state.get("step") != "taking_test":
        return
    question = db.query(Question).filter(Question.id == question_id).first()
    if question:
        await send_question(bot, user, question)


async def handle_finish_test(bot: Bot, user: User, test_id: int, db: Session):
    state = get_state(user.bale_id)
    if not state or state.get("step") != "taking_test":
        return
    test = db.query(Test).filter(Test.id == test_id).first()
    answers = state.get("answers", {})
    clear_state(user.bale_id)
    await calculate_result(bot, user, test, answers, db)


# ==================== محاسبه نتیجه ====================

async def calculate_result(bot: Bot, user: User, test: Test, answers: dict, db: Session):
    analysis_type = getattr(test, 'analysis_type', 'numeric') or 'numeric'
    tone = getattr(test, 'tone', 'friendly') or 'friendly'

    if analysis_type == 'typology':
        result_title, result_analysis, extra = _calc_typology(test, answers, db)
        total_score = 0
    elif analysis_type == 'combined':
        result_title, result_analysis, extra, total_score = _calc_combined(test, answers, db)
    else:
        result_title, result_analysis, extra, total_score = _calc_numeric(test, answers, db)

    result = TestResult(
        user_id=user.id, test_id=test.id, answers=answers,
        total_score=total_score, result_title=result_title, result_analysis=result_analysis
    )
    db.add(result)
    db.commit()

    # چک دسترسی (دعوتی/پولی) قبل از نمایش نتیجه
    access = getattr(test, 'access_type', 'free') or 'free'
    if access == 'invite' and _get_invite_count(user.id, test.id, db) < 2 and not _has_paid_for_test(user.id, test.id, db):
        import json
        set_state(user.bale_id, {
            "step": "test_done_locked",
            "test_id": test.id,
            "pending_result": {
                "title": result_title, "analysis": result_analysis,
                "score": total_score, "analysis_type": analysis_type,
                "tone": tone, "extra": extra,
            }
        })
        invite_count = _get_invite_count(user.id, test.id, db)
        await send_message(bot, user.bale_id,
            f"تست تموم شد! برای دیدن نتیجه باید ۲ نفر دعوت کنی.\n📊 {invite_count}/2",
            reply_markup=inline_keyboard([
                [{"text": "🎁 دعوت از ۲ نفر", "callback_data": f"invite_test_{test.id}"}],
                [{"text": "💳 مشاهده فوری (پرداخت)", "callback_data": f"pay_test_receipt_{test.id}"}],
            ]))
        return
    if access == 'paid' and not _has_paid_for_test(user.id, test.id, db):
        set_state(user.bale_id, {
            "step": "test_done_locked",
            "test_id": test.id,
            "pending_result": {
                "title": result_title, "analysis": result_analysis,
                "score": total_score, "analysis_type": analysis_type,
                "tone": tone, "extra": extra,
            }
        })
        await send_message(bot, user.bale_id,
            f"تست تموم شد! برای دیدن نتیجه باید هزینه رو پرداخت کنی.\n💰 {test.price:,} تومان",
            reply_markup=inline_keyboard([
                [{"text": "📸 ارسال عکس فیش واریزی", "callback_data": f"pay_test_receipt_{test.id}"}],
            ]))
        return

    # چک عضویت کانال قبل از نمایش نتیجه
    channel_id = _get_channel_id(db)
    if channel_id:
        is_member = await _check_channel_membership(bot, user.bale_id, channel_id)
        if not is_member:
            # ذخیره نتیجه موقت
            import json
            set_state(user.bale_id, {
                "step": "waiting_channel_join",
                "test_id": test.id,
                "pending_result": {
                    "title": result_title,
                    "analysis": result_analysis,
                    "score": total_score,
                    "analysis_type": analysis_type,
                    "tone": tone,
                    "extra": extra,
                }
            })
            await send_message(bot, user.bale_id,
                f"تست تموم شد! برای دیدن نتیجه باید عضو کانال ما بشی 👇\n{channel_id}",
                reply_markup=inline_keyboard([
                    [{"text": "✅ عضو شدم، نتیجه رو نشون بده", "callback_data": f"show_result_after_join_{test.id}"}],
                ]))
            return

    msg = _format_result(test, result_title, result_analysis, total_score, analysis_type, tone, extra)
    await send_message(bot, user.bale_id, msg, reply_markup=inline_keyboard([
        [{"text": "📅 رزرو جلسه بر اساس نتیجه", "callback_data": "goto_reservation"}],
        [{"text": "🔄 تست دیگری بده", "callback_data": "goto_tests"}],
    ]))

    await suggest_podcasts(bot, user, db)
    await request_review(bot, user, test_id=test.id, db=db)


def _calc_numeric(test, answers, db):
    total_score = 0
    for question_id, option_id in answers.items():
        option = db.query(Option).filter(Option.id == option_id).first()
        if option:
            total_score += option.score
    score_range = db.query(ScoreRange).filter(
        ScoreRange.test_id == test.id,
        ScoreRange.min_score <= total_score,
        ScoreRange.max_score >= total_score
    ).first()
    title = score_range.title if score_range else "نتیجه"
    analysis = score_range.analysis if score_range else "تحلیل در حال آماده‌سازی است."
    return title, analysis, None, total_score


def _calc_typology(test, answers, db):
    from collections import Counter
    type_counts = Counter()
    for question_id, option_id in answers.items():
        option = db.query(Option).filter(Option.id == option_id).first()
        if option and getattr(option, 'type_label', None):
            type_counts[option.type_label] += 1
    if not type_counts:
        return "نامشخص", "اطلاعات کافی برای تحلیل تیپ وجود ندارد.", None
    dominant_type = type_counts.most_common(1)[0][0]
    score_range = db.query(ScoreRange).filter(
        ScoreRange.test_id == test.id,
        ScoreRange.title == dominant_type
    ).first()
    analysis = score_range.analysis if score_range else f"تیپ {dominant_type} شما."
    extra = {"type_counts": dict(type_counts), "dominant": dominant_type}
    return dominant_type, analysis, extra


def _calc_combined(test, answers, db):
    total_score = 0
    from collections import Counter
    type_counts = Counter()
    for question_id, option_id in answers.items():
        option = db.query(Option).filter(Option.id == option_id).first()
        if option:
            total_score += option.score
            if getattr(option, 'type_label', None):
                type_counts[option.type_label] += 1
    score_range = db.query(ScoreRange).filter(
        ScoreRange.test_id == test.id,
        ScoreRange.min_score <= total_score,
        ScoreRange.max_score >= total_score
    ).first()
    title = score_range.title if score_range else "نتیجه"
    analysis = score_range.analysis if score_range else "تحلیل در حال آماده‌سازی است."
    dominant_type = type_counts.most_common(1)[0][0] if type_counts else None
    extra = {"type_counts": dict(type_counts), "dominant": dominant_type}
    return title, analysis, extra, total_score


def _format_result(test, title, analysis, score, analysis_type, tone, extra):
    greeting = "عزیزم" if tone == 'friendly' else ""
    if analysis_type == 'numeric':
        score_line = f"📊 امتیاز شما: {score:.1f}\n"
    elif analysis_type == 'typology':
        dominant = extra.get('dominant', '') if extra else ''
        score_line = f"🔤 تیپ غالب شما: {dominant}\n"
    else:
        score_line = f"📊 امتیاز: {score:.1f}\n"
        if extra and extra.get('dominant'):
            score_line += f"🔤 تیپ غالب: {extra['dominant']}\n"
    msg = (
        f"✅ تست «{test.title}» تموم شد! {greeting}\n"
        f"━━━━━━━━━━━━━\n"
        f"{score_line}"
        f"🔹 نتیجه: {title}\n\n"
        f"📝 تحلیل:\n{analysis}"
    )
    return msg


async def suggest_podcasts(bot: Bot, user: User, db: Session):
    from models.product import Product, ProductType
    podcasts = db.query(Product).filter(
        Product.type == ProductType.podcast, Product.is_active == True, Product.price == 0
    ).order_by(Product.order).limit(10).all()
    if not podcasts:
        return
    await send_message(bot, user.bale_id, "🎧 پادکست‌های رایگان که می‌تونه کمکت کنه:\n━━━━━━━━━━━━━")
    for p in podcasts:
        title = (p.title or "").replace("*", "").replace("_", "").replace("`", "").strip()
        desc = f"📌 {title}"
        if p.link:
            if p.link.startswith("http"):
                desc += f"\n🔗 {p.link}"
            else:
                desc += f"\n{p.link.replace('*', '').replace('_', '')}"
        try:
            await send_message(bot, user.bale_id, desc)
        except Exception as e:
            print(f"podcast send error {p.id}: {e}")
            try:
                await send_message(bot, user.bale_id, f"📌 {title}")
            except:
                pass


async def request_review(bot: Bot, user: User, test_id: int, db: Session):
    await send_message(bot, user.bale_id,
        "از تست چقدر رضایت داشتی؟\nاز ۱ تا ۵ امتیاز بده:",
        reply_markup=inline_keyboard([[
            {"text": "⭐️ ۱", "callback_data": f"review_test_{test_id}_1"},
            {"text": "⭐️ ۲", "callback_data": f"review_test_{test_id}_2"},
            {"text": "⭐️ ۳", "callback_data": f"review_test_{test_id}_3"},
            {"text": "⭐️ ۴", "callback_data": f"review_test_{test_id}_4"},
            {"text": "⭐️ ۵", "callback_data": f"review_test_{test_id}_5"},
        ]]))


async def show_result_after_join(bot, user, test_id, db):
    """نمایش نتیجه بعد از عضویت در کانال"""
    channel_id = _get_channel_id(db)
    if channel_id:
        is_member = await _check_channel_membership(bot, user.bale_id, channel_id)
        if not is_member:
            await send_message(bot, user.bale_id,
                "هنوز عضو کانال نشدی! لطفاً اول عضو بشو بعد دوباره بزن.")
            return

    state = get_state(user.bale_id)
    pending = state.get("pending_result")
    clear_state(user.bale_id)

    if not pending:
        await send_message(bot, user.bale_id, "نتیجه‌ای پیدا نشد. لطفاً تست رو دوباره بگیر.")
        return

    test = db.query(Test).filter(Test.id == test_id).first()
    result_title = pending["title"]
    result_analysis = pending["analysis"]
    total_score = pending["score"]
    analysis_type = pending.get("analysis_type", "numeric")
    tone = pending.get("tone", "friendly")
    extra = pending.get("extra")

    # ذخیره نتیجه
    result = TestResult(
        user_id=user.id, test_id=test_id,
        answers={}, total_score=total_score,
        result_title=result_title, result_analysis=result_analysis
    )
    db.add(result)
    db.commit()

    msg = _format_result(test, result_title, result_analysis, total_score, analysis_type, tone, extra)
    await send_message(bot, user.bale_id, msg, reply_markup=inline_keyboard([
        [{"text": "📅 رزرو جلسه بر اساس نتیجه", "callback_data": "goto_reservation"}],
        [{"text": "🔄 تست دیگری بده", "callback_data": "goto_tests"}],
    ]))
    await suggest_podcasts(bot, user, db)
    await request_review(bot, user, test_id=test_id, db=db)