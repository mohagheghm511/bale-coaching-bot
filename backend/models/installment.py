from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base
import enum


class InstallmentStatus(str, enum.Enum):
    pending  = "pending"   # در انتظار پرداخت
    paid     = "paid"      # پرداخت شده
    overdue  = "overdue"   # سررسید گذشته


class InstallmentPlan(Base):
    """پلن اقساط یک محصول/پکیج"""
    __tablename__ = "installment_plans"

    id             = Column(Integer, primary_key=True, index=True)
    product_id     = Column(Integer, ForeignKey("products.id"), nullable=True)
    package_id     = Column(Integer, ForeignKey("coaching_packages.id"), nullable=True)
    first_payment  = Column(Integer, nullable=False)   # پرداخت اولیه
    total_count    = Column(Integer, nullable=False)   # تعداد اقساط
    is_active      = Column(Boolean, default=True)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())

    installments   = relationship("Installment", back_populates="plan")


class Installment(Base):
    """هر قسط"""
    __tablename__ = "installments"

    id          = Column(Integer, primary_key=True, index=True)
    plan_id     = Column(Integer, ForeignKey("installment_plans.id"), nullable=False)
    number      = Column(Integer, nullable=False)      # قسط چندم
    amount      = Column(Integer, nullable=False)      # مبلغ قسط
    due_date    = Column(DateTime, nullable=False)     # تاریخ سررسید
    status      = Column(String(20), default="pending")
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    plan        = relationship("InstallmentPlan", back_populates="installments")


class UserInstallment(Base):
    """اقساط یک کاربر خاص"""
    __tablename__ = "user_installments"

    id             = Column(Integer, primary_key=True, index=True)
    user_id        = Column(Integer, ForeignKey("users.id"), nullable=False)
    plan_id        = Column(Integer, ForeignKey("installment_plans.id"), nullable=False)
    installment_id = Column(Integer, ForeignKey("installments.id"), nullable=False)
    payment_id     = Column(Integer, ForeignKey("payments.id"), nullable=True)
    status         = Column(String(20), default="pending")  # pending/paid/rejected
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
