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
