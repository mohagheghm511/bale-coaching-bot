from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base
import enum

class PaymentStatus(str, enum.Enum):
    pending = "pending"
    uploaded = "uploaded"
    approved = "approved"
    rejected = "rejected"
    refunded = "refunded"

class PaymentMethod(str, enum.Enum):
    card_transfer = "card_transfer"
    bale_gateway = "bale_gateway"

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    reservation_id = Column(Integer, ForeignKey("reservations.id"), nullable=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    amount = Column(Integer, nullable=False)
    method = Column(Enum(PaymentMethod), default=PaymentMethod.card_transfer)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.pending)
    tracking_code = Column(String(50), unique=True, nullable=False)
    receipt_image = Column(String(500), nullable=True)
    admin_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="payments")
    reservation = relationship("Reservation", back_populates="payment")

class BroadcastMessage(Base):
    __tablename__ = "broadcast_messages"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    text = Column(Text, nullable=False)
    sent_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
