from datetime import datetime
from typing import Optional
from sqlalchemy import String, Float, DateTime, Boolean, Text, Integer, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class SpeciesResource(Base):
    """User-added resources (links, images, PDFs) attached to a species card."""

    __tablename__ = "species_resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    species_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(20), nullable=False)  # link | image | pdf
    url: Mapped[Optional[str]] = mapped_column(String(512))      # external URL or served path
    filename: Mapped[Optional[str]] = mapped_column(String(256)) # original filename for uploads
    description: Mapped[Optional[str]] = mapped_column(Text)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EnrichmentSource(Base):
    """
    Raw provenance record for each external data fetch per species.
    Append-only — never delete. One row per (species, source_name) fetch.
    """

    __tablename__ = "enrichment_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    species_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("species.id"), nullable=False, index=True
    )
    source_name: Mapped[str] = mapped_column(String(50), nullable=False)  # "wikidata" | "pfaf"
    source_url: Mapped[Optional[str]] = mapped_column(String(512))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # Full raw response — TEXT, never truncated, never deleted
    raw_response_json: Mapped[Optional[str]] = mapped_column(Text)
    extraction_confidence: Mapped[Optional[float]] = mapped_column(Float)
    parsing_method: Mapped[Optional[str]] = mapped_column(String(30))  # "sparql" | "html_scrape"

    # Relationships
    species: Mapped["Species"] = relationship("Species", back_populates="enrichment_sources")


class CulinaryInfoHistory(Base):
    """
    Audit trail for every manual edit to a culinary_info field.
    Append-only — never delete. One row per save action.
    """

    __tablename__ = "culinary_info_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    culinary_info_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("culinary_info.id"), nullable=False, index=True
    )
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    old_value: Mapped[Optional[str]] = mapped_column(Text)
    new_value: Mapped[Optional[str]] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    changed_by: Mapped[str] = mapped_column(String(100), default="human")
    # Optional source context — used by automated enrichment writers (e.g. fao_fungi+mushroom_observer).
    # Always NULL for human edits.
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class SpeciesEdibilityHistory(Base):
    """
    Audit trail for edits to the species-level edibility verdict fields.
    `field` is 'edibility_status' today; left as a free string (not an enum)
    so 'edibility_verified' can log through the same table later without a
    schema change. Append-only — never delete.

    Distinct from CulinaryInfoHistory: that table tracks culinary_info
    columns and is keyed off culinary_info_id (so it needs a culinary_info
    row to exist first). This tracks Species columns directly, keyed off
    species_id, since edibility_status can be set before any culinary_info
    row exists for a species.

    Added migration 0046 — forward-only, no backfill of prior edibility_status
    changes (those predate this table and live only as unstructured
    CHANGELOG/culinary_info_history entries from one-off curator sessions).
    """

    __tablename__ = "species_edibility_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    species_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("species.id"), nullable=False, index=True
    )
    field: Mapped[str] = mapped_column(String(30), nullable=False)  # 'edibility_status' today
    old_value: Mapped[Optional[str]] = mapped_column(Text)
    new_value: Mapped[Optional[str]] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    changed_by: Mapped[str] = mapped_column(String(100), default="human")
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class SpeciesAIDraft(Base):
    """
    AI-generated draft for a species field — sits in the review queue until
    the user approves, edits-and-approves, or rejects it.

    Rules:
      - Never shown on the species card until status == 'approved' or 'edited_approved'
      - On approval: final_text (or draft_text if not edited) is copied to culinary_info
      - On species rename: all 'pending' drafts for this species are set to 'invalidated'
        and new drafts are regenerated with the new name
      - Never delete rows — append-only audit trail
    """

    __tablename__ = "species_ai_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    species_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("species.id"), nullable=False, index=True
    )
    field_name: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "taste_notes" | "medicinal_notes" | "recipe"

    # The AI-generated text (immutable once written)
    draft_text: Mapped[Optional[str]] = mapped_column(Text)

    # Status lifecycle: pending → approved / edited_approved / rejected / invalidated
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)

    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    approved_by: Mapped[str] = mapped_column(String(100), default="human")

    # User-edited version (None = use draft_text as-is)
    final_text: Mapped[Optional[str]] = mapped_column(Text)

    # Source texts used as context for generation — stored for transparency
    generation_context_json: Mapped[Optional[str]] = mapped_column(Text)
    model: Mapped[Optional[str]] = mapped_column(String(80))  # e.g. "claude-haiku-4-5-20251001"

    species: Mapped["Species"] = relationship("Species", back_populates="ai_drafts")


class Species(Base):
    __tablename__ = "species"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Taxonomy
    scientific_name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    name_key: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    common_names: Mapped[Optional[str]] = mapped_column(Text)     # JSON array — English
    common_names_de: Mapped[Optional[str]] = mapped_column(Text)  # JSON array — German
    preferred_common_name: Mapped[Optional[str]] = mapped_column(String(200))  # human-set sort key
    family: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    genus: Mapped[Optional[str]] = mapped_column(String(100))
    kingdom: Mapped[Optional[str]] = mapped_column(String(50))  # Plantae / Fungi
    gbif_taxon_id: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    inaturalist_taxon_id: Mapped[Optional[str]] = mapped_column(String(50))

    # GBIF full-lineage metadata (migration 0045). Descriptive only — NEVER read
    # by identification, confidence scoring, auto-approve routing, or edibility.
    # Denormalised rank ladder; stores whatever kingdom GBIF returns (Plantae or
    # Fungi), not a hardcoded plant ladder. kingdom/family/genus already exist
    # above and are reused (human-curated values never clobbered by GBIF).
    # DB column names are class_/order_ (trailing underscore) to avoid the SQL
    # reserved words CLASS/ORDER. The canonical GBIF key is gbif_usage_key
    # (defined below) — no separate gbif_taxon_key column.
    phylum: Mapped[Optional[str]] = mapped_column(String(100))
    class_: Mapped[Optional[str]] = mapped_column("class_", String(100))
    order_: Mapped[Optional[str]] = mapped_column("order_", String(100))
    gbif_match_type: Mapped[Optional[str]] = mapped_column(
        String(20)
    )  # EXACT | FUZZY | HIGHERRANK | NONE
    gbif_match_confidence: Mapped[Optional[int]] = mapped_column(Integer)

    # ITIS name validation (additive — never auto-renames approved species)
    itis_tsn: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    itis_accepted_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    itis_name_match: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, index=True
    )  # "accepted" | "synonym" | "no_match" | None (= not yet checked)
    itis_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Edibility (safety-critical: never hallucinate)
    edibility_status: Mapped[Optional[str]] = mapped_column(
        String(30)
    )  # edible | toxic | inedible | unknown | caution
    edibility_source_url: Mapped[Optional[str]] = mapped_column(String(512))
    edibility_confidence: Mapped[Optional[float]] = mapped_column(Float)
    edibility_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    edibility_verified_by: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    # Structured toxicity severity (migration 0039). Drives the safety-render
    # rebuild: 'deadly' → red + skull, 'toxic' → amber, 'none' → normal.
    # Distinct from edibility_status — a 'toxic' edibility can be either
    # severity. Backfilled; never auto-written by enrichment.
    toxicity_severity: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="none"
    )  # none | toxic | deadly

    gbif_usage_key: Mapped[Optional[int]] = mapped_column(Integer, index=True)

    # Phenology — structured harvest / activity months (1–12, comma-separated)
    # Fallback for all "in season" queries: if NULL, photo_taken_at month proxy is used.
    flower_months: Mapped[Optional[str]] = mapped_column(
        String(50)
    )  # e.g. "4,5,6,7" — months when species flowers
    fruit_months: Mapped[Optional[str]] = mapped_column(
        String(50)
    )  # e.g. "8,9,10" — months when fruits / berries are present
    leaf_months: Mapped[Optional[str]] = mapped_column(
        String(50)
    )  # e.g. "3,4,5,6" — months when leaves are harvestable
    peak_season: Mapped[Optional[str]] = mapped_column(
        Text
    )  # free-text harvest note, e.g. "Best harvested April–May before flowering"

    # Per-species running foraging notes (Phase 11a). Free-text field shown in the
    # editable "Foraging Notes" area on the species card. Whisper transcripts from
    # foraging_note encounters are auto-appended here with a datestamp separator.
    # Separate from per-recording encounter transcripts.
    foraging_notes: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Set when an observation moves off / is deleted and leaves this card with
    # NO backing observation (true phantom — see species_link orphan-GC). A
    # reversible marker, not a delete: re-identifying back onto the name clears
    # it. Keyed on zero-observation only, NEVER on review status.
    orphaned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    candidates: Mapped[list["SpeciesCandidate"]] = relationship(
        "SpeciesCandidate", back_populates="species"
    )
    culinary_info: Mapped[Optional["CulinaryInfo"]] = relationship(
        "CulinaryInfo", back_populates="species", uselist=False
    )
    enrichment_sources: Mapped[list["EnrichmentSource"]] = relationship(
        "EnrichmentSource", back_populates="species", cascade="all, delete-orphan"
    )
    ai_drafts: Mapped[list["SpeciesAIDraft"]] = relationship(
        "SpeciesAIDraft", back_populates="species", cascade="all, delete-orphan"
    )
    recipes: Mapped[list["SpeciesRecipe"]] = relationship(
        "SpeciesRecipe", back_populates="species", cascade="all, delete-orphan"
    )
    edibility_conditions: Mapped[list["SpeciesEdibilityCondition"]] = relationship(
        "SpeciesEdibilityCondition",
        back_populates="species",
        cascade="all, delete-orphan",
        foreign_keys="SpeciesEdibilityCondition.species_id",
    )
    lookalikes: Mapped[list["SpeciesLookalike"]] = relationship(
        "SpeciesLookalike",
        back_populates="species",
        cascade="all, delete-orphan",
        foreign_keys="SpeciesLookalike.species_id",
    )
    lookalike_of: Mapped[list["SpeciesLookalike"]] = relationship(
        "SpeciesLookalike",
        back_populates="lookalike_species",
        foreign_keys="SpeciesLookalike.lookalike_species_id",
    )


class SpeciesCandidate(Base):
    """One row per (observation, candidate species) pair from an API call."""

    __tablename__ = "species_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    observation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("observations.id"), nullable=False, index=True
    )
    species_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("species.id"), index=True
    )

    # Raw candidate data (what the API returned)
    scientific_name_raw: Mapped[str] = mapped_column(String(200), nullable=False)
    common_name_raw: Mapped[Optional[str]] = mapped_column(String(200))
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, default=1)  # 1 = top match

    # Source tracking (never invent data)
    api_source: Mapped[str] = mapped_column(String(50))  # plantnet | inaturalist | gbif | manual
    api_response_raw: Mapped[Optional[str]] = mapped_column(Text)  # full JSON blob
    source_url: Mapped[Optional[str]] = mapped_column(String(512))
    identified_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Human review
    human_confirmed: Mapped[Optional[bool]] = mapped_column(Boolean)
    confirmed_by: Mapped[Optional[str]] = mapped_column(String(100))

    # Relationships
    observation: Mapped["Observation"] = relationship(
        "Observation", back_populates="species_candidates"
    )
    species: Mapped[Optional["Species"]] = relationship(
        "Species", back_populates="candidates"
    )


class SpeciesRecipe(Base):
    """
    Recipe bank entry for a species. Multiple recipes per species, each tagged
    with a season. Editing only via the review queue. Never auto-deleted.

    Season values: spring | summer | autumn | winter | year-round
    Source values: ai_generated | human
    Status values: approved | archived
    """

    __tablename__ = "species_recipes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    species_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("species.id"), nullable=False, index=True
    )
    title: Mapped[Optional[str]] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    season: Mapped[str] = mapped_column(String(20), nullable=False, default="year-round", index=True)
    is_preferred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_medicinal_prep: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="ai_generated")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="approved", index=True)
    # notes: free-text flag set by system events (e.g. "species renamed — recipe may be incorrect")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # ai_draft_id: FK back to the originating draft (nullable — human-added recipes have none)
    ai_draft_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("species_ai_drafts.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    species: Mapped["Species"] = relationship("Species", back_populates="recipes")


class SpeciesEdibilityCondition(Base):
    """
    Conditional edibility detail for a species part × preparation × season combination.
    Safe/unsafe ruling sits beneath the top-level edibility_status gate on Species.
    Multiple rows per species — one per distinct (part, preparation, season) condition.

    part values:        leaf | berry | shoot | root | flower | whole | other
    preparation values: raw | cooked | dried | tinctured | any
    season values:      spring | summer | autumn | winter | any
    """

    __tablename__ = "species_edibility_conditions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    species_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("species.id"), nullable=False, index=True
    )

    part: Mapped[str] = mapped_column(String(30), nullable=False)
    preparation: Mapped[str] = mapped_column(String(30), nullable=False)
    season: Mapped[str] = mapped_column(String(20), nullable=False, default="any")

    # Safety ruling: True = safe under these conditions, False = unsafe/toxic
    safe: Mapped[bool] = mapped_column(Boolean, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    species: Mapped["Species"] = relationship(
        "Species",
        back_populates="edibility_conditions",
        foreign_keys=[species_id],
    )


class SpeciesLookalike(Base):
    """
    Lookalike relationship from a species to a potentially dangerous look-alike.
    Directional: species_id → lookalike. Application queries both directions
    (WHERE species_id=X OR lookalike_species_id=X) for bidirectional display.

    lookalike_name is always stored (denormalised) — required when lookalike is not
    in the DB (lookalike_species_id is NULL), and kept as display label when it is.

    toxicity_level values: safe | caution | toxic | deadly
    """

    __tablename__ = "species_lookalikes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    species_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("species.id"), nullable=False, index=True
    )

    # Lookalike identity — at least lookalike_name must always be set
    lookalike_species_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("species.id"), nullable=True, index=True
    )
    lookalike_name: Mapped[str] = mapped_column(String(200), nullable=False)

    distinguishing_notes: Mapped[Optional[str]] = mapped_column(Text)
    toxicity_level: Mapped[str] = mapped_column(String(20), nullable=False, default="caution")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    species: Mapped["Species"] = relationship(
        "Species",
        back_populates="lookalikes",
        foreign_keys=[species_id],
    )
    lookalike_species: Mapped[Optional["Species"]] = relationship(
        "Species",
        back_populates="lookalike_of",
        foreign_keys=[lookalike_species_id],
    )


class SpeciesSynonym(Base):
    """
    Taxonomic-synonym resolution layer. Maps an older/alternate accepted name
    to the species row that now carries the currently-accepted name, so a
    name_key lookup miss on the synonym can resolve to the existing card
    instead of silently creating a duplicate.

    Read-only at resolution time — never touched by enrichment, identification,
    or auto-approval logic beyond a lookup.
    """

    __tablename__ = "species_synonyms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    synonym_name_key: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    synonym_scientific_name: Mapped[str] = mapped_column(String(200), nullable=False)
    canonical_species_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("species.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
