from bale import Bot
from sqlalchemy.orm import Session
from models.user import User
from models.product import Product, ProductType
from models.payment import Payment, PaymentMethod, PaymentStatus
from bot.sender import send_message, inline_keyboard
import random, string

TYPE_ICONS = {
    "course": "🎓",
    "podcast": "🎧",
    "webinar": "📡",
    "channel": "📢",
    "coaching": "🏋",
}

async def show_courses(bot: Bot, user: User, db: Session):
    await show_by_type(bot, user, db, ProductType.course, "🎓 دوره‌های آموزشی")

async def show_podcasts(bot: Bot, user: User, db: Session):
    await show_by_type(bot, user, db, ProductType.podcast, "🎧 پادکست‌ها")

async def show_webinars(bot: Bot, user: User, db: Session):
    await show_by_type(bot, user, db, ProductType.webinar, "📡 وبینارها")

async def show_channels(bot: Bot, user: User, db: Session):
    await show_by_type(bot, user, db, ProductType.channel, "📢 کانال‌ها")

async def show_by_type(bot: Bot, user: User, db: Session, ptype: ProductType, title: str):
    products = db.query(Product).filter(
        Product.type == ptype,
        Product.is_active == True
    ).order_by(Product.order).all()

    if not products:
        await send_message(bot, user.bale_id, f"در حال حاضر {title} موجود نیست.")
        return

    await send_message(bot, user.bale_id, f"{title}:")
    for p in products:
        approved = [r for r in p.reviews if r.is_approved]
        avg = sum(r.score for r in approved) / len(approved) if approved else 0
        rating = f"⭐ {avg:.1f} ({len(approved)} نظر)" if approved else ""

        price_text = "🆓 رایگان" if p.price == 0 else f"💰 {p.price:,} تومان"

        # بررسی ظرفیت
        capacity = getattr(p, 'capacity', 0)
        sold = getattr(p, 'sold_count', 0)
        if capacity > 0 and sold >= capacity:
            cap_text = "🔴 ظرفیت تکمیل"
            can_buy = False
        elif capacity > 0:
            cap_text = f"👥 {capacity - sold} جای خالی"
            can_buy = True
        else:
            cap_text = "👥 نامحدود"
            can_buy = True

        icon = TYPE_ICONS.get(p.type.value if hasattr(p.type, 'value') else str(p.type), "📦")
        msg = f"{icon} {p.title}\n{price_text}"
        if rating:
            msg += f"\n{rating}"
        msg += f"\n{cap_text}"
        if p.description:
            msg += f"\n\n{p.description}"

        if can_buy:
            if p.price == 0:
                btn_text = "▶️ دریافت رایگان"
            else:
                btn_text = "🛒 خرید"
            buttons = [
                [{"text": btn_text, "callback_data": f"product_{p.id}"}],
            ]
            if approved:
                buttons[0].append({"text": f"💬 نظرات ({len(approved)})", "callback_data": f"reviews_{p.id}"})
        else:
            buttons = [[{"text": "🔴 ظرفیت تکمیل شده", "callback_data": f"product_full_{p.id}"}]]

        await send_message(bot, user.bale_id, msg, reply_markup=inline_keyboard(buttons))

async def show_product(bot: Bot, user: User, product_id: int, db: Session):
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        return

    # چک ظرفیت
    capacity = getattr(p, 'capacity', 0)
    sold = getattr(p, 'sold_count', 0)
    if capacity > 0 and sold >= capacity:
        await send_message(bot, user.bale_id, "❌ متأسفانه ظرفیت این محصول تکمیل شده.")
        return

    # رایگان
    if p.price == 0:
        msg = f"✅ {p.title}\n"
        if p.description:
            msg += f"{p.description}\n"
        if p.link:
            msg += f"\n🔗 لینک: {p.link}"
        else:
            msg += "\n📩 لینک به زودی برای شما ارسال می‌شود."
        await send_message(bot, user.bale_id, msg)
        # آپدیت تعداد فروش
        if hasattr(p, 'sold_count'):
            p.sold_count = (p.sold_count or 0) + 1
            db.commit()
        return

    # پولی — ایجاد پرداخت
    tracking = "PRD-" + ''.join(random.choices(string.digits, k=5))
    payment = Payment(
        user_id=user.id,
        product_id=product_id,
        amount=p.price,
        method=PaymentMethod.bale_gateway,
        status=PaymentStatus.pending,
        tracking_code=tracking
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    from bot.handlers.payment import show_payment_info
    await show_payment_info(bot, user, payment.id, db)

async def after_product_payment(bot: Bot, user: User, product_id: int, db: Session):
    """بعد از پرداخت موفق محصول — ارسال لینک"""
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        return
    # آپدیت تعداد فروش
    if hasattr(p, 'sold_count'):
        p.sold_count = (p.sold_count or 0) + 1
        db.commit()

    if p.link:
        await send_message(bot, user.bale_id,
            f"🎉 خرید {p.title} با موفقیت انجام شد!\n\n"
            f"🔗 لینک دسترسی:\n{p.link}"
        )
    else:
        await send_message(bot, user.bale_id,
            f"🎉 خرید {p.title} با موفقیت انجام شد!\n\n"
            f"📩 اطلاعات دسترسی به زودی برای شما ارسال می‌شود."
        )
