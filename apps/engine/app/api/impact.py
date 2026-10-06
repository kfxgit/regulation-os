"""GET /documents/{document_id}/impact -- see app/impact.py for why this
exists instead of a populated RegulatoryChange table.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.impact import get_document_impact
from app.models import Document
from app.models.enums import RelationshipType

router = APIRouter(tags=["impact"])


class ImpactEdgeResponse(BaseModel):
    relationship_id: UUID
    relationship_type: RelationshipType
    confidence_extraction: Optional[float]
    confidence_classification: Optional[float]
    confidence_source_match: Optional[float]
    other_document_id: Optional[UUID]
    other_document_reference_number: Optional[str]
    external_reference_text: Optional[str]
    citing_requirement_id: Optional[UUID]
    citing_requirement_text: Optional[str]


class DocumentImpactResponse(BaseModel):
    document_id: UUID
    document_reference_number: str
    document_title: str
    outgoing: list[ImpactEdgeResponse]
    incoming_resolved: list[ImpactEdgeResponse]
    incoming_candidates: list[ImpactEdgeResponse]


def _edge_response(edge) -> ImpactEdgeResponse:
    return ImpactEdgeResponse(
        relationship_id=edge.relationship.id,
        relationship_type=edge.relationship.relationship_type,
        confidence_extraction=edge.relationship.confidence_extraction,
        confidence_classification=edge.relationship.confidence_classification,
        confidence_source_match=edge.relationship.confidence_source_match,
        other_document_id=edge.other_document.id if edge.other_document else None,
        other_document_reference_number=edge.other_document.reference_number if edge.other_document else None,
        external_reference_text=edge.relationship.external_reference_text,
        citing_requirement_id=edge.citing_requirement.id if edge.citing_requirement else None,
        citing_requirement_text=edge.citing_requirement.requirement_text if edge.citing_requirement else None,
    )


@router.get("/documents/{document_id}/impact", response_model=DocumentImpactResponse)
def document_impact_endpoint(document_id: UUID, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="No document with that id.")

    impact = get_document_impact(db, document)
    return DocumentImpactResponse(
        document_id=document.id,
        document_reference_number=document.reference_number,
        document_title=document.title,
        outgoing=[_edge_response(e) for e in impact.outgoing],
        incoming_resolved=[_edge_response(e) for e in impact.incoming_resolved],
        incoming_candidates=[_edge_response(e) for e in impact.incoming_candidates],
    )
