"""
پشتیبانی — کاربر پیام می‌فرسته، ادمین روی دکمه پاسخ می‌زنه، جواب ارسال می‌شه، تیکت بسته می‌شه
"""
from bale import Bot
from sqlalchemy.orm import Session
from models.user import User
from bot.sender import send_message, inline_keyboard
from bot.dispatcher import set_state, clear_state, get_state
from core.config import settings

# نگه‌داری تیکت‌های باز: {ticket_id: user_bale_id}
open_tickets: dict = {}


async def start_support(bot: Bot, user: User):
    """مرحله اول: از کاربر بخواه پیامش رو بنویسه"""
    set_state(user.bale_id, {"step": "waiting_support_message"})
    await send_message(
        bot, user.bale_id,
        "💬 پشتیبانی\n━━━━━━━━━━━━━\n"
        "پیام خودت رو بنویس، در اولین فرصت پاسخ داده می‌شه 👇\n\n"
        "(برای انصراف /cancel بزن)"
    )


async def handle_support_message(bot: Bot, user: User, text: str, db: Session):
    """مرحله دوم: پیام کاربر رو به ادمین ارسال کن با دکمه پاسخ"""
    if text == "/cancel":
        clear_state(user.bale_id)
        await send_message(bot, user.bale_id, "❌ لغو شد.")
        return

    clear_state(user.bale_id)

    # ticket_id بر اساس bale_id کاربر
    ticket_id = str(user.bale_id)

    # ذخیره تیکت
    open_tickets[ticket_id] = user.bale_id

    # ارسال به ادمین با دکمه پاسخ
    admin_msg = (
        f"📩 تیکت پشتیبانی جدید\n"
        f"━━━━━━━━━━━━━\n"
        f"👤 {user.full_name}\n"
        f"📞 {user.phone or 'ثبت نشده'}\n"
        f"🆔 {user.bale_id}\n"
        f"━━━━━━━━━━━━━\n"
        f"💬 پیام:\n{text}"
    )

    reply_btn = inline_keyboard([
        [{"text": "✍️ پاسخ به این تیکت", "callback_data": f"reply_ticket_{ticket_id}"}]
    ])

    await send_message(bot, settings.ADMIN_BALE_ID, admin_msg, reply_markup=reply_btn)

    # تأیید به کاربر
    await send_message(
        bot, user.bale_id,
        "✅ پیامت ارسال شد!\n"
        "به زودی پاسخ دریافت می‌کنی 🙏",
        reply_markup=inline_keyboard([
            [{"text": "🏠 منو اصلی", "callback_data": "goto_main"}]
        ])
    )


async def handle_admin_reply_callback(bot: Bot, admin: User, ticket_id: str):
    """وقتی ادمین روی دکمه پاسخ می‌زنه — state ادمین رو تنظیم کن"""
    if ticket_id not in open_tickets:
        await send_message(bot, admin.bale_id, "⚠️ این تیکت دیگه باز نیست یا قبلاً بسته شده.")
        return

    set_state(admin.bale_id, {
        "step": "admin_reply_ticket",
        "ticket_id": ticket_id
    })
    await send_message(
        bot, admin.bale_id,
        "✍️ متن پاسخ خود را بنویسید:\n(برای انصراف /cancel بزن)"
    )


async def handle_admin_reply_text(bot: Bot, admin: User, text: str):
    """وقتی ادمین متن پاسخ رو فرستاد — به کاربر ارسال کن و تیکت رو ببند"""
    state = get_state(admin.bale_id)
    ticket_id = state.get("ticket_id")

    if text == "/cancel":
        clear_state(admin.bale_id)
        await send_message(bot, admin.bale_id, "❌ ارسال پاسخ لغو شد.")
        return

    user_bale_id = open_tickets.get(ticket_id)
    if not user_bale_id:
        clear_state(admin.bale_id)
        await send_message(bot, admin.bale_id, "⚠️ تیکت پیدا نشد یا قبلاً بسته شده.")
        return

    # ارسال جواب به کاربر
    await bot.send_message(
        user_bale_id,
        f"📬 پاسخ پشتیبانی:\n━━━━━━━━━━━━━\n{text}"
    )

    # بستن تیکت و پاک کردن state ادمین
    del open_tickets[ticket_id]
    clear_state(admin.bale_id)

    # اطلاع به ادمین
    await send_message(
        bot, admin.bale_id,
        "✅ پاسخ ارسال شد و تیکت بسته شد."
    )