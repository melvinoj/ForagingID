from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.sql import func

from app.database import Base


class RecordedWalk(Base):
    __tablename__ = "recorded_walks"

    id                = Column(Integer, primary_key=True, index=True)
    name              = Column(String(200), nullable=False)
    started_at        = Column(DateTime(timezone=True), nullable=False)
    ended_at          = Column(DateTime(timezone=True), nullable=True)
    distance_m        = Column(Float, nullable=True)
    duration_s        = Column(Integer, nullable=True)
    elevation_gain_m  = Column(Float, nullable=True)
    elevation_loss_m  = Column(Float, nullable=True)
    track_points_json = Column(Text, nullable=False, default="[]")
    audio_note_path   = Column(String(500), nullable=True)
    created_at        = Column(DateTime(timezone=True), server_default=func.now())
    # Ownership (multi-tenancy groundwork) — nullable, no FK yet; backfilled to curator (user_id=1)
    user_id           = Column(Integer, nullable=True)


class RecordedWalkObservation(Base):
    __tablename__ = "recorded_walk_observations"

    id               = Column(Integer, primary_key=True, index=True)
    recorded_walk_id = Column(Integer, ForeignKey("recorded_walks.id", ondelete="CASCADE"), nullable=False, index=True)
    observation_id   = Column(Integer, nullable=False)
    encountered_at   = Column(DateTime(timezone=True), nullable=True)
