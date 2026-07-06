"""
ScanSession model — persists per-batch processing history for both pipelines.

Pipeline 1 (Syncthing): one session per auto-scan batch that finds new files.
Pipeline 2 (File upload): one session per drag/folder submission.

Sessions are write-once incrementally (never deleted). They are observers of
the pipeline — they do not participate in identification logic.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ScanSession(Base):
    __tablename__ = "scan_sessions"

    id:              Mapped[int]            = mapped_column(Integer, primary_key=True, autoincrement=True)
    pipeline:        Mapped[int]            = mapped_column(Integer, nullable=False)          # 1 or 2
    label:           Mapped[str]            = mapped_column(Text,    nullable=False)
    started_at:      Mapped[datetime]       = mapped_column(DateTime, nullable=False)
    ended_at:        Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    files_received:  Mapped[int]            = mapped_column(Integer, default=0, server_default="0")
    files_processed: Mapped[int]            = mapped_column(Integer, default=0, server_default="0")
    files_approved:  Mapped[int]            = mapped_column(Integer, default=0, server_default="0")
    files_review:    Mapped[int]            = mapped_column(Integer, default=0, server_default="0")
    files_rejected:  Mapped[int]            = mapped_column(Integer, default=0, server_default="0")  # pre-filter rejects
    files_duplicate: Mapped[int]            = mapped_column(Integer, default=0, server_default="0")  # skipped as duplicate hash
    files_failed:    Mapped[int]            = mapped_column(Integer, default=0, server_default="0")
    files_skipped:   Mapped[int]            = mapped_column(Integer, default=0, server_default="0")  # non-image files (sidecars etc.)
    source_path:     Mapped[Optional[str]]  = mapped_column(Text,    nullable=True)           # P2 folder path
    # ── Durable batch state (migration 0021) ─────────────────────────────────
    # status: queued / running / paused / complete / failed / stalled
    status:                  Mapped[Optional[str]] = mapped_column(Text,    nullable=True, server_default="complete")
    last_heartbeat:          Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    files_new:               Mapped[int]          = mapped_column(Integer, default=0, server_default="0")
    files_retryable:         Mapped[int]          = mapped_column(Integer, default=0, server_default="0")
    files_already_processed: Mapped[int]          = mapped_column(Integer, default=0, server_default="0")
