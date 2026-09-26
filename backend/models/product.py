from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float, ForeignKey, Enum, Time
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base
import enum

class ProductType(str, enum.Enum):
    course = "course"
    podcast = "podcast"
    webinar = "webinar"
    channel = "channel"
    coaching = "coaching"

class ReservationStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    cancelled = "cancelled"
    rescheduled = "rescheduled"
    completed = "completed"

class CoachingPackage(Base):
    """پکیج‌های کوچینگ"""
    __tablename__ = "coaching_packages"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    session_type = Column(String(20), nullable=False, default="individual")  # individual, group, vip, all
    session_count = Column(Integer, nullable=False)
    session_duration = Column(Integer, nullable=False)
    price = Column(Integer, nullable=False)
    capacity = Column(Integer, nullable=False, default=1)  # حداکثر تعداد خریداران
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    reservations = relationship("Reservation", back_populates="package")
    time_slots = relationship("TimeSlot", back_populates="package")

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(Enum(ProductType), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Integer, nullable=False)
    capacity = Column(Integer, default=0)  # 0 = نامحدود
    sold_count = Column(Integer, default=0)  # تعداد فروخته شده
    is_active = Column(Boolean, default=True)
    order = Column(Integer, default=0)
    link = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    reviews = relationship("Review", back_populates="product")

class TimeSlot(Base):
    """ساعت‌های آزاد برای رزرو"""
    __tablename__ = "time_slots"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, nullable=False)
    is_available = Column(Boolean, default=True)
    package_id = Column(Integer, ForeignKey("coaching_packages.id"), nullable=True)  # وصل به پکیج
    created_at = Column(DateTime, server_default=func.now())

    reservations = relationship("Reservation", back_populates="time_slot")
    package = relationship("CoachingPackage", back_populates="time_slots")

class Reservation(Base):
    __tablename__ = "reservations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    time_slot_id = Column(Integer, ForeignKey("time_slots.id"))
    package_id = Column(Integer, ForeignKey("coaching_packages.id"), nullable=True)
    session_number = Column(Integer, default=1)        # جلسه چندم از پکیج
    price = Column(Integer, nullable=False)
    status = Column(Enum(ReservationStatus), default=ReservationStatus.pending)
    notes = Column(Text, nullable=True)
    cancel_reason = Column(Text, nullable=True)
    reminder_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    user = relationship("User", back_populates="reservations")
    time_slot = relationship("TimeSlot", back_populates="reservations")
    package = relationship("CoachingPackage", back_populates="reservations")
    payment = relationship("Payment", back_populates="reservation", uselist=False)
