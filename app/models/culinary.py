from datetime import datetime
from typing import Optional
from sqlalchemy import String, Float, DateTime, Boolean, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class CulinaryInfo(Base):
    """Culinary enrichment data for a species. Priority display field."""

    __tablename__ = "culinary_info"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    species_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("species.id"), nullable=False, unique=True, index=True
    )

    # --- CULINARY (displayed first) ---
    edible_parts: Mapped[Optional[str]] = mapped_column(Text)
    # e.g. "young leaves, flower buds, seeds"

    flavour_profile: Mapped[Optional[str]] = mapped_column(Text)
    # e.g. "nutty, slightly bitter, umami when cooked"

    preparation_methods: Mapped[Optional[str]] = mapped_column(Text)
    # e.g. "blanch to remove bitterness; use raw in salads when young"

    cooking_techniques: Mapped[Optional[str]] = mapped_column(Text)
    # e.g. "sauté, steam, tempura, ferment"

    preservation_methods: Mapped[Optional[str]] = mapped_column(Text)
    # e.g. "dry, pickle, freeze blanched"

    seasonal_peak: Mapped[Optional[str]] = mapped_column(String(200))
    # e.g. "March–May for leaves; August–September for seeds"

    harvest_stage: Mapped[Optional[str]] = mapped_column(Text)
    # e.g. "harvest before flowering for best flavour"

    pairing_ideas: Mapped[Optional[str]] = mapped_column(Text)
    # e.g. "pairs well with garlic, lemon, strong cheeses"

    culinary_traditions: Mapped[Optional[str]] = mapped_column(Text)
    # e.g. "used in Japanese cuisine as tempura; Eastern European pickling"

    recipe_ideas: Mapped[Optional[str]] = mapped_column(Text)

    workshop_value_score: Mapped[Optional[float]] = mapped_column(Float)
    # 0.0–1.0 score for workshop planning priority

    # --- TRADITIONAL / ETHNOBOTANICAL (secondary) ---
    traditional_uses: Mapped[Optional[str]] = mapped_column(Text)
    cultural_notes: Mapped[Optional[str]] = mapped_column(Text)

    # --- MEDICINAL FOLKLORE (labelled non-medical) ---
    medicinal_folklore: Mapped[Optional[str]] = mapped_column(Text)
    # ALWAYS display with disclaimer: "Traditional use only — not medical advice"

    # --- SAFETY ---
    look_alike_warnings: Mapped[Optional[str]] = mapped_column(Text)
    preparation_warnings: Mapped[Optional[str]] = mapped_column(Text)

    # --- PHASE 8: ID NOTES (from iNaturalist + TrompenburgPlants) ---
    id_notes: Mapped[Optional[str]] = mapped_column(Text)
    id_notes_sources_json: Mapped[Optional[str]] = mapped_column(Text)  # JSON: [{source, url}]
    inat_retrieved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    trompenburg_retrieved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # --- PHASE 8: CULINARY LINKS (links only — no content stored) ---
    # JSON: [{source_label, title, url}, ...] — up to 3 per source
    culinary_links_json: Mapped[Optional[str]] = mapped_column(Text)
    culinary_links_retrieved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # --- PHASE 8: AI-DRAFTED APPROVED FIELDS ---
    # Populated only after explicit approval from the AI draft review queue.
    # Never set directly by enrichment; always flows through species_ai_drafts.
    taste_notes: Mapped[Optional[str]] = mapped_column(Text)
    medicinal_notes: Mapped[Optional[str]] = mapped_column(Text)
    # Human-only structured JSON tags [{source, label, url?}] — no AI path.
    medicinal_clinical: Mapped[Optional[str]] = mapped_column(Text)
    recipe: Mapped[Optional[str]] = mapped_column(Text)

    # --- SOURCING ---
    primary_source_url: Mapped[Optional[str]] = mapped_column(String(512))
    sources_json: Mapped[Optional[str]] = mapped_column(Text)  # JSON array of {name, url}
    data_confidence: Mapped[Optional[float]] = mapped_column(Float)

    # --- DATA PROVENANCE ---
    # JSON list of field names whose values were AI-interpreted (not sourced facts)
    ai_generated_fields_json: Mapped[Optional[str]] = mapped_column(Text)
    # JSON list of AI fields that have been approved and are publicly visible
    ai_approved_fields_json: Mapped[Optional[str]] = mapped_column(Text)
    pfaf_retrieved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    wikidata_retrieved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # --- MANUAL REVIEW FLAG (Phase 11a.2) ---
    # Set by the species-card / Lists "Send to review" button. Surfaces the
    # species in the enrichment review queue regardless of confidence, so the
    # review tab is the single canonical write path to enrichment data.
    # Cleared from the review tab once resolved.
    review_requested: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    review_requested_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    review_request_note: Mapped[Optional[str]] = mapped_column(Text)

    # --- ENRICHMENT REVIEW SIGN-OFF ---
    # True once a curator has approved the AI-generated enrichment text via the
    # Enrichment Review tab (POST /api/culinary/{name}/approve-enrichment).
    # Completely separate from edibility_verified — reviewing enrichment text
    # does NOT constitute confirming the edibility verdict.
    enrichment_reviewed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    species: Mapped["Species"] = relationship("Species", back_populates="culinary_info")
