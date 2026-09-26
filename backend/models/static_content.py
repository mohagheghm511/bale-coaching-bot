from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Enum
from sqlalchemy.sql import func
from core.database import Base
import enum


class ContentType(str, enum.Enum):
    review     = "review"      # رضایت مشتریان
    intro      = "intro"       # معرفی من
    faq        = "faq"         # سوالات متداول


class MediaType(str, enum.Enum):
    text       = "text"
    photo      = "photo"
    video      = "video"
    voice      = "voice"
    audio      = "audio"
    document   = "document"
    link       = "link"        # لینک خارجی (با دکمه)


class StaticContent(Base):
    """محتوای صفحه‌های ثابت: رضایت / معرفی / FAQ"""
    __tablename__ = "static_contents"

    id          = Column(Integer, primary_key=True, index=True)
    content_type = Column(Enum(ContentType), nullable=False)
    media_type  = Column(Enum(MediaType), nullable=False, default=MediaType.text)

    # متن اصلی — برای text/faq/link-caption
    text        = Column(Text, nullable=True)

    # برای FAQ: سوال جداگانه
    question    = Column(Text, nullable=True)

    # برای لینک: آدرس و لیبل دکمه
    link_url    = Column(String(1000), nullable=True)
    link_label  = Column(String(200), nullable=True)

    # file_id بله برای انواع مدیا
    file_id     = Column(String(500), nullable=True)

    is_active   = Column(Boolean, default=True)
    order       = Column(Integer, default=0)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
