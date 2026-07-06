"""
personal_list.py — Standing personal species lists (Phase 11a.3).

A personal list is the "workshop-of-one": the same machinery as a multi-participant
workshop list, differing only in member count (here, one — user_id = 1). The standing
"My Season" list is auto-created per user with slug "my-season".

Architectural boundary (11a): lists reference species read-only BY ID. A list membership
row never copies or writes species/observation/enrichment data — it points at species.id.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class PersonalList(Base):
    """A standing personal list owned by one user. The 'My Season' list is the
    canonical standing list (slug='my-season', is_standing=1)."""

    __tablename__ = "personal_lists"
    __table_args__ = (UniqueConstraint("user_id", "slug", name="uq_personal_list_user_slug"),)

    id:          Mapped[int]               = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id:     Mapped[int]               = mapped_column(Integer, nullable=False, server_default="1", index=True)
    slug:        Mapped[str]               = mapped_column(String(60), nullable=False)
    name:        Mapped[str]               = mapped_column(String(200), nullable=False)
    is_standing: Mapped[bool]              = mapped_column(Boolean, nullable=False, server_default="0")
    created_at:  Mapped[datetime]          = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at:  Mapped[datetime]          = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=datetime.utcnow)

    members: Mapped[list["PersonalListSpecies"]] = relationship(
        "PersonalListSpecies", back_populates="personal_list", cascade="all, delete-orphan"
    )


class PersonalListSpecies(Base):
    """Membership row: a species (by ID, read-only reference) belongs to a personal list."""

    __tablename__ = "personal_list_species"
    __table_args__ = (UniqueConstraint("list_id", "species_id", name="uq_list_species"),)

    id:         Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    list_id:    Mapped[int]      = mapped_column(Integer, ForeignKey("personal_lists.id"), nullable=False, index=True)
    species_id: Mapped[int]      = mapped_column(Integer, ForeignKey("species.id"), nullable=False, index=True)
    added_at:   Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    personal_list: Mapped["PersonalList"] = relationship("PersonalList", back_populates="members")
