"""Structured + full-text search over the regulation knowledge base.

Scoped to RegulatoryRequirement -- the primary unit everything else
(obligations, citations, relationships, applicability) hangs off of.
Full-text search uses Postgres's built-in to_tsvector/websearch_to_tsquery
(a functional GIN index backs it -- see the migration that adds it), not
a new dependency. Semantic search is deferred until pgvector is installed
(CLAUDE.md section 6) -- this covers keyword/phrase search and structured
filters only.

Defaults to status=ACTIVE: a search over the knowledge base should surface
reviewed, trustworthy content by default, not AI-drafted-and-unreviewed
rows. Pass status explicitly to search DRAFT/SUPERSEDED (e.g. for review
tooling).
"""

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import ApplicabilityRule, Document, DocumentVersion, EntityType, RegulatoryRequirement


@dataclass
class SearchResult:
    requirement: RegulatoryRequirement
    document: Document
    rank: Optional[float]  # None when no text query was given (no ranking basis)


def search_requirements(
    session: Session,
    query: Optional[str] = None,
    clause_type: Optional[str] = None,
    status: Optional[str] = "ACTIVE",
    entity_type_code: Optional[str] = None,
    high_risk_only: bool = False,
    document_id: Optional[UUID] = None,
    limit: int = 25,
    offset: int = 0,
) -> list[SearchResult]:
    rank_expr = None
    if query:
        tsvector = func.to_tsvector("english", RegulatoryRequirement.requirement_text)
        tsquery = func.websearch_to_tsquery("english", query)
        rank_expr = func.ts_rank(tsvector, tsquery)

    columns = [RegulatoryRequirement, Document]
    if rank_expr is not None:
        columns.append(rank_expr.label("rank"))

    q = (
        session.query(*columns)
        .join(DocumentVersion, RegulatoryRequirement.document_version_id == DocumentVersion.id)
        .join(Document, DocumentVersion.document_id == Document.id)
    )

    if status is not None:
        q = q.filter(RegulatoryRequirement.status == status)
    if clause_type is not None:
        q = q.filter(RegulatoryRequirement.clause_type == clause_type)
    if high_risk_only:
        q = q.filter(RegulatoryRequirement.contains_high_risk_language.is_(True))
    if document_id is not None:
        q = q.filter(Document.id == document_id)
    if entity_type_code is not None:
        # a requirement can carry more than one ApplicabilityRule row for
        # the same entity (e.g. an INCLUDES and a separate EXCLUDES
        # carve-out) -- distinct() avoids returning it twice.
        q = (
            q.join(ApplicabilityRule, ApplicabilityRule.requirement_id == RegulatoryRequirement.id)
            .join(EntityType, ApplicabilityRule.entity_type_id == EntityType.id)
            .filter(ApplicabilityRule.status == "ACTIVE", EntityType.code == entity_type_code)
            .distinct()
        )

    if rank_expr is not None:
        q = q.filter(tsvector.op("@@")(tsquery)).order_by(rank_expr.desc())
    else:
        q = q.order_by(RegulatoryRequirement.created_at.desc())

    q = q.limit(limit).offset(offset)

    results = []
    for row in q.all():
        if rank_expr is not None:
            requirement, document, rank = row
        else:
            requirement, document = row
            rank = None
        results.append(SearchResult(requirement=requirement, document=document, rank=rank))
    return results
