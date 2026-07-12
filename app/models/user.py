from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    """Canonical principal / account row.

    id=1 is reserved for the curator (role='curator'); workshop participants
    map to their workshop_participants.id (id ≥ 2, role='participant').
    Additive groundwork for multi-tenancy — no FK is added to other tables yet.
    """
    __tablename__ = "users"

    id:           Mapped[int]           = mapped_column(Integer, primary_key=True, autoincrement=True)
    role:         Mapped[str]           = mapped_column(Text, nullable=False, server_default="participant")
    display_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at:   Mapped[datetime]      = mapped_column(DateTime, nullable=False, server_default=func.now())
