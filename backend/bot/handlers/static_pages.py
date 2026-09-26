"""
bot/handlers/static_pages.py
صفحه‌های ثابت: سوالات متداول / رضایت مشتریان / معرفی من
"""
from sqlalchemy.orm import Session
from models.user import User
from models.static_content import StaticContent, ContentType, MediaType
from bale import Bot
from bot.sender import send_message, inline_keyboard


# ==================== ارسال یک آیتم محتوا به کاربر ====================

async def _send_content_item(bot: Bot, chat_id: str, item: StaticContent):
    """ارسال هر نوع محتوایی به کاربر"""
    caption = item.text or ""
    link_btn = None
    if item.link_url:
        label = item.link_label or "🔗 مشاهده"
        link_btn = inline_keyboard([[{"text": label, "callback_data": f"noop_{item.id}"}]])
        # بله inline keyboard لینک خارجی پشتیبانی نمی‌کنه — متن لینک رو ضمیمه می‌کنیم
        caption = f"{caption}\n\n{item.link_url}".strip() if caption else item.link_url

    if item.media_type == MediaType.text or item.media_type == MediaType.link:
        await send_message(bot, chat_id, caption)
    elif item.media_type == MediaType.photo:
        from bale import InputFile
        await bot.send_document(chat_id, InputFile(item.file_id), caption=caption)
    elif item.media_type == MediaType.video:
        from bale import InputFile
        try:
            await bot.send_video(chat_id, InputFile(item.file_id), caption=caption)
        except:
            await bot.send_document(chat_id, InputFile(item.file_id), caption=caption)
    elif item.media_type == MediaType.voice:
        from bale import InputFile
        try:
            await bot.send_audio(chat_id, InputFile(item.file_id), caption=caption)
        except:
            await bot.send_document(chat_id, InputFile(item.file_id), caption=caption)
    elif item.media_type == MediaType.audio:
        from bale import InputFile
        try:
            await bot.send_audio(chat_id, InputFile(item.file_id), caption=caption)
        except:
            await bot.send_document(chat_id, InputFile(item.file_id), caption=caption)
    elif item.media_type == MediaType.document:
        from bale import InputFile
        await bot.send_document(chat_id, InputFile(item.file_id), caption=caption)


# ==================== سوالات متداول ====================

async def show_faq(bot: Bot, user: User, db: Session):
    items = (
        db.query(StaticContent)
        .filter(StaticContent.content_type == ContentType.faq, StaticContent.is_active == True)
        .order_by(StaticContent.order)
        .all()
    )
    if not items:
        await send_message(bot, user.bale_id,
            "❓ سوالات متداول\n━━━━━━━━━━━━━\nهنوز سوالی ثبت نشده.")
        return

    await send_message(bot, user.bale_id, "❓ سوالات متداول\n━━━━━━━━━━━━━")
    for item in items:
        q = item.question or ""
        a = item.text or ""
        msg = f"🔹 {q}\n\n💬 {a}" if q else a
        await send_message(bot, user.bale_id, msg)


# ==================== رضایت مشتریان ====================

async def show_reviews_content(bot: Bot, user: User, db: Session):
    items = (
        db.query(StaticContent)
        .filter(StaticContent.content_type == ContentType.review, StaticContent.is_active == True)
        .order_by(StaticContent.order)
        .all()
    )
    if not items:
        await send_message(bot, user.bale_id,
            "⭐ رضایت مشتریان\n━━━━━━━━━━━━━\nهنوز محتوایی ثبت نشده.")
        return

    await send_message(bot, user.bale_id, "⭐ رضایت مشتریان\n━━━━━━━━━━━━━")
    for item in items:
        await _send_content_item(bot, user.bale_id, item)


# ==================== معرفی من ====================

async def show_intro(bot: Bot, user: User, db: Session):
    items = (
        db.query(StaticContent)
        .filter(StaticContent.content_type == ContentType.intro, StaticContent.is_active == True)
        .order_by(StaticContent.order)
        .all()
    )
    if not items:
        await send_message(bot, user.bale_id,
            "👤 معرفی من\n━━━━━━━━━━━━━\nهنوز محتوایی ثبت نشده.")
        return

    await send_message(bot, user.bale_id, "👤 معرفی من\n━━━━━━━━━━━━━")
    for item in items:
        await _send_content_item(bot, user.bale_id, item)
