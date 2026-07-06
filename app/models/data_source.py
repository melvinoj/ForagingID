from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class DataSource(Base):
    """
    Registry of external foraging data sources (Phase 11a — Data Sources).

    Registry + reachability only — no scraping logic lives here. `data_types`
    is stored as a JSON array string (e.g. '["culinary","folklore"]').
    """

    __tablename__ = "data_sources"

    id:               Mapped[int]                = mapped_column(primary_key=True, autoincrement=True)
    label:            Mapped[str]                = mapped_column(Text, nullable=False)
    url:              Mapped[str]                = mapped_column(Text, nullable=False, unique=True)
    # JSON array: any of culinary / id_notes / medicinal / phenology / folklore
    data_types:       Mapped[Optional[str]]      = mapped_column(Text, nullable=True)
    species_scope:    Mapped[Optional[str]]      = mapped_column(Text, nullable=True)  # plants / fungi / both
    region:           Mapped[Optional[str]]      = mapped_column(Text, nullable=True)  # UK / Europe / Global / US
    status:           Mapped[str]                = mapped_column(Text, nullable=False, server_default="active")  # active / paused
    notes:            Mapped[Optional[str]]      = mapped_column(Text, nullable=True)
    last_tested:      Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_test_status: Mapped[str]                = mapped_column(Text, nullable=False, server_default="untested")  # ok / unreachable / untested
    created_at:       Mapped[datetime]           = mapped_column(DateTime, nullable=False, server_default=func.now())
