from typing import Optional

from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AboutContent(Base):
    """
    Single-row table (id is always 1) holding the editable About-page copy.

    full_description contains the literal [SPECIES_COUNT] / [OBSERVATION_COUNT]
    placeholders; the API substitutes live counts before returning.
    """

    __tablename__ = "about_content"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    snappy_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
