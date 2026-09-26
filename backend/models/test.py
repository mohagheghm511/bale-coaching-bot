from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base

class Test(Base):
    __tablename__ = "tests"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    is_free = Column(Boolean, default=True)
    price = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    analysis_type = Column(String(20), default="numeric")
    tone = Column(String(20), default="friendly")
    importance = Column(Text, nullable=True)
    access_type = Column(String(20), default="free")  # free / invite / paid
    analysis_content = Column(Text, nullable=True)  # محتوای تحلیلی ادمین
    questions = relationship("Question", back_populates="test", order_by="Question.order")
    results = relationship("TestResult", back_populates="test")
    reviews = relationship("Review", back_populates="test")

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    test_id = Column(Integer, ForeignKey("tests.id", ondelete="CASCADE"))
    text = Column(Text, nullable=False)
    analysis = Column(Text, nullable=True)  # تحلیل این سوال پس از پاسخ کاربر
    order = Column(Integer, default=0)

    test = relationship("Test", back_populates="questions")
    options = relationship("Option", back_populates="question", order_by="Option.order")

class Option(Base):
    __tablename__ = "options"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"))
    text = Column(String(500), nullable=False)
    score = Column(Float, default=0)
    type_label = Column(String(50), nullable=True)
    order = Column(Integer, default=0)

    question = relationship("Question", back_populates="options")

class ScoreRange(Base):
    """تحلیل نتیجه بر اساس بازه امتیاز"""
    __tablename__ = "score_ranges"

    id = Column(Integer, primary_key=True, index=True)
    test_id = Column(Integer, ForeignKey("tests.id", ondelete="CASCADE"))
    min_score = Column(Float, nullable=False)
    max_score = Column(Float, nullable=False)
    title = Column(String(200), nullable=False)
    analysis = Column(Text, nullable=False)
    recommendations = Column(Text, nullable=True)

class TestResult(Base):
    __tablename__ = "test_results"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    test_id = Column(Integer, ForeignKey("tests.id", ondelete="CASCADE"))
    answers = Column(JSON, nullable=False)  # {question_id: option_id}
    total_score = Column(Float, nullable=False)
    result_title = Column(String(200), nullable=True)
    result_analysis = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="test_results")
    test = relationship("Test", back_populates="results")
