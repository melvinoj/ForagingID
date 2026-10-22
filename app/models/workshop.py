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
    """A one-time /join link plus the device session it creates (batch 7).

    participant_id NULL = curator device (long-lived, no expiry); set = workshop
    participant (guest access). `token` is only the link: /join/<token> works
    once (claimed_at) and issues a separate cookie secret whose sha256 is
    session_hash — the link itself is never a credential."""
    __tablename__ = "guest_tokens"

    id:                  Mapped[int]           = mapped_column(Integer, primary_key=True, autoincrement=True)
    token:               Mapped[str]           = mapped_column(Text, nullable=False, unique=True, index=True)
    participant_id:      Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("workshop_participants.id"), nullable=True)
    workshop_session_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("foraging_sessions.id"), nullable=True)
    expires_at:          Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)   # NULL = never
    is_active:           Mapped[bool]          = mapped_column(Boolean, nullable=False, server_default="1")
    created_at:          Mapped[datetime]      = mapped_column(DateTime, nullable=False, server_default=func.now())
    name:                Mapped[Optional[str]] = mapped_column(Text, nullable=True)        # curator device name
    claimed_at:          Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    session_hash:        Mapped[Optional[str]] = mapped_column(Text, nullable=True, unique=True, index=True)
    last_used_at:        Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


def is_curator_token(tok: "GuestToken") -> bool:
    """The ONLY definition of "this token is a curator device" (no role column)."""
    return tok.participant_id is None


def token_is_live(tok: "GuestToken", now: Optional[datetime] = None) -> bool:
    """Active and not expired (expires_at NULL = never expires)."""
    now = now or datetime.utcnow()
    return bool(tok.is_active) and (tok.expires_at is None or tok.expires_at > now)


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
