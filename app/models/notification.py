from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class NotificationDismissal(Base):
    """A dismissed seasonal-return notification (11b).

    Dedup is per species per season: `season_key` encodes the year and which
    season fired (e.g. "2026:fruit", "2026:flower", "2026:anniversary"), so a
    species can still notify for a distinct season later in the year, but a
    dismissed one never re-nags within the same season.
    """
    __tablename__ = "notification_dismissals"

    id:           Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id:      Mapped[int]      = mapped_column(Integer, nullable=False, server_default="1")
    species_id:   Mapped[int]      = mapped_column(Integer, ForeignKey("species.id"), nullable=False, index=True)
    season_key:   Mapped[str]      = mapped_column(String(40), nullable=False)
    dismissed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "species_id", "season_key", name="uq_notif_dismissal"),
    )
