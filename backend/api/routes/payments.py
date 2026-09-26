from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from core.database import get_db
from core.bot_instance import get_bot
from models.payment import Payment, PaymentStatus
from bot.handlers.payment import approve_payment, reject_payment

router = APIRouter()

@router.get("/")
def list_payments(status: str = None, db: Session = Depends(get_db)):
    q = db.query(Payment)
    if status:
        q = q.filter(Payment.status == status)
    return q.order_by(Payment.created_at.desc()).all()

@router.post("/{payment_id}/approve")
async def approve(payment_id: int, db: Session = Depends(get_db)):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(404, "پرداخت پیدا نشد")
    bot = get_bot()
    await approve_payment(bot, payment_id, db)
    return {"ok": True, "message": "پرداخت تأیید شد"}

@router.post("/{payment_id}/reject")
async def reject(payment_id: int, db: Session = Depends(get_db)):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(404, "پرداخت پیدا نشد")
    bot = get_bot()
    await reject_payment(bot, payment_id, db)
    return {"ok": True, "message": "پرداخت رد شد"}

@router.get("/{payment_id}/receipt")
def get_receipt(payment_id: int, db: Session = Depends(get_db)):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(404, "پرداخت پیدا نشد")
    return {"receipt_image": payment.receipt_image}
