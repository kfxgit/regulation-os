"""Document, DocumentVersion, DocumentPage, Section.

Document = the logical regulatory document (e.g. "BPRD Circular No. 5 of 2023").
DocumentVersion = one processed artifact of that document (a specific PDF file /
OCR run). Re-processing (better OCR, a corrected scan) creates a new version;
nothing is overwritten.
"""

import uuid
from datetime import date
from typing import Optional

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import DocumentType, OcrStatus


class Document(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "document"

    regulator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("regulator.id")
    )
    title: Mapped[str] = mapped_column(String(500))
    document_type: Mapped[DocumentType] = mapped_column(String(30))
    reference_number: Mapped[str] = mapped_column(String(255))
    issue_date: Mapped[date] = mapped_column(Date)


class DocumentVersion(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "document_version"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document.id")
    )
    version_number: Mapped[int] = mapped_column(Integer)
    file_hash: Mapped[str] = mapped_column(String(64))
    file_uri: Mapped[str] = mapped_column(String(1000))
    page_count: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    ocr_status: Mapped[OcrStatus] = mapped_column(String(20), default=OcrStatus.PENDING)


class DocumentPage(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "document_page"

    document_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_version.id")
    )
    page_number: Mapped[int] = mapped_column(Integer)
    raw_text: Mapped[Optional[str]] = mapped_column(Text, default=None)
    image_uri: Mapped[Optional[str]] = mapped_column(String(1000), default=None)


class Section(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "section"

    document_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_version.id")
    )
    parent_section_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("section.id"), default=None
    )
    section_number: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    title: Mapped[Optional[str]] = mapped_column(String(500), default=None)
    order_index: Mapped[int] = mapped_column(Integer)
