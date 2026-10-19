"""
experience.py — Publish-as-experience publications (migration 0054).

One row per experience page for a saved walk. B2 creates/edits drafts only;
publish/unpublish (and so published_at, published_commit, public_species_json)
arrive with Stage C. Schema rules and the walk-delete behaviour are documented
in migrations/versions/0054_experience_publications.py.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

PUBLICATION_STATUSES = ("draft", "published", "unpublished")


class ExperiencePublication(Base):
    __tablename__ = "experience_publications"
    __table_args__ = (
        # At most one default — same partial unique index as the migration.
        Index("ux_experience_publications_one_default", "is_default",
              unique=True, sqlite_where=text("is_default = 1")),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    saved_walk_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("saved_walks.id", ondelete="SET NULL"), nullable=True, index=True)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    overrides_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    unpublished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    published_commit: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    public_species_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
