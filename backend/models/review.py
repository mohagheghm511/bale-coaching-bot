from sqlalchemy import Column, Integer, Float, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base

class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    test_id = Column(Integer, ForeignKey("tests.id"), nullable=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    score = Column(Float, nullable=False)
    text = Column(Text, nullable=True)
    is_approved = Column(Boolean, default=False)
    allow_publish = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="reviews")
    test = relationship("Test", back_populates="reviews")
    product = relationship("Product", back_populates="reviews")
