from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base
import enum

class UserStatus(str, enum.Enum):
    active = "active"
    blocked = "blocked"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    bale_id = Column(String(50), unique=True, index=True, nullable=False)
    username = Column(String(100), nullable=True)
    full_name = Column(String(200), nullable=True)
    phone = Column(String(20), nullable=True)
    status = Column(Enum(UserStatus), default=UserStatus.active)
    is_admin = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)  # یادداشت ادمین
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relations
    test_results = relationship("TestResult", back_populates="user")
    reservations = relationship("Reservation", back_populates="user")
    payments = relationship("Payment", back_populates="user")
    reviews = relationship("Review", back_populates="user")

    def __repr__(self):
        return f"<User {self.bale_id} - {self.full_name}>"
