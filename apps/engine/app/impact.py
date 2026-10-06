"""Impact analysis over the relationships we already hold -- "a change
arrives, what is affected downstream" (CLAUDE.md section 3's chain),
built directly on RegulatoryRelationship rather than populating
RegulatoryChange.

Why not RegulatoryChange: checked before building anything here --
0 of the 24 real relationships resolve to a Document we actually hold
content for (every one points to an external circular outside our
corpus), so RegulatoryChange.old_requirement_id would be NULL on every
row we could write today. There's no clause-level diff to store yet.
RegulatoryRelationship already has the real, reviewed data (24 ACTIVE
rows); this module just makes it queryable in both directions instead
of leaving it something you can only browse per-document in the review
page.

Three distinct things a document's "impact" means here:
  - outgoing: relationships this document makes (what it amends/
    supersedes/references), from the real, resolved data.
  - incoming_resolved: relationships where some other document in our
    corpus names THIS one as its target via a real foreign key. Always
    empty today (see above) but correct once a cross-document pair both
    get ingested.
  - incoming_candidates: NOT a resolved link. Reuses the same exact
    (department, number, year) parser relationship_resolver.py uses for
    real resolution, run against this document's own reference_number,
    to surface relationships whose external_reference_text LOOKS like it
    might mean this document. These are unconfirmed by construction --
    labelled as candidates, never silently treated as resolved -- because
    the identifier-matching lesson from relationship_resolver.py applies
    here too: a looser string-similarity match would be unsafe.
"""

from dataclasses import dataclass

from app.extraction.relationship_resolver import parse_document_reference
from app.models import Document, RegulatoryRelationship, RegulatoryRequirement


@dataclass
class ImpactEdge:
    relationship: RegulatoryRelationship
    other_document: Document | None  # None when the other side is still just external_reference_text
    citing_requirement: RegulatoryRequirement | None


@dataclass
class DocumentImpact:
    document: Document
    outgoing: list[ImpactEdge]
    incoming_resolved: list[ImpactEdge]
    incoming_candidates: list[ImpactEdge]


def get_document_impact(session, document: Document) -> DocumentImpact:
    outgoing_rows = (
        session.query(RegulatoryRelationship)
        .filter_by(from_document_id=document.id, status="ACTIVE")
        .all()
    )
    outgoing = [
        ImpactEdge(
            relationship=r,
            other_document=session.get(Document, r.to_document_id) if r.to_document_id else None,
            citing_requirement=session.get(RegulatoryRequirement, r.source_requirement_id)
            if r.source_requirement_id
            else None,
        )
        for r in outgoing_rows
    ]

    incoming_resolved_rows = (
        session.query(RegulatoryRelationship)
        .filter_by(to_document_id=document.id, status="ACTIVE")
        .all()
    )
    incoming_resolved = [
        ImpactEdge(
            relationship=r,
            other_document=session.get(Document, r.from_document_id),
            citing_requirement=session.get(RegulatoryRequirement, r.source_requirement_id)
            if r.source_requirement_id
            else None,
        )
        for r in incoming_resolved_rows
    ]

    incoming_candidates = []
    parsed_self = parse_document_reference(document.reference_number)
    if parsed_self is not None:
        unresolved_rows = (
            session.query(RegulatoryRelationship)
            .filter(
                RegulatoryRelationship.external_reference_text.isnot(None),
                RegulatoryRelationship.status == "ACTIVE",
            )
            .all()
        )
        for r in unresolved_rows:
            parsed_candidate = parse_document_reference(r.external_reference_text)
            if parsed_candidate is None:
                continue
            if parsed_candidate.department != parsed_self.department or parsed_candidate.number != parsed_self.number:
                continue
            if (
                parsed_self.year is not None
                and parsed_candidate.year is not None
                and parsed_self.year != parsed_candidate.year
            ):
                continue  # SBP circular numbers reset yearly -- a year mismatch on both sides means a different document
            incoming_candidates.append(
                ImpactEdge(
                    relationship=r,
                    other_document=session.get(Document, r.from_document_id),
                    citing_requirement=session.get(RegulatoryRequirement, r.source_requirement_id)
                    if r.source_requirement_id
                    else None,
                )
            )

    return DocumentImpact(
        document=document,
        outgoing=outgoing,
        incoming_resolved=incoming_resolved,
        incoming_candidates=incoming_candidates,
    )
