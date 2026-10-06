"""GET /search/requirements -- the engine's first real query surface over
the knowledge base, per CLAUDE.md section 6 ("search" is one of the
engine's stated responsibilities). Thin wiring only; the actual query
logic lives in app/search.py so it stays testable without spinning up
FastAPI.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enums import ClauseType, RequirementStatus
from app.search import search_requirements

router = APIRouter(prefix="/search", tags=["search"])


class RequirementSearchResult(BaseModel):
    id: UUID
    clause_type: ClauseType
    requirement_text: str
    status: RequirementStatus
    contains_high_risk_language: bool
    confidence_extraction: Optional[float]
    document_id: UUID
    document_reference_number: str
    document_title: str
    rank: Optional[float]


@router.get("/requirements", response_model=list[RequirementSearchResult])
def search_requirements_endpoint(
    q: Optional[str] = Query(default=None, description="Full-text search over requirement_text (plain keywords/phrases)."),
    clause_type: Optional[ClauseType] = None,
    status: Optional[RequirementStatus] = RequirementStatus.ACTIVE,
    entity_type_code: Optional[str] = Query(default=None, description="e.g. 'BANK', 'DFI' -- filters to requirements with an ACTIVE applicability rule for this entity type."),
    high_risk_only: bool = False,
    document_id: Optional[UUID] = None,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    results = search_requirements(
        db,
        query=q,
        clause_type=clause_type.value if clause_type else None,
        status=status.value if status else None,
        entity_type_code=entity_type_code,
        high_risk_only=high_risk_only,
        document_id=document_id,
        limit=limit,
        offset=offset,
    )
    return [
        RequirementSearchResult(
            id=r.requirement.id,
            clause_type=r.requirement.clause_type,
            requirement_text=r.requirement.requirement_text,
            status=r.requirement.status,
            contains_high_risk_language=r.requirement.contains_high_risk_language,
            confidence_extraction=r.requirement.confidence_extraction,
            document_id=r.document.id,
            document_reference_number=r.document.reference_number,
            document_title=r.document.title,
            rank=r.rank,
        )
        for r in results
    ]
