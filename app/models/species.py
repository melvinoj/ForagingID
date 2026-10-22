from datetime import datetime
from typing import Optional
from sqlalchemy import String, Float, DateTime, Boolean, Text, Integer, ForeignKey, JSON, and_, func
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
    model: Mapped[Optional[str]] = mapped_column(String(80))  # e.g. "deepseek/deepseek-chat"

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
    # rebuild: 'deadly' → red + skull, 'toxic' → amber, 'none' → normal,
    # 'unknown' → never assessed (fails closed — culinary_allowed is False).
    # Distinct from edibility_status — a 'toxic' edibility can be either
    # severity. Written ONLY with the verdict, through severity_for_verdict()
    # (fix batch 3, audit B2-02); never by enrichment.
    # default='unknown' (ORM inserts — every app path that creates a species):
    # a new species is never born "known safe". The DB's server_default stays
    # 'none' (changing it means a SQLite table rebuild); no app code inserts
    # species rows with raw SQL.
    toxicity_severity: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unknown", server_default="none"
    )  # none | toxic | deadly | unknown

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


# ---------------------------------------------------------------------------
# Severity half — the ONLY definition of "toxicity has been assessed as exactly
# 'none'". 'toxic', 'deadly', 'unknown' and anything unrecognised/missing are
# False. It is NOT the culinary rule (that also needs the verdict — below);
# safety_decision() uses it, and so do the experience gates' "toxicity known
# safe" checks (badge wording + rule 7), whose edible claims and recipes are
# gated on the verdict separately (gates.may_claim_edible).
# ---------------------------------------------------------------------------
def severity_is_none(toxicity_severity: Optional[str]) -> bool:
    return toxicity_severity == "none"


# Verdicts that may carry culinary content (Melvin, 21 Oct 2026).
CULINARY_VERDICTS = ("edible", "caution")


# ---------------------------------------------------------------------------
# Culinary guard — "may recipes / culinary content be returned for this
# species?". ONE rule: it delegates to safety_decision() (verdict edible or
# caution AND severity exactly 'none'). Extend safety_decision(); never copy
# the comparison into a call site. The verdict argument is required so a
# caller that only passes severity fails loudly instead of silently allowing.
# ---------------------------------------------------------------------------
def culinary_allowed(toxicity_severity: Optional[str], edibility_status: Optional[str]) -> bool:
    return safety_decision(toxicity_severity, edibility_status)["culinary_allowed"]


# SQL form of culinary_allowed() for queries that join Species — the same rule
# (verdict lowercased + trimmed, as safety_decision normalises it). Kept equal
# to the Python rule by tests/test_batch5_safety_gate.py, which compares the two
# over every severity × verdict combination.
CULINARY_ALLOWED_SQL = and_(
    Species.toxicity_severity == "none",
    func.lower(func.trim(Species.edibility_status)).in_(CULINARY_VERDICTS),
)


# ---------------------------------------------------------------------------
# Known hazard — the ONLY definition of "toxicity_severity says toxic or
# deadly". Used by the critical-hazards review list (app/api/experience.py) and
# the experience export gates (scripts/experience_export/gates.py). Unknown /
# NULL is NOT a known hazard here (severity_is_none() is the fail-closed half
# for that); callers that must fail closed on unknown combine the two.
# ---------------------------------------------------------------------------
TOXIC_SEVERITIES = ("toxic", "deadly")


def is_toxic_severity(toxicity_severity: Optional[str]) -> bool:
    return toxicity_severity in TOXIC_SEVERITIES


# ---------------------------------------------------------------------------
# Safety gate (audit P1 / batch 5, 21 Oct 2026) — the ONLY definition of the
# decision every output shows: may culinary content (edible parts, taste notes,
# recipes) appear, and which safety label goes with the species.
#   culinary_allowed — verdict is 'edible' or 'caution' AND severity is exactly
#                      'none' (Melvin, 21 Oct 2026). Inedible, unknown, NULL,
#                      toxic or any other verdict → no culinary content.
#   level / label    — deadly  → "☠ deadly"
#                      toxic   → "☠ toxic"   (severity toxic, or verdict toxic)
#                      unknown → "⚠ toxicity unknown" (severity not exactly
#                                'none': unknown / NULL / unrecognised; or the
#                                verdict is unknown / NULL — never assessed)
#                      caution → "⚠ caution", warning = the approved caution
#                                warning (curator-authored preparation_warnings)
#                      none    → no label. Culinary content only for 'edible';
#                                an inedible (or other) verdict is blocked
#                                without a label — pages show the verdict badge.
# Served as "safety" by /api/culinary/{name} and /api/species/{name}/profile;
# the PDF and the walk Export summary re-ask it server-side (B2-09). Pages read
# it through frontend/static/js/safety-gate.js and never re-derive it.
# ---------------------------------------------------------------------------
SAFETY_LABELS = {
    "deadly":  "☠ deadly",
    "toxic":   "☠ toxic",
    "unknown": "⚠ toxicity unknown",
    "caution": "⚠ caution",
    "none":    "",
}

# Outgoing surfaces (Melvin, 21 Oct 2026 — batch 6): browser print, PDF, walk
# Export summary, experience page. A CAUTION species with no curator-authored
# preparation warning withholds its culinary content there and carries this
# label instead of "⚠ caution" — experience-gates rule 8, applied to every
# outgoing surface. In-app surfaces keep "⚠ caution" and the culinary content.
# Since 22 Oct 2026 (Melvin): a curator-authored preparation_warnings OR
# look_alike_warnings is enough to print the culinary content.
CAUTION_UNREVIEWED_LABEL = "⚠ caution — warning not yet reviewed"


def safety_decision(toxicity_severity: Optional[str], edibility_status: Optional[str],
                    caution_warning: Optional[str] = None,
                    caution_lookalike: Optional[str] = None) -> dict:
    """caution_warning / caution_lookalike: the CURATOR-AUTHORED preparation /
    look-alike warning text (callers pass None for uncurated text). Either one
    lets a caution species print culinary content on handouts; "warning" stays
    the preparation text only."""
    verdict = (edibility_status or "").strip().lower()
    if toxicity_severity == "deadly":
        level = "deadly"
    elif toxicity_severity == "toxic" or verdict == "toxic":
        level = "toxic"
    elif not severity_is_none(toxicity_severity) or verdict in ("", "unknown"):
        level = "unknown"
    elif verdict == "caution":
        level = "caution"
    else:
        level = "none"
    warning = (caution_warning or "").strip() or None
    culinary = level == "caution" or (level == "none" and verdict == "edible")
    lookalike = (caution_lookalike or "").strip() or None
    caution_unreviewed = level == "caution" and warning is None and lookalike is None
    return {
        # == verdict in CULINARY_VERDICTS and severity_is_none() (levels above)
        "culinary_allowed": culinary,
        "level": level,
        "label": SAFETY_LABELS[level],
        "warning": warning if level == "caution" else None,
        "verdict": verdict or None,     # the DB verdict the decision used (lowercased)
        # Outgoing surfaces only (CAUTION_UNREVIEWED_LABEL above).
        "handout_culinary_allowed": culinary and not caution_unreviewed,
        "handout_label": CAUTION_UNREVIEWED_LABEL if caution_unreviewed else SAFETY_LABELS[level],
    }


# ---------------------------------------------------------------------------
# Placeholder marker (audit E-14) — the ONLY definition of "this text stands in
# for content and is not content": the whole value is one parenthesised phrase
# of at most 80 characters, e.g. "(set)" or "(human-authored
# preparation_warnings)". One-off SQL in June 2026 wrote 11 such
# culinary_info_history rows. A marker is never shown as warning text and never
# counts as curator-authored; the DB refuses new ones (migration 0051, whose
# trigger condition is placeholder_marker_sql() — kept equal to this rule by
# tests/test_batch6_warnings.py).
# ---------------------------------------------------------------------------
PLACEHOLDER_MARKER_MAX = 80
_SQL_WS = "' ' || char(9) || char(10) || char(13)"


def is_placeholder_marker(text: Optional[str]) -> bool:
    t = (text or "").strip(" \t\n\r")
    return 2 <= len(t) <= PLACEHOLDER_MARKER_MAX and t[0] == "(" and t[-1] == ")" and ")" not in t[1:-1]


def placeholder_marker_sql(col: str) -> str:
    """SQLite form of is_placeholder_marker() for a column expression."""
    t = f"trim({col}, {_SQL_WS})"
    return (f"(length({t}) BETWEEN 2 AND {PLACEHOLDER_MARKER_MAX} AND substr({t}, 1, 1) = '(' "
            f"AND substr({t}, -1, 1) = ')' AND instr(substr({t}, 2, length({t}) - 2), ')') = 0)")


# ---------------------------------------------------------------------------
# Species warnings (batch 6, B2-03) — the ONLY definition of which
# preparation / look-alike warning text a surface shows. Every surface reads it
# through the served `safety.warnings` / `safety.handout_warnings`
# (app/services/safety_gate.py → static/js/safety-gate.js; the PDF, Export
# summary and experience export call it server-side).
#   species_warnings — in-app view: the full text of each field (never cut),
#                      with reviewed=True when curator-authored. Empty text,
#                      PFAF's "None known" and placeholder markers are no
#                      warning. In-app pages label reviewed=False text "Source
#                      text — not yet reviewed" and never drop it.
#   handout_warnings — outgoing view: curator-authored text only; a toxic /
#                      deadly species with no curator-authored preparation text
#                      prints TOXIC_FALLBACK_TEXT. Preparation warnings print for
#                      every verdict.
# ---------------------------------------------------------------------------
TOXIC_FALLBACK_TEXT = ("Not safe to eat. Please simply appreciate the natural beauty and power "
                       "of this plant without handling or consuming it.")
WARNING_FIELDS = {"preparation": "preparation_warnings", "look_alike": "look_alike_warnings"}


def warning_text(current: Optional[str]) -> Optional[str]:
    t = (current or "").strip()
    if not t or t.lower() == "none known" or is_placeholder_marker(t):
        return None
    return t


def species_warnings(fields: dict) -> dict:
    """fields: {culinary_info column: (current, latest_changed_by, latest_new_value)}
    for the two WARNING_FIELDS columns (a missing column = no text)."""
    out = {}
    for key, col in WARNING_FIELDS.items():
        cur, by, new = fields.get(col) or (None, None, None)
        t = warning_text(cur)
        out[key] = {"text": t, "reviewed": is_curator_authored(by, new, cur)} if t else None
    return out


def handout_warnings(level: str, warnings: dict) -> dict:
    def reviewed(w):
        return w["text"] if w and w.get("reviewed") else None
    prep = reviewed((warnings or {}).get("preparation"))
    fallback = prep is None and level in TOXIC_SEVERITIES
    return {
        "preparation": TOXIC_FALLBACK_TEXT if fallback else prep,
        "preparation_is_fallback": fallback,
        "look_alike": reviewed((warnings or {}).get("look_alike")),
    }


def culinary_warnings(decision: Optional[dict], handout: bool) -> list:
    """Cautionary text that travels with culinary content (Melvin, 22 Oct 2026
    — Fix B): look-alike then preparation warning, each {kind, heading, text,
    reviewed}. Python twin of SafetyGate.culinaryWarnings (static/js/
    safety-gate.js), for the PDF and the experience page. decision: a served
    safety decision (safety_gate.safety_for_species). handout=True: curator
    text only, uncut; handout=False: in-app text with reviewed (False =
    "Source text — not yet reviewed"). [] when there is no warning text."""
    d = decision or {}
    out = []
    if handout:
        hw = d.get("handout_warnings") or {}
        look, prep = (hw.get("look_alike") or "").strip(), (hw.get("preparation") or "").strip()
        if look:
            out.append({"kind": "look_alike", "heading": "Look-alikes", "text": look, "reviewed": True})
        if prep:
            out.append({"kind": "preparation", "heading": "Caution" if d.get("level") == "caution" else "Preparation",
                        "text": prep, "reviewed": True})
        return out
    w = d.get("warnings") or {}
    for kind, heading in (("look_alike", "Look-alike warning"), ("preparation", "Preparation warning")):
        x = w.get(kind)
        if x and x.get("text"):
            out.append({"kind": kind, "heading": heading, "text": x["text"], "reviewed": bool(x.get("reviewed"))})
    return out


# ---------------------------------------------------------------------------
# Display name — the ONLY server definition of a species' English common name
# for short references (names rule, Melvin 20 Oct 2026: "Common (Latin)",
# Latin alone only when there is no common name). preferred_common_name when
# set (and not a stray JSON list), else the first of common_names (EN).
# Used by map pins, the walk API, critical hazards, the walk summary export and
# scripts/experience_export (en_name). Frontend formatting: _spNameHtml.
# ---------------------------------------------------------------------------
def sentence_case_name(name: Optional[str]) -> str:
    """Display form of ONE English common name (Melvin, 21 Oct 2026): the first
    character upper-cased when it is a letter, the rest exactly as sourced
    ("disc mayweed" → "Disc mayweed", "St John's wort" unchanged). Display
    only — stored names stay as sourced. German names are never passed here.
    JS twin: spCommon() in frontend/static/js/species-names.js."""
    n = (name or "").strip()
    return n[0].upper() + n[1:] if n and n[0].isalpha() else n


def display_common_name(preferred: Optional[str], common_names) -> str:
    return sentence_case_name(_raw_common_name(preferred, common_names))


def _raw_common_name(preferred: Optional[str], common_names) -> str:
    import json as _json
    p = (preferred or "").strip()
    if p and not p.startswith("["):
        return p
    raw = preferred or common_names
    if not raw:
        return ""
    try:
        v = _json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(v, list):
            return str(v[0]).strip() if v else ""
        return str(v).strip()
    except (ValueError, TypeError):
        return str(raw).split(",")[0].strip()



# ---------------------------------------------------------------------------
# Fungal species — the ONLY definition of "this species is a fungus" for the
# observation category rule (observation_service.apply_species_category).
# ---------------------------------------------------------------------------
def is_fungal_kingdom(kingdom: Optional[str]) -> bool:
    return (kingdom or "").strip().lower() == "fungi"


# ---------------------------------------------------------------------------
# Curator-authored field text — the ONLY definition of "the CURRENT value of a
# culinary_info field is curator-authored": the latest culinary_info_history
# row for that field is changed_by='human' AND its new_value equals the current
# value. 'ai_approved:human' (an AI draft a human approved) is NOT curator-
# authored, and neither is 'pfaf_fallback' (PFAF text filled in when no AI text
# was available — Melvin D5, 21 Oct 2026). Used by the experience export gates
# (gates.human_authored) and the curator-review draft approval
# (culinary.approve_ai_draft).
# ---------------------------------------------------------------------------
def is_curator_authored(latest_changed_by: Optional[str], latest_new_value: Optional[str],
                        current: Optional[str]) -> bool:
    cur = (current or "").strip()
    return bool(cur) and latest_changed_by == "human" and (latest_new_value or "").strip() == cur \
        and not is_placeholder_marker(cur)      # E-14: a marker is never content


# ---------------------------------------------------------------------------
# PFAF fallback text (Melvin D2–D5, 21 Oct 2026) — the ONLY definition of "the
# CURRENT value of a field is PFAF text filled in because no AI text was
# available": the latest culinary_info_history row for the field is
# changed_by=PFAF_FALLBACK_CHANGED_BY AND its new_value equals the current value.
# The label is provenance, never a prefix in the stored text; the species card
# and Review show the "PFAF text — replace with your own" chip from this.
# Writer: app/services/pfaf_fallback.py.
# ---------------------------------------------------------------------------
PFAF_FALLBACK_CHANGED_BY = "pfaf_fallback"


def is_pfaf_fallback(latest_changed_by: Optional[str], latest_new_value: Optional[str],
                     current: Optional[str]) -> bool:
    cur = (current or "").strip()
    return bool(cur) and latest_changed_by == PFAF_FALLBACK_CHANGED_BY \
        and (latest_new_value or "").strip() == cur


# Verdicts for which no AI-drafted text is generated at all (safety-critical) —
# and, since 21 Oct 2026, no PFAF fallback text either. The ONLY definition:
# enrichment, section regenerate, Regenerate and the PFAF fallback read it.
AI_NO_CONTENT_VERDICTS = frozenset({"toxic", "inedible", "not_edible"})


# ---------------------------------------------------------------------------
# Curator-review drafts (audit D3-01, Melvin 20 Oct 2026) — draft fields whose
# text is NOT model output: PFAF Known Hazards, or a field's existing text of
# unknown origin, queued in species_ai_drafts for the curator to approve as-is
# or rewrite. Approval IS the curator authoring the text (history
# changed_by='human'). AI regenerate never invalidates these drafts, and the
# review queue's "Approve all" never includes them. Both warning fields since
# 21 Oct 2026 (scripts/import_warning_review_drafts.py, every verdict); Review
# can also Remove the field (curator decision, history row changed_by='human').
# edible_parts / id_notes / seasonal_peak since 22 Oct 2026: enrichment fills
# them only when empty; changed source text for a filled one comes here as a
# review draft (model 'source_update:<source>', enrichment._queue_source_review_drafts).
# ---------------------------------------------------------------------------
CURATOR_DRAFT_FIELDS = frozenset({"preparation_warnings", "look_alike_warnings",
                                  "edible_parts", "id_notes", "seasonal_peak"})


# ---------------------------------------------------------------------------
# Verdict → severity (fix batch 3, audit B2-02 / P2) — the ONLY definition of
# what toxicity_severity becomes when a species' verdict (edibility_status) is
# written. Every verdict writer calls it (PATCH /api/edibility/status,
# /bulk-status, the bracken safety constant) and logs a
# species_edibility_history row when the severity changes.
#
#   'unknown' = never assessed: fails closed everywhere culinary_allowed() is
#   asked. 'deadly' is a severity of a toxic verdict, never a verdict.
#
# Without an explicit severity in the request:
#   toxic     → 'deadly' if already deadly, else 'toxic'
#   edible / caution → 'none' (the verdict is the assessment) — but REFUSED if
#               the species is toxic/deadly now: never lowered automatically
#   inedible  → unchanged ("inedible" ≠ "toxic"; the curator chooses)
#   unknown   → 'unknown' if it was 'none' (a cleared verdict must not read as
#               safe), else unchanged
# With an explicit severity (a curator choice — may relax): it must fit the
# verdict (ALLOWED_SEVERITIES).
# ---------------------------------------------------------------------------
SEVERITY_VALUES = ("none", "toxic", "deadly", "unknown")
UNASSESSED_SEVERITY = "unknown"
ALLOWED_SEVERITIES = {
    "edible":   ("none",),
    "caution":  ("none", "toxic"),
    "inedible": ("none", "toxic", "unknown"),
    "toxic":    ("toxic", "deadly"),
    "unknown":  ("unknown", "toxic", "deadly"),
}


class SeverityRuleError(ValueError):
    """The verdict/severity combination is refused — nothing may be written."""


def severity_for_verdict(verdict: str, current: Optional[str], requested: Optional[str] = None) -> str:
    v = (verdict or "").strip().lower()
    cur = (current or "").strip().lower() or UNASSESSED_SEVERITY
    if cur not in SEVERITY_VALUES:
        cur = UNASSESSED_SEVERITY
    if v not in ALLOWED_SEVERITIES:
        raise SeverityRuleError(f"no severity rule for verdict {verdict!r}")
    if requested is not None and str(requested).strip() != "":
        req = str(requested).strip().lower()
        if req not in SEVERITY_VALUES:
            raise SeverityRuleError(f"toxicity_severity must be one of {list(SEVERITY_VALUES)}")
        if req not in ALLOWED_SEVERITIES[v]:
            raise SeverityRuleError(
                f"verdict {v!r} cannot have severity {req!r} (allowed: {', '.join(ALLOWED_SEVERITIES[v])})")
        return req
    if v == "toxic":
        return "deadly" if cur == "deadly" else "toxic"
    if v in ("edible", "caution"):
        if is_toxic_severity(cur):
            raise SeverityRuleError(
                f"severity is {cur!r} — a {v!r} verdict would lower it; send toxicity_severity "
                f"explicitly ({', '.join(ALLOWED_SEVERITIES[v])}) to relax it")
        return "none"
    if v == "unknown":
        return UNASSESSED_SEVERITY if cur == "none" else cur
    return cur                                                   # inedible: unchanged
