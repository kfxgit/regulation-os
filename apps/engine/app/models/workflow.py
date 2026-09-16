"""ExtractionRun (every AI job logged) and Review (human decisions,
before/after snapshots)."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import ExtractionRunStatus, ReviewDecision


class ExtractionRun(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "extraction_run"

    document_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_version.id")
    )
    model_name: Mapped[str] = mapped_column(String(100))
    model_version: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(50))
    status: Mapped[ExtractionRunStatus] = mapped_column(
        String(20), default=ExtractionRunStatus.RUNNING
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, default=None)


class Review(UUIDPKMixin, TimestampMixin, Base):
    """A human decision on a DRAFT requirement, obligation, or
    relationship. Links to exactly one of the three (never more than
    one, never none)."""

    __tablename__ = "review"
    __table_args__ = (
        CheckConstraint(
            "(num_nonnulls(requirement_id, obligation_id, relationship_id) = 1)",
            name="ck_review_exactly_one_target",
        ),
    )

    requirement_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("regulatory_requirement.id"), default=None
    )
    obligation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("obligation.id"), default=None
    )
    relationship_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("regulatory_relationship.id"), default=None
    )
    reviewer_identifier: Mapped[str] = mapped_column(String(255))
    decision: Mapped[ReviewDecision] = mapped_column(String(20))
    before_snapshot: Mapped[dict] = mapped_column(JSONB)
    after_snapshot: Mapped[dict] = mapped_column(JSONB)
    notes: Mapped[Optional[str]] = mapped_column(Text, default=None)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
