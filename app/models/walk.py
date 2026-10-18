from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.sql import func

from app.database import Base


class SavedWalk(Base):
    __tablename__ = "saved_walks"

    id             = Column(Integer, primary_key=True, index=True)
    name           = Column(String(200), nullable=False)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
    obs_ids_json   = Column(Text, default="[]")      # JSON array of observation IDs
    waypoints_json = Column(Text, default="[]")      # JSON array of {lat, lng, obs_id}
    route_geojson  = Column(Text, nullable=True)     # ORS GeoJSON or null for straight-line
    distance_m     = Column(Float, default=0.0)
    duration_min   = Column(Integer, default=0)
    # Ownership (multi-tenancy groundwork) — nullable, no FK yet; backfilled to curator (user_id=1)
    user_id        = Column(Integer, nullable=True)
    # Membership by route proximity (migration 0053; rule in app/services/walk_membership.py).
    # All NULL = defaults: 25 m buffer, photos taken on/after created_at join.
    buffer_m          = Column(Float, nullable=True)
    members_since     = Column(DateTime, nullable=True)   # PHOTO clock (EXIF local), not UTC
    excluded_obs_json = Column(Text, nullable=True)       # JSON ids removed from the walk by hand
    accepted_obs_json = Column(Text, nullable=True)       # JSON ids of older photos accepted from review
