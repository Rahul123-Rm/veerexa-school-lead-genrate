"""
models/school.py — SQLAlchemy ORM models for the Veerexa School Lead Finder.

Tables:
  schools        — one row per unique school / lead
  outreach_logs  — timestamped outreach history per school
  search_cache   — cached API responses keyed by query string
  api_usage      — daily request counts for billing guard
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class School(Base):
    __tablename__ = "schools"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # ── Identity ─────────────────────────────────────────────────────────────
    place_id = Column(String(255), unique=True, nullable=True, index=True)
    name = Column(String(512), nullable=False)

    # ── Contact ──────────────────────────────────────────────────────────────
    phone = Column(String(30), nullable=True)
    website = Column(String(512), nullable=True)
    email = Column(String(255), nullable=True)
    instagram = Column(String(512), nullable=True)
    instagram_status = Column(String(64), nullable=True)   # verified / needs manual
    facebook = Column(String(512), nullable=True)
    linkedin = Column(String(512), nullable=True)
    whatsapp = Column(String(512), nullable=True)

    # ── Location ─────────────────────────────────────────────────────────────
    address = Column(Text, nullable=True)
    city = Column(String(128), nullable=True)
    district = Column(String(128), nullable=True)
    state = Column(String(128), nullable=True)
    postal_code = Column(String(16), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    maps_url = Column(String(512), nullable=True)

    # ── Google Places metadata ────────────────────────────────────────────────
    rating = Column(Float, nullable=True)
    review_count = Column(Integer, nullable=True)
    business_status = Column(String(64), nullable=True)

    # ── Data quality ──────────────────────────────────────────────────────────
    contact_source = Column(String(64), nullable=True)     # Google Places / Official website / Manual entry
    verification_status = Column(String(128), nullable=True)

    # ── Outreach ──────────────────────────────────────────────────────────────
    outreach_status = Column(String(64), nullable=True, default="New")
    is_verified = Column(Boolean, nullable=False, default=False)
    notes = Column(Text, nullable=True)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_checked = Column(DateTime, nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────────
    outreach_logs = relationship(
        "OutreachLog", back_populates="school", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "place_id": self.place_id,
            "name": self.name,
            "phone": self.phone,
            "website": self.website,
            "email": self.email,
            "instagram": self.instagram,
            "instagram_status": self.instagram_status,
            "facebook": self.facebook,
            "linkedin": self.linkedin,
            "whatsapp": self.whatsapp,
            "address": self.address,
            "city": self.city,
            "district": self.district,
            "state": self.state,
            "postal_code": self.postal_code,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "maps_url": self.maps_url,
            "rating": self.rating,
            "review_count": self.review_count,
            "business_status": self.business_status,
            "contact_source": self.contact_source,
            "verification_status": self.verification_status,
            "outreach_status": self.outreach_status,
            "is_verified": self.is_verified,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_checked": self.last_checked.isoformat() if self.last_checked else None,
        }


class OutreachLog(Base):
    __tablename__ = "outreach_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False, index=True)

    status = Column(String(64), nullable=False)
    channel = Column(String(64), nullable=True)   # WhatsApp / Instagram / Call / Email
    contact_date = Column(DateTime, nullable=True)
    follow_up_date = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    school = relationship("School", back_populates="outreach_logs")


class SearchCache(Base):
    __tablename__ = "search_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cache_key = Column(String(512), unique=True, nullable=False, index=True)
    response_json = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ApiUsage(Base):
    __tablename__ = "api_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    usage_date = Column(String(10), unique=True, nullable=False, index=True)
    request_count = Column(Integer, nullable=False, default=0)
    last_updated = Column(String(32), nullable=True)
