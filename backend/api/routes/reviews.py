from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from core.database import get_db
from models.payment import Review

router = APIRouter()

@router.get("/pending")
def pending_reviews(db: Session = Depends(get_db)):
    return db.query(Review).filter(Review.is_approved == False).order_by(Review.created_at.desc()).all()

@router.post("/{review_id}/approve")
def approve(review_id: int, db: Session = Depends(get_db)):
    r = db.query(Review).filter(Review.id == review_id).first()
    if not r:
        raise HTTPException(404)
    r.is_approved = True
    db.commit()
    return {"message": "تأیید شد"}

@router.delete("/{review_id}")
def delete_review(review_id: int, db: Session = Depends(get_db)):
    r = db.query(Review).filter(Review.id == review_id).first()
    if not r:
        raise HTTPException(404)
    db.delete(r)
    db.commit()
    return {"message": "حذف شد"}
