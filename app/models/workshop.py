from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Boolean, Text, Integer, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.database import Base


class WorkshopParticipant(Base):
    """Named participant in a workshop. id ≥ 2 (curator reserves id/user_id=1)."""
    __tablename__ = "workshop_participants"

    id:         Mapped[int]           = mapped_column(Integer, primary_key=True, autoincrement=True)
    name:       Mapped[str]           = mapped_column(Text, nullable=False)
    notes:      Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime]      = mapped_column(DateTime, nullable=False, server_default=func.now())


class GuestToken(Base):
    """Short-lived token granting scoped access to a participant (or curator)."""
    __tablename__ = "guest_tokens"

    id:                  Mapped[int]           = mapped_column(Integer, primary_key=True, autoincrement=True)
    token:               Mapped[str]           = mapped_column(Text, nullable=False, unique=True, index=True)
    participant_id:      Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("workshop_participants.id"), nullable=True)
    workshop_session_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("foraging_sessions.id"), nullable=True)
    expires_at:          Mapped[datetime]      = mapped_column(DateTime, nullable=False)
    is_active:           Mapped[bool]          = mapped_column(Boolean, nullable=False, server_default="1")
    created_at:          Mapped[datetime]      = mapped_column(DateTime, nullable=False, server_default=func.now())


class WorkshopSite(Base):
    __tablename__ = "workshop_sites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)

    description: Mapped[Optional[str]] = mapped_column(Text)
    access_notes: Mapped[Optional[str]] = mapped_column(Text)
    parking_notes: Mapped[Optional[str]] = mapped_column(Text)
    terrain_difficulty: Mapped[Optional[str]] = mapped_column(String(20))
    is_private_land: Mapped[bool] = mapped_column(Boolean, default=False)
    is_avoided: Mapped[bool] = mapped_column(Boolean, default=False)
    avoided_reason: Mapped[Optional[str]] = mapped_column(Text)

    seasonal_reliability_score: Mapped[Optional[float]] = mapped_column(Float)
    best_months: Mapped[Optional[str]] = mapped_column(String(100))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
