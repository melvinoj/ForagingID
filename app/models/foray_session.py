from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class ForagingSession(Base):
    __tablename__ = "foraging_sessions"

    id:                Mapped[int]           = mapped_column(Integer, primary_key=True)
    name:              Mapped[str]           = mapped_column(String(200), nullable=False)
    status:            Mapped[str]           = mapped_column(String(20), nullable=False, default="draft")
    walk_id:           Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("saved_walks.id", ondelete="SET NULL"), nullable=True)
    recorded_walk_id:  Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("recorded_walks.id", ondelete="SET NULL"), nullable=True)
    location_override: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    session_date:      Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # YYYY-MM-DD
    facilitator_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at:        Mapped[datetime]      = mapped_column(DateTime, server_default=func.now())
    updated_at:        Mapped[datetime]      = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class SessionSpecies(Base):
    __tablename__ = "session_species"

    id:            Mapped[int]      = mapped_column(Integer, primary_key=True)
    session_id:    Mapped[int]      = mapped_column(Integer, ForeignKey("foraging_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    species_id:    Mapped[int]      = mapped_column(Integer, ForeignKey("species.id",           ondelete="CASCADE"), nullable=False)
    display_order: Mapped[int]      = mapped_column(Integer, nullable=False, default=0)
    source:        Mapped[str]      = mapped_column(String(20), nullable=False, default="manual")
    added_at:      Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SessionAttendee(Base):
    __tablename__ = "session_attendees"

    id:            Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id:    Mapped[int] = mapped_column(Integer, ForeignKey("foraging_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    name:          Mapped[str] = mapped_column(Text, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
