from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    category: Mapped[Optional[str]] = mapped_column(String(50))
    # season | habitat | type | workshop | custom

    observations: Mapped[list["ObservationTag"]] = relationship(
        "ObservationTag", back_populates="tag"
    )


class ObservationTag(Base):
    __tablename__ = "observation_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    observation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("observations.id"), nullable=False, index=True
    )
    tag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tags.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    observation: Mapped["Observation"] = relationship("Observation", back_populates="tags")
    tag: Mapped["Tag"] = relationship("Tag", back_populates="observations")
