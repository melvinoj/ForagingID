from datetime import datetime
from typing import Optional
from sqlalchemy import Float, DateTime, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class MapNote(Base):
    __tablename__ = "map_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    longitude: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    species_tags: Mapped[Optional[str]] = mapped_column(Text)  # JSON array of scientific names
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
