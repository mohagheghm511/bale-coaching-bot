from bale import Bot
from sqlalchemy.orm import Session
from models.user import User
from models.payment import PaymentStatus
from bot.sender import send_message, inline_keyboard


async def show(bot: Bot, user: User, db: Session):
    total_paid = sum(p.amount for p in user.payments if p.status == PaymentStatus.approved)
    last_test = "ندارد"
    if user.test_results:
        last = user.test_results[-1]
        last_test = last.test.title if last.test else "حذف شده"
    active_res = [r for r in user.reservations if r.status == "confirmed"]
    msg = (
        f"پروفایل من\n━━━━━━━━━━━━━\n"
        f"نام: {user.full_name}\nموبایل: {user.phone or 'ثبت نشده'}\n"
        f"━━━━━━━━━━━━━\n"
        f"تست انجام شده: {len(user.test_results)}\n"
        f"آخرین تست: {last_test}\n"
        f"رزروهای فعال: {len(active_res)}\n"
        f"مجموع خرید: {total_paid:,} تومان\n"
        f"━━━━━━━━━━━━━\n"
        f"عضو از: {user.created_at.strftime('%Y/%m/%d')}"
    )
    await send_message(bot, user.bale_id, msg, reply_markup=inline_keyboard([
        [{"text": "نتایج تست‌هام", "callback_data": "my_tests"},
         {"text": "رزروهای من", "callback_data": "my_reservations"}],
        [{"text": "دوره‌های من", "callback_data": "my_courses"}],
    ]))


async def show_my_tests(bot: Bot, user: User, db: Session):
    if not user.test_results:
        await send_message(bot, user.bale_id, "هنوز تستی نگرفتی.")
        return
    for r in user.test_results[-5:]:
        test_title = r.test.title if r.test else "حذف شده"
        msg = (
            f"🧪 {test_title}\n"
            f"امتیاز: {r.total_score:.1f}\n"
            f"نتیجه: {r.result_title or '-'}\n"
            f"تاریخ: {r.created_at.strftime('%Y/%m/%d')}"
        )
        await send_message(bot, user.bale_id, msg)


async def show_my_reservations(bot: Bot, user: User, db: Session):
    if not user.reservations:
        await send_message(bot, user.bale_id, "رزروی ثبت نکردی.")
        return
    for res in user.reservations[-5:]:
        import jdatetime
        slot_date = "نامشخص"
        if res.time_slot:
            try:
                j = jdatetime.datetime.fromgregorian(datetime=res.time_slot.date)
                slot_date = j.strftime("%Y/%m/%d %H:%M")
            except:
                slot_date = res.time_slot.date.strftime("%Y/%m/%d %H:%M")
        pkg_title = res.package.title if res.package else "-"
        status_map = {
            "confirmed": "تأیید شده",
            "pending": "در انتظار",
            "cancelled": "لغو شده",
            "rescheduled": "جابجا شده"
        }
        msg = (
            f"📦 {pkg_title}\n"
            f"📅 {slot_date}\n"
            f"وضعیت: {status_map.get(str(res.status).split('.')[-1], str(res.status))}"
        )
        await send_message(bot, user.bale_id, msg)


async def show_my_courses(bot: Bot, user: User, db: Session):
    from models.product import Product
    paid_product_ids = [
        p.product_id for p in user.payments
        if p.status == PaymentStatus.approved and p.product_id
    ]
    if not paid_product_ids:
        await send_message(bot, user.bale_id, "هنوز دوره‌ای خریداری نکردی.")
        return
    for pid in paid_product_ids:
        product = db.query(Product).filter(Product.id == pid).first()
        if product:
            msg = f"🎓 {product.title}\n{product.description or ''}"
            if product.link:
                msg += f"\n🔗 {product.link}"
            await send_message(bot, user.bale_id, msg)