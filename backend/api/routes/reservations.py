from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from core.database import get_db
from models.product import Reservation, ReservationStatus, TimeSlot

router = APIRouter()

@router.get("/")
def list_reservations(status: str = None, db: Session = Depends(get_db)):
    q = db.query(Reservation)
    if status:
        q = q.filter(Reservation.status == status)
    return q.order_by(Reservation.created_at.desc()).all()

@router.post("/slots")
def add_slot(date: str, db: Session = Depends(get_db)):
    try:
        dt = datetime.strptime(date, "%Y-%m-%d %H:%M")
    except:
        raise HTTPException(400, "فرمت: 2025-07-15 16:00")
    slot = TimeSlot(date=dt)
    db.add(slot)
    db.commit()
    return {"id": slot.id, "date": slot.date}

@router.post("/{res_id}/cancel")
async def cancel_reservation(res_id: int, db: Session = Depends(get_db)):
    res = db.query(Reservation).filter(Reservation.id == res_id).first()
    if not res:
        raise HTTPException(404)
    res.status = ReservationStatus.cancelled
    if res.time_slot:
        res.time_slot.is_available = True
    db.commit()
    from services.scheduler import notify_cancellation
    await notify_cancellation(res, db)
    return {"message": "لغو شد"}
