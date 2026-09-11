"""Reference / lookup tables: Regulator, and the three hierarchical
applicability taxonomies (EntityType, ProductType, BusinessActivity)."""

import uuid
from typing import Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin


class Regulator(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "regulator"

    name: Mapped[str] = mapped_column(String(255))
    short_code: Mapped[str] = mapped_column(String(20), unique=True)
    country: Mapped[str] = mapped_column(String(100))
    website: Mapped[Optional[str]] = mapped_column(String(500), default=None)


class EntityType(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "entity_type"

    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entity_type.id"), default=None
    )
    code: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(255))


class ProductType(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "product_type"

    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_type.id"), default=None
    )
    code: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(255))


class BusinessActivity(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "business_activity"

    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("business_activity.id"), default=None
    )
    code: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(255))
