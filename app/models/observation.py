from datetime import datetime
from typing import Optional
from sqlalchemy import String, Float, DateTime, Boolean, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

# review_status values that represent a finalized human decision. Background
# identification passes, retries, and bulk-queue actions must never silently
# overwrite these — doing so was the root cause of rejected/approved
# observations reappearing in the review queue (see scan.py, identify.py).
TERMINAL_REVIEW_STATUSES = frozenset({"approved", "manually_verified", "rejected"})


def is_terminal_review_status(status: Optional[str]) -> bool:
    """True if `status` is a finalized review decision that must be protected
    from being overwritten by automated identification/bulk-queue logic."""
    return status in TERMINAL_REVIEW_STATUSES


# ── Phone origin (provenance) ────────────────────────────────────────────────
# The upload_source written by Pipeline 1 (Syncthing): a photo that arrived
# straight off the phone with its capture metadata intact.
#
# This is PROVENANCE and nothing else. It is deliberately NOT the same set as
# scan.py's `requires_forced_review`, which decides whether auto-approve is
# vetoed and — correctly — contains file_upload but not syncthing, the inverse
# of this. One badly-named variable (`is_phone`) previously served both ideas
# and was twice read as provenance when it was a routing veto. Two concepts,
# two names, defined apart on purpose. Do not merge them.
PHONE_ORIGIN_SOURCE = "syncthing"


def is_phone_origin(obs) -> bool:
    """
    True when this observation came off the phone via Syncthing (P1).

    Use for genuine provenance questions — GPS/EXIF trust, P1-only rules.
    Never use it to decide auto-approve eligibility; that is
    scan.py's `requires_forced_review`, which is a different set.
    """
    return getattr(obs, "upload_source", None) == PHONE_ORIGIN_SOURCE


class Observation(Base):
    __tablename__ = "observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # File info
    file_path: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)
    # UNIQUE: the content hash is the dedup key. A DB-level unique index makes the
    # check-then-insert dedup race-proof across concurrent P1/P2 ingest (Tier-2 fix);
    # insert paths catch IntegrityError and return the existing row. SQLite allows
    # multiple NULLs in a unique index, so hash-less rows (none today) stay valid.
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), unique=True, index=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    file_format: Mapped[Optional[str]] = mapped_column(String(10))

    # Thumbnail
    thumbnail_path: Mapped[Optional[str]] = mapped_column(String(1024))

    # Timestamps
    photo_taken_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # GPS (denormalised for fast map queries)
    latitude: Mapped[Optional[float]] = mapped_column(Float, index=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, index=True)
    altitude_m: Mapped[Optional[float]] = mapped_column(Float)
    gps_accuracy_m: Mapped[Optional[float]] = mapped_column(Float)

    # Camera/device
    camera_make: Mapped[Optional[str]] = mapped_column(String(100))
    camera_model: Mapped[Optional[str]] = mapped_column(String(100))

    # Classification flags
    is_plant_likely: Mapped[Optional[bool]] = mapped_column(Boolean)
    plant_detect_confidence: Mapped[Optional[float]] = mapped_column(Float)
    # Why the pre-filter accepted or rejected this image:
    # 'plant' | 'screenshot' | 'ui_blank' | 'person_animal' | 'food_warm' | 'sky_blue' | 'no_plant_signal'
    prefilter_category: Mapped[Optional[str]] = mapped_column(String(30))
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("observations.id"))

    # Review workflow
    review_status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending | approved | rejected | needs_review
    # Controlled vocabulary for why an observation is in the review queue.
    # Set at queue-entry time; NULL = unclassified pre-existing row.
    # Values: low_confidence | non_plant | no_gps | failed_id |
    #         data_trust | needs_enrichment | duplicate_suspect | manual_review
    review_label: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    reviewer_notes: Mapped[Optional[str]] = mapped_column(Text)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    workshop_suitable: Mapped[Optional[bool]] = mapped_column(Boolean)

    # --- Human triage layer (migration 0050) ---
    # Deliberately separate from review_label: that field is machine-written by
    # the scan/trust/audit pipelines and is overwritten on rescan, so it cannot
    # hold a human decision. These are written only by a human triage pass.
    #
    # triage_keep is three-state on purpose:
    #   None = untriaged, True = human keeper, False = explicit human discard.
    # Do not collapse to a default-False boolean — that erases "nobody has
    # looked at this yet", which a delete-by-omission pass depends on.
    triage_keep: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    triage_keep_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # Data protection, orthogonal to triage_keep: True means no other copy of
    # this photo is known to exist on disk. Enforced in delete_observation_file().
    never_reject: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # Processing state
    processing_stage: Mapped[str] = mapped_column(
        String(30), default="ingested"
    )  # ingested | detected | identified | enriched

    # --- Identification layer (populated by identify pipeline, not ingestion) ---
    identification_status: Mapped[Optional[str]] = mapped_column(
        String(40), default="pending_identification", index=True
    )  # pending_identification | identified | failed_identification | not_plant
    # | pending_connection — API call could not run because the device was
    #   offline (timeout/connection error). Re-run via the reconnect hook;
    #   shown in the review queue as 'Awaiting connection — identification not run'.

    # Foreign key to the canonical Species row — the source of truth for which
    # species this observation belongs to. Nullable: an observation can be
    # unidentified, or named with a string that has no Species row yet.
    # species_primary (below) is a synced display cache of the scientific name;
    # every write to species_primary must pair with a write to species_id
    # (see app/services/species_link.py) or the cache desyncs.
    species_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("species.id"), index=True
    )

    # Denormalised top-result fields for fast queries / map display
    species_primary: Mapped[Optional[str]] = mapped_column(String(200), index=True)
    # Best-guess name when confidence is below min_identification_confidence.
    # species_primary is NULL in this case; species_suggested holds the API's
    # top result so the reviewer can still see it without it counting as an ID.
    species_suggested: Mapped[Optional[str]] = mapped_column(String(200))
    # Full JSON array: [{scientific_name, common_name, score, source}]
    species_candidates_json: Mapped[Optional[str]] = mapped_column(Text)
    # Full raw API response blob — never discard, always storable
    plantnet_raw_json: Mapped[Optional[str]] = mapped_column(Text)

    # --- Cached identification quality fields (Phase 10.5) ---
    # top_score: confidence score of the top candidate (candidates[0].score).
    # Cached here so Data Trust queries never need to parse JSON.
    top_score: Mapped[Optional[float]] = mapped_column(Float)
    # dual_source_agreement: 1=both PlantNet+iNat present, 0=single source, NULL=no candidates.
    dual_source_agreement: Mapped[Optional[int]] = mapped_column(Integer)
    # routing_reason: most-recent processing_log message for this observation.
    # Records why it was approved/queued/rejected (best-effort, may be NULL).
    routing_reason: Mapped[Optional[str]] = mapped_column(Text)

    # --- Human correction ---
    # True when a human has overridden the AI species identification.
    # species_primary holds the corrected name; species_candidates_json preserves
    # the original AI candidates so nothing is discarded.
    human_corrected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # --- Post-processing: confirmed copy ---
    # Path to the copy in photos/confirmed_plants/ — None if not yet copied.
    # Original file is NEVER moved or modified.
    confirmed_copy_path: Mapped[Optional[str]] = mapped_column(String(1024))

    # --- Base category ---
    # "plant"     — default; PlantNet + iNaturalist identification
    # "fungi"     — iNaturalist only; always needs_review; amber/orange pin
    # "landscape" — no identification pipeline; manual description; blue pin
    obs_category: Mapped[str] = mapped_column(
        String(20), default="plant", nullable=False, server_default="plant"
    )
    # Auto-suggested category from pipeline (e.g. 'fungi' when top iNat result
    # has iconic_taxon_name='Fungi'). Always user-editable.
    category_suggested: Mapped[Optional[str]] = mapped_column(String(20))

    # --- Upload provenance ---
    # "phone"  = uploaded directly from a browser (phone or desktop)
    # None     = ingested from a local folder scan
    # Path integrity: "phone" uploads in <project_root>/uploads/ are permanent
    # and must never be abandoned if the scan folder is re-linked.
    upload_source: Mapped[Optional[str]] = mapped_column(String(20))

    # --- Ownership (multi-tenancy groundwork) ---
    # Nullable, no FK yet (added in a later supervised migration). Existing rows
    # backfilled to the curator (user_id=1).
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    location: Mapped[Optional["Location"]] = relationship(
        "Location", back_populates="observation", foreign_keys="[Location.observation_id]", uselist=False
    )
    species_candidates: Mapped[list["SpeciesCandidate"]] = relationship(
        "SpeciesCandidate", back_populates="observation", cascade="all, delete-orphan"
    )
    tags: Mapped[list["ObservationTag"]] = relationship(
        "ObservationTag", back_populates="observation", cascade="all, delete-orphan"
    )
    processing_logs: Mapped[list["ProcessingLog"]] = relationship(
        "ProcessingLog", back_populates="observation", cascade="all, delete-orphan"
    )
    edits: Mapped[list["ObservationEdit"]] = relationship(
        "ObservationEdit", back_populates="observation",
        cascade="all, delete-orphan", order_by="ObservationEdit.edited_at"
    )


class DeletedHash(Base):
    """File hashes of permanently deleted observations — prevents re-ingest."""
    __tablename__ = "deleted_hashes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    original_observation_id: Mapped[Optional[int]] = mapped_column(Integer)
    deleted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    deleted_by: Mapped[str] = mapped_column(String(80), default="human")


class ObservationEdit(Base):
    """
    Append-only audit log for human edits to observations.

    Every time a human changes species_primary, reviewer_notes, review_status,
    or any other observation field via the UI, a row is written here.
    Rows are never updated or deleted — the full edit history is always intact.
    """
    __tablename__ = "observation_edits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    observation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("observations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    field_name: Mapped[str] = mapped_column(String(80), nullable=False)
    old_value: Mapped[Optional[str]] = mapped_column(Text)
    new_value: Mapped[Optional[str]] = mapped_column(Text)
    edited_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    edited_by: Mapped[str] = mapped_column(String(80), default="human")

    observation: Mapped["Observation"] = relationship("Observation", back_populates="edits")
