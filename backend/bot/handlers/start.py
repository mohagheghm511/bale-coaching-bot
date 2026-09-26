from bale import Bot
from models.user import User
from bot.sender import send_message, reply_keyboard, phone_request_keyboard


def main_menu(is_admin=False, has_installments=False):
    buttons = [
        ["🧪جعبه‌ی سیاهِ شخصیت‌شناسی"],
        ["📅 رزرو جلسه کوچینگ"],
        ["🎓 دوره‌ها و آموزش‌ها", "🎧 پادکست‌ها"],
        ["👤 معرفی من", "⭐ رضایت مشتریان"],
        ["❓ سوالات شما", "📞 پشتیبانی"],
        ["👤 پروفایل من"],
    ]
    if has_installments:
        buttons.insert(-1, ["💳 اقساط من"])
    if is_admin:
        buttons.append(["⚙️ پنل مدیریت"])
    return reply_keyboard(buttons)


async def handle_start(bot: Bot, user: User, db=None):
    from bot.dispatcher import set_state
    if not user.full_name:
        set_state(user.bale_id, {"step": "waiting_name"})
        await send_message(bot, user.bale_id,
            "سلام! 👋\nبه ربات کوچینگ خوش آمدید 🌱\n\nلطفاً نام و نام خانوادگی خود را وارد کنید:")
    elif not user.phone:
        set_state(user.bale_id, {"step": "waiting_phone"})
        await send_message(bot, user.bale_id,
            f"ممنون {user.full_name} عزیز! 📞\nحالا شماره موبایلت رو با دکمه زیر به اشتراک بذار:",
            reply_markup=phone_request_keyboard())
    else:
        await show_main_menu(bot, user, db)


async def show_main_menu(bot: Bot, user: User, db=None):
    from core.config import settings
    is_adm = str(user.bale_id) in settings.admin_ids
    has_installments = False
    if db:
        try:
            from models.installment import UserInstallment
            count = db.query(UserInstallment).filter(
                UserInstallment.user_id == user.id,
                UserInstallment.status == "pending"
            ).count()
            has_installments = count > 0
        except:
            pass
    await send_message(bot, user.bale_id,
        f"سلام {user.full_name} عزیز! 👋\nچه کاری می‌تونم برات انجام بدم؟",
        reply_markup=main_menu(is_adm, has_installments))
