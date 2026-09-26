from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from core.database import get_db
from models.test import Test, Question, Option, ScoreRange

router = APIRouter()

class OptionCreate(BaseModel):
    text: str
    score: float
    order: int = 0

class QuestionCreate(BaseModel):
    text: str
    order: int = 0
    options: List[OptionCreate]

class ScoreRangeCreate(BaseModel):
    min_score: float
    max_score: float
    title: str
    analysis: str
    recommendations: Optional[str] = None

class TestCreate(BaseModel):
    title: str
    description: Optional[str] = None
    is_free: bool = True
    price: int = 0
    questions: Optional[List[QuestionCreate]] = []
    score_ranges: Optional[List[ScoreRangeCreate]] = []

@router.get("/")
def list_tests(db: Session = Depends(get_db)):
    return db.query(Test).order_by(Test.order).all()

@router.post("/")
def create_test(data: TestCreate, db: Session = Depends(get_db)):
    test = Test(title=data.title, description=data.description, is_free=data.is_free, price=data.price)
    db.add(test)
    db.flush()

    for i, q in enumerate(data.questions):
        question = Question(test_id=test.id, text=q.text, order=q.order or i)
        db.add(question)
        db.flush()
        for j, o in enumerate(q.options):
            db.add(Option(question_id=question.id, text=o.text, score=o.score, order=o.order or j))

    for sr in data.score_ranges:
        db.add(ScoreRange(test_id=test.id, **sr.dict()))

    db.commit()
    return {"id": test.id, "message": "تست ساخته شد"}

@router.put("/{test_id}")
def update_test(test_id: int, data: TestCreate, db: Session = Depends(get_db)):
    test = db.query(Test).filter(Test.id == test_id).first()
    if not test:
        raise HTTPException(404, "تست پیدا نشد")
    test.title = data.title
    test.description = data.description
    test.is_free = data.is_free
    test.price = data.price
    db.commit()
    return {"message": "تست بروزرسانی شد"}

@router.delete("/{test_id}")
def delete_test(test_id: int, db: Session = Depends(get_db)):
    test = db.query(Test).filter(Test.id == test_id).first()
    if not test:
        raise HTTPException(404, "تست پیدا نشد")
    db.delete(test)
    db.commit()
    return {"message": "تست حذف شد"}
