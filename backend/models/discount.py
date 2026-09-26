from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from core.database import Base


class DiscountCode(Base):
    __tablename__ = "discount_codes"

    id         = Column(Integer, primary_key=True, index=True)
    code       = Column(String(50), unique=True, nullable=False)
    amount     = Column(Integer, nullable=False)   # مبلغ تخفیف به تومان
    max_uses   = Column(Integer, default=0)        # 0 = نامحدود
    used_count = Column(Integer, default=0)
    is_active  = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
