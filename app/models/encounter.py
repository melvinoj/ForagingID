from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, Text, UniqueConstraint, and_, false, or_
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class EncounterPhoto(Base):
    """Many-to-many link between encounters and observations (photos).

    Each row records how the binding was made so the resolver can be audited.
    """
    __tablename__ = "encounter_photos"
    __table_args__ = (
        UniqueConstraint("encounter_id", "observation_id", name="uq_encounter_observation"),
    )

    id:              Mapped[int]             = mapped_column(Integer, primary_key=True, autoincrement=True)
    encounter_id:    Mapped[int]             = mapped_column(Integer, ForeignKey("encounters.id", ondelete="CASCADE"), nullable=False, index=True)
    observation_id:  Mapped[int]             = mapped_column(Integer, ForeignKey("observations.id", ondelete="CASCADE"), nullable=False, index=True)
    binding_method:  Mapped[str]             = mapped_column(Text, nullable=False)  # "own_named" | "filename" | "proximity" | "manual"
    binding_detail:  Mapped[Optional[str]]   = mapped_column(Text, nullable=True)
    created_at:      Mapped[datetime]        = mapped_column(DateTime, nullable=False, server_default=func.now())

    encounter:   Mapped["Encounter"]    = relationship("Encounter", back_populates="photos")
    observation: Mapped["Observation"]  = relationship("Observation", lazy="joined")


class Encounter(Base):
    __tablename__ = "encounters"

    id:                  Mapped[int]             = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id:             Mapped[int]             = mapped_column(Integer, nullable=False, server_default="1")
    species_id:          Mapped[Optional[int]]   = mapped_column(Integer, ForeignKey("species.id"), nullable=True, index=True)
    observation_id:      Mapped[Optional[int]]   = mapped_column(Integer, ForeignKey("observations.id"), nullable=True)
    list_id:             Mapped[Optional[int]]   = mapped_column(Integer, nullable=True)
    workshop_session_id: Mapped[Optional[int]]   = mapped_column(Integer, nullable=True)
    encounter_date:      Mapped[datetime]        = mapped_column(DateTime, nullable=False, index=True)
    latitude:            Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude:           Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    location_name:       Mapped[Optional[str]]   = mapped_column(Text, nullable=True)
    audio_path:          Mapped[Optional[str]]   = mapped_column(Text, nullable=True)
    text_note:           Mapped[Optional[str]]   = mapped_column(Text, nullable=True)
    sketch_path:         Mapped[Optional[str]]   = mapped_column(Text, nullable=True)
    prompt_stage:        Mapped[Optional[str]]   = mapped_column(Text, nullable=True)
    prompt_response:     Mapped[Optional[str]]   = mapped_column(Text, nullable=True)
    # Capture context: "field" (New Encounter tab, default) or "season" (recorded
    # from the My Season tab record button). Display/grouping only — additive (11a Prompt 2).
    encounter_type:      Mapped[str]             = mapped_column(Text, nullable=False, server_default="field")
    # Whisper transcript of audio_path — nullable; populated only on the
    # deliberate laptop-side Transcribe step, never automatically on capture (11a.4).
    transcript:          Mapped[Optional[str]]   = mapped_column(Text, nullable=True)
    # AI-extracted suggestions (JSON string) — species/phenology/recipe/location
    # cues surfaced for the user to confirm or dismiss. Never auto-written elsewhere (11a.4).
    encounter_suggestions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Field Recipe artefact (JSON string) — one structured recipe per encounter
    # (title/body/ingredients/date/location_name). Ingredients link to species via
    # ingredients[].species_id. Saved via PATCH /field-recipe; never auto-written (Phase 12).
    field_recipes:       Mapped[Optional[str]]   = mapped_column(Text, nullable=True)
    research_visible:    Mapped[bool]            = mapped_column(Boolean, nullable=False, server_default="1")
    # Client-generated UUID — the idempotency key for the offline write queue
    # (Phase 13.10b). Nullable + unique: old clients send none; a replayed POST that
    # repeats a client_uuid returns the existing row instead of creating a duplicate.
    # SQLite treats NULLs as distinct in a unique index, so legacy rows (NULL) coexist.
    client_uuid:         Mapped[Optional[str]]   = mapped_column(Text, nullable=True, unique=True, index=True)
    # Camera filename the encounter is waiting for — set at capture time by
    # online own-naming or offline gallery tap-pick, so p1 can bind on arrival.
    expected_filename:   Mapped[Optional[str]]   = mapped_column(Text, nullable=True)
    # "Share with guests" (batch 8, migration 0057): a CURATOR encounter is
    # visible to workshop participants only when this is set. Default off.
    shared_with_guests:  Mapped[bool]            = mapped_column(Boolean, nullable=False, server_default="0", default=False)
    created_at:          Mapped[datetime]        = mapped_column(DateTime, nullable=False, server_default=func.now())

    photos: Mapped[List["EncounterPhoto"]] = relationship("EncounterPhoto", back_populates="encounter", cascade="all, delete-orphan", lazy="selectin")


# ---------------------------------------------------------------------------
# Who may see an encounter (batch 8, Melvin 22 Oct 2026) — the ONLY rule:
# the curator sees everything; a participant sees their own notes plus curator
# encounters marked shared_with_guests — never another participant's; an
# anonymous guest sees nothing. Its media (audio, sketch) follow the same rule
# (app.services.guest_access). `identity` is app.api.identity.Identity.
# ---------------------------------------------------------------------------
CURATOR_USER_ID = 1          # identity.py: localhost / curator devices are user 1


def encounter_visible_to(enc, identity) -> bool:
    if not identity.is_guest:
        return True
    if identity.is_anonymous_guest or identity.user_id is None:
        return False
    return enc.user_id == identity.user_id or (enc.user_id == CURATOR_USER_ID and bool(enc.shared_with_guests))


def encounter_visibility_clause(identity):
    """SQL twin of encounter_visible_to() for SELECTs on Encounter."""
    if not identity.is_guest:
        return Encounter.id.is_not(None)
    if identity.is_anonymous_guest or identity.user_id is None:
        return false()
    return or_(Encounter.user_id == identity.user_id,
               and_(Encounter.user_id == CURATOR_USER_ID, Encounter.shared_with_guests.is_(True)))
