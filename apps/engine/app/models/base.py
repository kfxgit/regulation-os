import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base class for all regulation tables (Python-owned side of the DB)."""


class UUIDPKMixin:
    """Standard UUID primary key, generated in Python (no DB extension needed)."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class TimestampMixin:
    """created_at only. Rows in this schema are never updated in place —
    revisions are new rows (see RegulatoryRequirement / Obligation)."""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
