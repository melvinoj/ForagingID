from datetime import datetime
from typing import Optional
from sqlalchemy import String, Float, DateTime, Boolean, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    observation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("observations.id"), nullable=False, index=True
    )

    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    altitude_m: Mapped[Optional[float]] = mapped_column(Float)

    # Reverse geocoded (populated lazily)
    country: Mapped[Optional[str]] = mapped_column(String(100))
    region: Mapped[Optional[str]] = mapped_column(String(100))
    locality: Mapped[Optional[str]] = mapped_column(String(200))
    habitat_description: Mapped[Optional[str]] = mapped_column(Text)

    # Workshop planning fields
    is_workshop_site: Mapped[bool] = mapped_column(Boolean, default=False)
    access_notes: Mapped[Optional[str]] = mapped_column(Text)
    parking_notes: Mapped[Optional[str]] = mapped_column(Text)
    terrain_difficulty: Mapped[Optional[str]] = mapped_column(String(20))
    # easy | moderate | difficult | technical
    is_private_land: Mapped[Optional[bool]] = mapped_column(Boolean)
    is_avoided: Mapped[bool] = mapped_column(Boolean, default=False)
    avoided_reason: Mapped[Optional[str]] = mapped_column(Text)
    seasonal_reliability_score: Mapped[Optional[float]] = mapped_column(Float)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    observation: Mapped[Optional["Observation"]] = relationship(
        "Observation",
        back_populates="location",
    )
