from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Integer, ForeignKey, Text, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class ProcessingLog(Base):
    __tablename__ = "processing_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    observation_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("observations.id"), index=True
    )
    stage: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # ingest | detect | identify | enrich | review
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    # success | failed | skipped | pending
    message: Mapped[Optional[str]] = mapped_column(Text)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    observation: Mapped[Optional["Observation"]] = relationship(
        "Observation", back_populates="processing_logs"
    )
