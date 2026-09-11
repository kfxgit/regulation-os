"""Obligation: what an organization must actually DO. Canonical and
tenant-free — this describes the obligation itself, not any specific
organization's assignment of it (that's Phase 3, Node-owned).

Requirement = what the regulation says. Obligation = actor + action +
object + frequency + deadline. Stored separately, linked by requirement_id.
Same immutable revision pattern as RegulatoryRequirement.
"""

import uuid
from typing import Optional

from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import ObligationFrequency, RequirementStatus


class Obligation(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "obligation"
    __table_args__ = (
        UniqueConstraint("stable_key", "revision_number", name="uq_obligation_stable_revision"),
    )

    stable_key: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    revision_number: Mapped[int] = mapped_column(Integer)

    requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("regulatory_requirement.id")
    )

    actor: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)
    object: Mapped[str] = mapped_column(Text)
    frequency: Mapped[Optional[ObligationFrequency]] = mapped_column(String(20), default=None)
    # High-risk field: a wrong deadline is worse than a missing one.
    # Stays NULL until confirmed, never defaults to a guessed value.
    deadline_description: Mapped[Optional[str]] = mapped_column(Text, default=None)

    status: Mapped[RequirementStatus] = mapped_column(
        String(20), default=RequirementStatus.DRAFT
    )
    superseded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("obligation.id"), default=None
    )

    confidence_extraction: Mapped[Optional[float]] = mapped_column(Float, default=None)
    confidence_source_match: Mapped[Optional[float]] = mapped_column(Float, default=None)
    confidence_classification: Mapped[Optional[float]] = mapped_column(Float, default=None)
    confidence_applicability: Mapped[Optional[float]] = mapped_column(Float, default=None)
    confidence_interpretation: Mapped[Optional[float]] = mapped_column(Float, default=None)

    extraction_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("extraction_run.id")
    )
