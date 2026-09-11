"""All regulation models, imported here so Base.metadata sees every table
(needed for Alembic autogenerate)."""

from app.models.base import Base
from app.models.documents import Document, DocumentPage, DocumentVersion, Section
from app.models.obligations import Obligation
from app.models.requirements import (
    ApplicabilityRule,
    RegulatoryChange,
    RegulatoryRelationship,
    RegulatoryRequirement,
    SourceCitation,
)
from app.models.taxonomy import BusinessActivity, EntityType, ProductType, Regulator
from app.models.workflow import ExtractionRun, Review

__all__ = [
    "Base",
    "Regulator",
    "EntityType",
    "ProductType",
    "BusinessActivity",
    "Document",
    "DocumentVersion",
    "DocumentPage",
    "Section",
    "RegulatoryRequirement",
    "SourceCitation",
    "RegulatoryRelationship",
    "RegulatoryChange",
    "ApplicabilityRule",
    "Obligation",
    "ExtractionRun",
    "Review",
]
