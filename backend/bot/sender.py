from bale import Bot, InlineKeyboardMarkup, InlineKeyboardButton, MenuKeyboardMarkup, MenuKeyboardButton

def inline_keyboard(buttons: list) -> InlineKeyboardMarkup:
    """
    buttons = [
        [{"text": "دکمه ۱", "callback_data": "d1"}, {"text": "دکمه ۲", "callback_data": "d2"}],
        [{"text": "دکمه ۳", "callback_data": "d3"}],
    ]
    """
    markup = InlineKeyboardMarkup()
    for row_index, row in enumerate(buttons, start=1):
        for btn in row:
            if "url" in btn:
                markup.add(InlineKeyboardButton(btn["text"], url=btn["url"]), row=row_index)
            else:
                markup.add(InlineKeyboardButton(btn["text"], callback_data=btn["callback_data"]), row=row_index)
    return markup

def reply_keyboard(buttons: list, request_contact_row: int = None) -> MenuKeyboardMarkup:
    """
    buttons = [["دکمه ۱", "دکمه ۲"], ["دکمه ۳"]]
    request_contact_row: اگر بدی، توی اون ردیف دکمه اشتراک شماره میذاره
    """
    markup = MenuKeyboardMarkup()
    for row_index, row in enumerate(buttons, start=1):
        for text in row:
            markup.add(MenuKeyboardButton(text), row=row_index)
    return markup

def phone_request_keyboard() -> MenuKeyboardMarkup:
    """کیبورد با دکمه اشتراک‌گذاری شماره تلفن"""
    markup = MenuKeyboardMarkup()
    markup.add(
        MenuKeyboardButton("📱 اشتراک‌گذاری شماره تلفن", request_contact=True),
        row=1
    )
    return markup

async def send_message(bot: Bot, chat_id, text: str, reply_markup=None):
    await bot.send_message(chat_id, text, components=reply_markup)

async def send_photo(bot: Bot, chat_id, file_id: str, caption: str = ""):
    try:
        from bale import InputFile
        await bot.send_document(chat_id, InputFile(file_id), caption=caption)
    except Exception:
        await bot.send_message(chat_id, f"📸 {caption}")

async def notify_admins(bot, text: str, reply_markup=None):
    """ارسال پیام به همه ادمین‌ها"""
    from core.config import settings
    for admin_id in settings.admin_ids:
        try:
            await send_message(bot, admin_id, text, reply_markup=reply_markup)
        except Exception as e:
            print(f"notify_admins error for {admin_id}: {e}")
