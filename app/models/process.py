"""BackgroundProcess model — durable state for long-running background tasks."""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BackgroundProcess(Base):
    __tablename__ = "background_processes"

    process_id:       Mapped[int]            = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Vocabulary: 'enrichment_run' | 'scan_session' | 'itis_backfill'
    process_type:     Mapped[str]            = mapped_column(String(32), nullable=False, index=True)
    # Vocabulary: 'running' | 'paused' | 'complete' | 'failed' | 'cancelled'
    status:           Mapped[str]            = mapped_column(String(16), nullable=False, default="running", server_default="running")
    started_at:       Mapped[datetime]       = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at:       Mapped[datetime]       = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_heartbeat:   Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    progress_current: Mapped[Optional[int]]  = mapped_column(Integer, default=0, server_default="0")
    progress_total:   Mapped[Optional[int]]  = mapped_column(Integer, default=0, server_default="0")
    # Human-readable current step, e.g. "Enriching Sambucus nigra (47 of 312)"
    detail:           Mapped[Optional[str]]  = mapped_column(String(255), nullable=True)
    # Last error message when status='failed'
    error:            Mapped[Optional[str]]  = mapped_column(String(512), nullable=True)
