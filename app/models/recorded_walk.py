from sqlalchemy import Boolean, Column, Integer, String, Float, DateTime, Text, ForeignKey, false, true
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
    # "Show to guests" (migration 0058): off by default; see recorded_walk_visible_to.
    shared_with_guests = Column(Boolean, nullable=False, server_default="0", default=False)


# ---------------------------------------------------------------------------
# Who may see a recorded walk (Melvin, 22 Oct 2026) — the ONLY rule, same shape
# as encounter_visible_to: the curator sees every walk; a workshop participant
# sees one (list, detail, trace) only when it is shared_with_guests; an
# anonymous guest sees none. The audio note is never a guest's, shared or not
# (recorded_walks.py nulls it; guest_access.py refuses /media/recorded-walks).
# ---------------------------------------------------------------------------

def recorded_walk_visible_to(walk, identity) -> bool:
    if not identity.is_guest:
        return True
    if identity.is_anonymous_guest or identity.user_id is None:
        return False
    return bool(walk.shared_with_guests)


def recorded_walk_visibility_clause(identity):
    """SQL twin of recorded_walk_visible_to() for SELECTs on RecordedWalk."""
    if not identity.is_guest:
        return true()
    if identity.is_anonymous_guest or identity.user_id is None:
        return false()
    return RecordedWalk.shared_with_guests.is_(True)


class RecordedWalkObservation(Base):
    __tablename__ = "recorded_walk_observations"

    id               = Column(Integer, primary_key=True, index=True)
    recorded_walk_id = Column(Integer, ForeignKey("recorded_walks.id", ondelete="CASCADE"), nullable=False, index=True)
    observation_id   = Column(Integer, nullable=False)
    encountered_at   = Column(DateTime(timezone=True), nullable=True)
