"""BackgroundProcess model — durable state for long-running background tasks."""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BackgroundProcess(Base):
    __tablename__ = "background_processes"

    process_id:       Mapped[int]            = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Vocabulary: 'enrichment_run' | 'itis_backfill' | 'p1_syncthing' |
    #   'reprocess_pending' | 'bulk_review' | 'bulk_retry_identify' |
    #   'bulk_unlock_prefilter' | 'fungi_edibility_backfill' | 'ai_draft_backfill*'
    # ('scan_session' was listed here historically but is never written — P1/P2
    #  batch state lives in the scan_sessions table instead.)
    process_type:     Mapped[str]            = mapped_column(String(32), nullable=False, index=True)
    # Vocabulary: non-terminal 'running' | 'paused';
    #             terminal 'complete' | 'failed' | 'cancelled' | 'interrupted'
    # 'interrupted' is set by recover_stale_processes() at startup for rows whose
    # driving process died without reaching bp_finish.
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

    # --- Pass B Phase 1 (dual-write groundwork). All nullable, all UNUSED this
    # phase: no code reads or writes these yet. Types mirror job_queue (0028) so
    # the store-merge in Phase 2 is a straight copy. See migration
    # 0051_bp_dualwrite_columns.
    queue_position:   Mapped[Optional[int]]      = mapped_column(Integer, nullable=True)
    payload:          Mapped[Optional[str]]      = mapped_column(Text, nullable=True)
    created_at:       Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ended_at:         Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    label:            Mapped[Optional[str]]      = mapped_column(Text, nullable=True)
    # Unbounded error, mirrors job_queue.error_message. Distinct from `error`
    # (VARCHAR(512)) above, which stays untouched this phase.
    error_text:       Mapped[Optional[str]]      = mapped_column(Text, nullable=True)
