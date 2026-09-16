"""RegulatoryRequirement (immutable, stable_key + revision), SourceCitation,
RegulatoryRelationship, RegulatoryChange, ApplicabilityRule.

RegulatoryRequirement is the core of the whole system: it is what the
regulation actually says, structured and verified. Rows here are never
UPDATEd (see the immutability trigger added in the migration) — an
amendment inserts a new row with the same stable_key and a higher
revision_number, and the old row's status flips to SUPERSEDED.
"""

import uuid
from datetime import date
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import ClauseType, RelationshipType, RequirementStatus, ScopeType


class RegulatoryRequirement(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "regulatory_requirement"
    __table_args__ = (
        UniqueConstraint("stable_key", "revision_number", name="uq_requirement_stable_revision"),
    )

    stable_key: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    revision_number: Mapped[int] = mapped_column(Integer)

    document_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_version.id")
    )
    section_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("section.id"), default=None
    )

    clause_type: Mapped[ClauseType] = mapped_column(String(30))
    requirement_text: Mapped[str] = mapped_column(Text)
    status: Mapped[RequirementStatus] = mapped_column(
        String(20), default=RequirementStatus.DRAFT
    )
    superseded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("regulatory_requirement.id"), default=None
    )
    effective_date: Mapped[Optional[date]] = mapped_column(Date, default=None)

    # HIGH-RISK FIELDS GET EXTRA VERIFICATION (CLAUDE.md section 4).
    # Claude must always explicitly decide this (no default in the
    # extraction contract) -- so it's NOT NULL here too, no default.
    contains_high_risk_language: Mapped[bool] = mapped_column(Boolean)
    high_risk_notes: Mapped[Optional[str]] = mapped_column(Text, default=None)

    # Five separate confidence scores. Never a single generic score.
    # No silent defaults: missing stays NULL, never 0.
    confidence_extraction: Mapped[Optional[float]] = mapped_column(Float, default=None)
    confidence_source_match: Mapped[Optional[float]] = mapped_column(Float, default=None)
    confidence_classification: Mapped[Optional[float]] = mapped_column(Float, default=None)
    confidence_applicability: Mapped[Optional[float]] = mapped_column(Float, default=None)
    confidence_interpretation: Mapped[Optional[float]] = mapped_column(Float, default=None)

    extraction_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("extraction_run.id")
    )


class SourceCitation(UUIDPKMixin, TimestampMixin, Base):
    """Proof: every requirement traces to an exact page + character span
    of source text. No citation = unpublishable (enforced in migration)."""

    __tablename__ = "source_citation"

    requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("regulatory_requirement.id")
    )
    document_page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_page.id")
    )
    char_start: Mapped[int] = mapped_column(Integer)
    char_end: Mapped[int] = mapped_column(Integer)
    quoted_text: Mapped[str] = mapped_column(Text)
    match_score: Mapped[Optional[float]] = mapped_column(Float, default=None)


class RegulatoryRelationship(UUIDPKMixin, TimestampMixin, Base):
    """AMENDS/REPLACES/SUPERSEDES etc. between documents.

    In practice, a clause usually references an older circular that
    isn't (yet) in our own corpus -- so to_document_id is optional: when
    the target resolves to a real Document we hold, we link it; when it
    doesn't, we still record what was referenced (external_reference_text)
    rather than silently drop it. Exactly one of the two is always set
    (never both, never neither -- same pattern as Review's exactly-one
    target). AI-derived like everything else here: DRAFT until reviewed,
    with confidence and traceability back to the clause that claimed it.
    """

    __tablename__ = "regulatory_relationship"
    __table_args__ = (
        CheckConstraint(
            "(num_nonnulls(to_document_id, external_reference_text) = 1)",
            name="ck_relationship_exactly_one_target",
        ),
    )

    from_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document.id")
    )
    to_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document.id"), default=None
    )
    external_reference_text: Mapped[Optional[str]] = mapped_column(Text, default=None)
    relationship_type: Mapped[RelationshipType] = mapped_column(String(30))
    description: Mapped[Optional[str]] = mapped_column(Text, default=None)

    status: Mapped[RequirementStatus] = mapped_column(
        String(20), default=RequirementStatus.DRAFT
    )
    confidence_extraction: Mapped[Optional[float]] = mapped_column(Float, default=None)
    source_requirement_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("regulatory_requirement.id"), default=None
    )
    extraction_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("extraction_run.id"), default=None
    )


class RegulatoryChange(UUIDPKMixin, TimestampMixin, Base):
    """Backbone of impact analysis: what changed when a new document
    version arrived."""

    __tablename__ = "regulatory_change"

    document_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_version.id")
    )
    change_type: Mapped[str] = mapped_column(String(20))  # ChangeType
    old_requirement_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("regulatory_requirement.id"), default=None
    )
    new_requirement_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("regulatory_requirement.id"), default=None
    )
    description: Mapped[str] = mapped_column(Text)


class ApplicabilityRule(UUIDPKMixin, TimestampMixin, Base):
    """Who/what a requirement applies to: entity, product, activity, dates.
    INCLUDES/EXCLUDES scoping sits between Requirement and Obligation."""

    __tablename__ = "applicability_rule"

    requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("regulatory_requirement.id")
    )
    scope_type: Mapped[ScopeType] = mapped_column(String(10))
    entity_type_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entity_type.id"), default=None
    )
    product_type_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_type.id"), default=None
    )
    business_activity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("business_activity.id"), default=None
    )
    condition_text: Mapped[Optional[str]] = mapped_column(Text, default=None)
    effective_from: Mapped[Optional[date]] = mapped_column(Date, default=None)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, default=None)
