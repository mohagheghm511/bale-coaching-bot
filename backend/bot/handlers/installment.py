"""
bot/handlers/installment.py
مدیریت اقساط کاربر
"""
from sqlalchemy.orm import Session
from models.user import User
from models.installment import InstallmentPlan, Installment, UserInstallment
from models.payment import Payment, PaymentStatus, PaymentMethod
from bale import Bot
from bot.sender import send_message, inline_keyboard, notify_admins
from bot.dispatcher import get_state, set_state, clear_state
import uuid


def _gen_tracking():
    return str(uuid.uuid4())[:8].upper()


# ==================== نمایش اقساط کاربر ====================

async def show_my_installments(bot: Bot, user: User, db: Session):
    items = (
        db.query(UserInstallment)
        .filter(UserInstallment.user_id == user.id, UserInstallment.status == "pending")
        .all()
    )
    if not items:
        await send_message(bot, user.bale_id, "✅ قسط پرداخت‌نشده‌ای ندارید.")
        return

    await send_message(bot, user.bale_id, f"📋 اقساط در انتظار پرداخت: {len(items)} قسط")
    for ui in items:
        inst = ui.installment if hasattr(ui, 'installment') else db.query(Installment).filter(Installment.id == ui.installment_id).first()
        plan = db.query(InstallmentPlan).filter(InstallmentPlan.id == ui.plan_id).first()
        if not inst or not plan:
            continue
        due = inst.due_date.strftime("%Y/%m/%d") if inst.due_date else "-"
        product_name = ""
        if plan.product_id:
            from models.product import Product
            p = db.query(Product).filter(Product.id == plan.product_id).first()
            product_name = p.title if p else ""
        elif plan.package_id:
            from models.product import CoachingPackage
            p = db.query(CoachingPackage).filter(CoachingPackage.id == plan.package_id).first()
            product_name = p.title if p else ""

        msg = (
            f"📦 {product_name}\n"
            f"💰 قسط {inst.number}: {inst.amount:,} تومان\n"
            f"📅 سررسید: {due}"
        )
        await send_message(bot, user.bale_id, msg, reply_markup=inline_keyboard([
            [{"text": f"💳 پرداخت قسط {inst.number}", "callback_data": f"pay_installment_{ui.id}"}],
        ]))


# ==================== پرداخت یک قسط ====================

async def start_installment_payment(bot: Bot, user: User, ui_id: int, db: Session):
    ui = db.query(UserInstallment).filter(UserInstallment.id == ui_id, UserInstallment.user_id == user.id).first()
    if not ui:
        return
    inst = db.query(Installment).filter(Installment.id == ui.installment_id).first()
    if not inst:
        return

    from bot.handlers.admin import bot_settings
    card = bot_settings.get("card_number", "")
    owner = bot_settings.get("card_owner", "")
    card_text = f"💳 شماره کارت: {card}"
    if owner:
        card_text += f"\n👤 به نام: {owner}"

    tracking = _gen_tracking()
    set_state(user.bale_id, {
        "step": "installment_waiting_receipt",
        "ui_id": ui_id,
        "amount": inst.amount,
        "tracking": tracking,
        "inst_number": inst.number,
    })

    await send_message(bot, user.bale_id,
        f"💳 پرداخت قسط {inst.number}\n━━━━━━━━━━━━━\n"
        f"{card_text}\n━━━━━━━━━━━━━\n"
        f"💰 مبلغ: {inst.amount:,} تومان\n"
        f"🔖 کد پیگیری: {tracking}\n\n"
        f"بعد از واریز عکس فیش را ارسال کن 👇")


async def handle_installment_receipt(bot: Bot, user: User, photo, db: Session):
    state = get_state(user.bale_id)
    ui_id = state.get("ui_id")
    amount = state.get("amount", 0)
    tracking = state.get("tracking", _gen_tracking())
    inst_number = state.get("inst_number", 1)

    file_id = getattr(photo, "file_id", None) or str(photo)

    payment = Payment(
        user_id=user.id,
        amount=amount,
        method=PaymentMethod.card_transfer,
        status=PaymentStatus.uploaded,
        tracking_code=tracking,
        receipt_image=file_id,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    # لینک پرداخت به UserInstallment
    ui = db.query(UserInstallment).filter(UserInstallment.id == ui_id).first()
    if ui:
        ui.payment_id = payment.id
    db.commit()

    clear_state(user.bale_id)

    await send_message(bot, user.bale_id,
        f"✅ فیش قسط {inst_number} دریافت شد.\n🔖 کد پیگیری: {tracking}",
        reply_markup=inline_keyboard([[{"text": "🏠 منو اصلی", "callback_data": "goto_main"}]]))

    await notify_admins(bot,
        f"📸 فیش قسط {inst_number}\n👤 {user.full_name}\n💰 {amount:,} تومان\n🔖 {tracking}",
        reply_markup=inline_keyboard([
            [{"text": "✅ تأیید قسط", "callback_data": f"admin_approve_installment_{ui_id}"},
             {"text": "❌ رد قسط", "callback_data": f"admin_reject_installment_{ui_id}"}],
        ]))


# ==================== تأیید/رد قسط توسط ادمین ====================

async def approve_installment(bot: Bot, ui_id: int, db: Session):
    ui = db.query(UserInstallment).filter(UserInstallment.id == ui_id).first()
    if not ui:
        return
    ui.status = "paid"
    inst = db.query(Installment).filter(Installment.id == ui.installment_id).first()
    if inst:
        inst.status = "paid"
    db.commit()

    await send_message(bot, str(ui.user_id),
        f"✅ قسط {inst.number if inst else ''} شما تأیید شد!\nممنون از پرداخت 🙏",
        reply_markup=inline_keyboard([
            [{"text": "📋 اقساط بعدی", "callback_data": "my_installments"}],
            [{"text": "🏠 منو اصلی", "callback_data": "goto_main"}],
        ]))


async def prompt_reject_installment(bot: Bot, admin_bale_id: str, ui_id: int):
    set_state(admin_bale_id, {"step": "admin_reject_installment_reason", "ui_id": ui_id})
    await send_message(bot, admin_bale_id, "📝 دلیل رد قسط را بنویس:")


async def reject_installment_with_reason(bot: Bot, admin_bale_id: str, reason: str, db: Session):
    state = get_state(admin_bale_id)
    ui_id = state.get("ui_id")
    clear_state(admin_bale_id)

    ui = db.query(UserInstallment).filter(UserInstallment.id == ui_id).first()
    if not ui:
        return
    ui.status = "pending"
    ui.payment_id = None
    db.commit()

    inst = db.query(Installment).filter(Installment.id == ui.installment_id).first()
    user = db.query(db.bind and __builtins__ or None)
    from models.user import User
    usr = db.query(User).filter(User.id == ui.user_id).first()
    if usr:
        await send_message(bot, usr.bale_id,
            f"❌ فیش قسط {inst.number if inst else ''} رد شد.\n📝 دلیل: {reason}\n\nمجدداً پرداخت کنید.",
            reply_markup=inline_keyboard([
                [{"text": f"💳 پرداخت مجدد", "callback_data": f"pay_installment_{ui_id}"}],
            ]))
    await send_message(bot, admin_bale_id, "✅ دلیل رد ارسال شد.")


# ==================== ثبت خرید قسطی ====================

async def create_user_installments(user_id: int, plan_id: int, db: Session):
    """ساخت UserInstallment برای همه اقساط یک پلن"""
    plan = db.query(InstallmentPlan).filter(InstallmentPlan.id == plan_id).first()
    if not plan:
        return
    installments = db.query(Installment).filter(Installment.plan_id == plan_id).order_by(Installment.number).all()
    for inst in installments:
        ui = UserInstallment(user_id=user_id, plan_id=plan_id, installment_id=inst.id)
        db.add(ui)
    db.commit()
