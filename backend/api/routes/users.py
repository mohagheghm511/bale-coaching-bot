from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from core.database import get_db
from models.user import User, UserStatus
from models.payment import BroadcastMessage
from bot.sender import send_message
import main as _main  # برای دسترسی به bot

router = APIRouter()

@router.get("/")
def list_users(db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.created_at.desc()).all()
    result = []
    for u in users:
        result.append({
            "id": u.id,
            "bale_id": u.bale_id,
            "full_name": u.full_name,
            "phone": u.phone,
            "status": u.status,
            "test_count": len(u.test_results),
            "reservation_count": len(u.reservations),
            "created_at": u.created_at,
        })
    return result

@router.get("/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "کاربر پیدا نشد")
    return {
        "user": user,
        "test_results": user.test_results,
        "reservations": user.reservations,
        "payments": user.payments,
        "reviews": user.reviews,
    }

@router.post("/{user_id}/block")
def block_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404)
    user.status = UserStatus.blocked
    db.commit()
    return {"message": "کاربر بلاک شد"}

@router.post("/{user_id}/unblock")
def unblock_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404)
    user.status = UserStatus.active
    db.commit()
    return {"message": "کاربر آنبلاک شد"}

class BroadcastData(BaseModel):
    title: str
    text: str

@router.post("/broadcast")
async def broadcast(data: BroadcastData, db: Session = Depends(get_db)):
    """ارسال پیام انبوه به همه کاربران فعال"""
    users = db.query(User).filter(User.status == UserStatus.active).all()

    sent = 0
    failed = 0
    for user in users:
        try:
            await send_message(_main.bot, user.bale_id, data.text)
            sent += 1
        except:
            failed += 1

    log = BroadcastMessage(title=data.title, text=data.text, sent_count=sent, failed_count=failed)
    db.add(log)
    db.commit()

    return {"sent": sent, "failed": failed}
