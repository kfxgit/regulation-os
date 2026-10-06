"""CLI to record a human review decision and, on approval, activate a
DRAFT requirement and its obligations.

This is the one place status ever moves past DRAFT (CLAUDE.md section 4,
"no silent publishing" -- a human must approve/correct before ACTIVE).
Every approval is recorded as a Review row with a before/after snapshot,
never just a silent status flip.

Usage:
  uv run python -m scripts.review approve-all <document_version_id> --reviewer you@example.com
"""

import argparse
import uuid
from datetime import datetime, timezone

from app.db.session import get_session
from app.models import (
    ApplicabilityRule,
    BusinessActivity,
    EntityType,
    Obligation,
    ProductType,
    RegulatoryRelationship,
    RegulatoryRequirement,
    Review,
    SourceCitation,
)
from app.models.enums import (
    ClauseType,
    ObligationFrequency,
    RelationshipType,
    RequirementStatus,
    ReviewDecision,
    ScopeType,
)


def _enum_value(enum_cls, value):
    """Normalize a str-enum field to its plain value ("DRAFT"), whether
    the ORM handed back the enum instance (a freshly created, unexpired
    row) or a raw string (a row reloaded from the DB). str(x) gives
    inconsistent output between the two ("DRAFT" vs
    "RequirementStatus.DRAFT") -- snapshots must not depend on which one
    the caller happened to have."""
    if value is None:
        return None
    return enum_cls(value).value


def _requirement_snapshot(r: RegulatoryRequirement) -> dict:
    return {
        "id": str(r.id),
        "stable_key": str(r.stable_key),
        "revision_number": r.revision_number,
        "clause_type": _enum_value(ClauseType, r.clause_type),
        "requirement_text": r.requirement_text,
        "status": _enum_value(RequirementStatus, r.status),
        "effective_date": r.effective_date.isoformat() if r.effective_date else None,
        "contains_high_risk_language": r.contains_high_risk_language,
        "high_risk_notes": r.high_risk_notes,
        "confidence_extraction": r.confidence_extraction,
        "confidence_source_match": r.confidence_source_match,
        "confidence_classification": r.confidence_classification,
        "confidence_applicability": r.confidence_applicability,
        "confidence_interpretation": r.confidence_interpretation,
    }


def _obligation_snapshot(o: Obligation) -> dict:
    return {
        "id": str(o.id),
        "stable_key": str(o.stable_key),
        "revision_number": o.revision_number,
        "actor": o.actor,
        "action": o.action,
        "object": o.object,
        "frequency": _enum_value(ObligationFrequency, o.frequency),
        "deadline_description": o.deadline_description,
        "status": _enum_value(RequirementStatus, o.status),
        "confidence_extraction": o.confidence_extraction,
        "confidence_source_match": o.confidence_source_match,
        "confidence_classification": o.confidence_classification,
    }


def _relationship_snapshot(r: RegulatoryRelationship) -> dict:
    return {
        "id": str(r.id),
        "from_document_id": str(r.from_document_id),
        "to_document_id": str(r.to_document_id) if r.to_document_id else None,
        "external_reference_text": r.external_reference_text,
        "relationship_type": _enum_value(RelationshipType, r.relationship_type),
        "status": _enum_value(RequirementStatus, r.status),
        "confidence_extraction": r.confidence_extraction,
    }


def _applicability_snapshot(a: ApplicabilityRule) -> dict:
    return {
        "id": str(a.id),
        "requirement_id": str(a.requirement_id),
        "scope_type": _enum_value(ScopeType, a.scope_type),
        "entity_type_id": str(a.entity_type_id) if a.entity_type_id else None,
        "entity_type_text": a.entity_type_text,
        "product_type_id": str(a.product_type_id) if a.product_type_id else None,
        "product_type_text": a.product_type_text,
        "business_activity_id": str(a.business_activity_id) if a.business_activity_id else None,
        "business_activity_text": a.business_activity_text,
        "condition_text": a.condition_text,
        "status": _enum_value(RequirementStatus, a.status),
        "confidence_extraction": a.confidence_extraction,
    }


def _latest_decision(
    session, *, requirement_id=None, obligation_id=None, relationship_id=None, applicability_rule_id=None
) -> str | None:
    """The most recent Review decision recorded against this requirement,
    obligation, relationship, or applicability rule, or None if it has
    never been reviewed."""
    query = session.query(Review)
    if requirement_id:
        query = query.filter_by(requirement_id=requirement_id)
    elif obligation_id:
        query = query.filter_by(obligation_id=obligation_id)
    elif relationship_id:
        query = query.filter_by(relationship_id=relationship_id)
    else:
        query = query.filter_by(applicability_rule_id=applicability_rule_id)
    latest = query.order_by(Review.reviewed_at.desc()).first()
    return latest.decision if latest else None


def approve_requirement(
    session,
    requirement: RegulatoryRequirement,
    reviewer: str,
    notes: str | None = None,
    override_rejection: bool = False,
):
    """Approve one DRAFT requirement and every obligation linked to it.
    Records a Review row per row activated. Skips anything not DRAFT
    (safe to re-run) and -- critically -- skips anything whose most
    recent review was REJECTED, since a rejected item stays DRAFT
    forever by design (see reject_requirement), and a bulk "approve
    everything still DRAFT" pass must never silently reactivate it.
    Pass override_rejection=True for a deliberate reversal."""
    now = datetime.now(timezone.utc)

    if requirement.status == RequirementStatus.DRAFT:
        if override_rejection or _latest_decision(session, requirement_id=requirement.id) != ReviewDecision.REJECTED.value:
            before = _requirement_snapshot(requirement)
            requirement.status = RequirementStatus.ACTIVE
            session.flush()
            after = _requirement_snapshot(requirement)
            session.add(
                Review(
                    requirement_id=requirement.id,
                    reviewer_identifier=reviewer,
                    decision=ReviewDecision.APPROVED,
                    before_snapshot=before,
                    after_snapshot=after,
                    notes=notes,
                    reviewed_at=now,
                )
            )

    obligations = session.query(Obligation).filter_by(requirement_id=requirement.id).all()
    for obligation in obligations:
        if obligation.status != RequirementStatus.DRAFT:
            continue
        if not override_rejection and _latest_decision(session, obligation_id=obligation.id) == ReviewDecision.REJECTED.value:
            continue
        before = _obligation_snapshot(obligation)
        obligation.status = RequirementStatus.ACTIVE
        session.flush()
        after = _obligation_snapshot(obligation)
        session.add(
            Review(
                obligation_id=obligation.id,
                reviewer_identifier=reviewer,
                decision=ReviewDecision.APPROVED,
                before_snapshot=before,
                after_snapshot=after,
                notes=notes,
                reviewed_at=now,
            )
        )


def reject_requirement(session, requirement: RegulatoryRequirement, reviewer: str, notes: str | None = None):
    """Reject a DRAFT requirement and its obligations: records a Review
    row per row, but never changes status. A rejected requirement stays
    DRAFT forever -- it simply never gets promoted to ACTIVE. Nothing is
    deleted; the rejection itself is the permanent record."""
    now = datetime.now(timezone.utc)

    if requirement.status == RequirementStatus.DRAFT:
        snapshot = _requirement_snapshot(requirement)
        session.add(
            Review(
                requirement_id=requirement.id,
                reviewer_identifier=reviewer,
                decision=ReviewDecision.REJECTED,
                before_snapshot=snapshot,
                after_snapshot=snapshot,  # nothing changes on the row itself
                notes=notes,
                reviewed_at=now,
            )
        )

    obligations = session.query(Obligation).filter_by(requirement_id=requirement.id).all()
    for obligation in obligations:
        if obligation.status != RequirementStatus.DRAFT:
            continue
        snapshot = _obligation_snapshot(obligation)
        session.add(
            Review(
                obligation_id=obligation.id,
                reviewer_identifier=reviewer,
                decision=ReviewDecision.REJECTED,
                before_snapshot=snapshot,
                after_snapshot=snapshot,
                notes=notes,
                reviewed_at=now,
            )
        )


def reject_all_for_document_version(session, document_version_id, reviewer: str, notes: str | None = None) -> int:
    """Reject every DRAFT requirement for one document version (e.g. an
    entire ingested file whose content turned out to be fully redundant
    with another document). Returns the count rejected."""
    requirements = (
        session.query(RegulatoryRequirement)
        .filter_by(document_version_id=document_version_id, status=RequirementStatus.DRAFT)
        .all()
    )
    for requirement in requirements:
        reject_requirement(session, requirement, reviewer, notes)
    return len(requirements)


def approve_relationship(
    session,
    relationship: RegulatoryRelationship,
    reviewer: str,
    notes: str | None = None,
    override_rejection: bool = False,
):
    """Approve one DRAFT relationship. Same rules as approve_requirement:
    skips anything not DRAFT, and skips anything last REJECTED unless
    override_rejection=True."""
    if relationship.status != RequirementStatus.DRAFT:
        return
    if not override_rejection and _latest_decision(session, relationship_id=relationship.id) == ReviewDecision.REJECTED.value:
        return

    before = _relationship_snapshot(relationship)
    relationship.status = RequirementStatus.ACTIVE
    session.flush()
    after = _relationship_snapshot(relationship)
    session.add(
        Review(
            relationship_id=relationship.id,
            reviewer_identifier=reviewer,
            decision=ReviewDecision.APPROVED,
            before_snapshot=before,
            after_snapshot=after,
            notes=notes,
            reviewed_at=datetime.now(timezone.utc),
        )
    )


def reject_relationship(session, relationship: RegulatoryRelationship, reviewer: str, notes: str | None = None):
    """Reject a DRAFT relationship: records a Review row, status stays
    DRAFT forever (same pattern as reject_requirement)."""
    if relationship.status != RequirementStatus.DRAFT:
        return
    snapshot = _relationship_snapshot(relationship)
    session.add(
        Review(
            relationship_id=relationship.id,
            reviewer_identifier=reviewer,
            decision=ReviewDecision.REJECTED,
            before_snapshot=snapshot,
            after_snapshot=snapshot,
            notes=notes,
            reviewed_at=datetime.now(timezone.utc),
        )
    )


def correct_relationship(
    session,
    relationship: RegulatoryRelationship,
    relationship_type: RelationshipType,
    reviewer: str,
    notes: str | None = None,
):
    """Correct a DRAFT relationship's type (e.g. extracted as REFERENCES
    when it should be AMENDS) and activate it. Unlike RegulatoryRequirement,
    RegulatoryRelationship has no stable_key/revision_number -- it isn't
    immutable -- so a correction edits the row in place rather than
    appending a new revision, then records the before/after as a single
    CORRECTED review."""
    if relationship.status != RequirementStatus.DRAFT:
        return

    before = _relationship_snapshot(relationship)
    relationship.relationship_type = relationship_type
    relationship.status = RequirementStatus.ACTIVE
    session.flush()
    after = _relationship_snapshot(relationship)
    session.add(
        Review(
            relationship_id=relationship.id,
            reviewer_identifier=reviewer,
            decision=ReviewDecision.CORRECTED,
            before_snapshot=before,
            after_snapshot=after,
            notes=notes,
            reviewed_at=datetime.now(timezone.utc),
        )
    )


def approve_applicability(
    session,
    rule: ApplicabilityRule,
    reviewer: str,
    notes: str | None = None,
    override_rejection: bool = False,
):
    """Approve one DRAFT applicability rule. Same rules as the others:
    skips anything not DRAFT, and skips anything last REJECTED unless
    override_rejection=True."""
    if rule.status != RequirementStatus.DRAFT:
        return
    if not override_rejection and _latest_decision(session, applicability_rule_id=rule.id) == ReviewDecision.REJECTED.value:
        return

    before = _applicability_snapshot(rule)
    rule.status = RequirementStatus.ACTIVE
    session.flush()
    after = _applicability_snapshot(rule)
    session.add(
        Review(
            applicability_rule_id=rule.id,
            reviewer_identifier=reviewer,
            decision=ReviewDecision.APPROVED,
            before_snapshot=before,
            after_snapshot=after,
            notes=notes,
            reviewed_at=datetime.now(timezone.utc),
        )
    )


def reject_applicability(session, rule: ApplicabilityRule, reviewer: str, notes: str | None = None):
    """Reject a DRAFT applicability rule: records a Review row, status
    stays DRAFT forever (same pattern as reject_requirement)."""
    if rule.status != RequirementStatus.DRAFT:
        return
    snapshot = _applicability_snapshot(rule)
    session.add(
        Review(
            applicability_rule_id=rule.id,
            reviewer_identifier=reviewer,
            decision=ReviewDecision.REJECTED,
            before_snapshot=snapshot,
            after_snapshot=snapshot,
            notes=notes,
            reviewed_at=datetime.now(timezone.utc),
        )
    )


def correct_requirement(session, old_requirement: RegulatoryRequirement, corrections: dict, reviewer: str, notes: str | None = None) -> RegulatoryRequirement:
    """Correct a DRAFT requirement: creates a new revision (same
    stable_key, revision_number + 1) with the corrections applied,
    supersedes the old row, and activates the new one -- a human
    correction during review IS the reviewed, final value, so it goes
    straight to ACTIVE rather than sitting as another DRAFT needing a
    separate approval pass.

    Rows are never edited in place (the immutability trigger would
    reject it anyway) -- this is the same append-a-revision pattern used
    for regulatory amendments, reused for human corrections.
    """
    now = datetime.now(timezone.utc)
    before = _requirement_snapshot(old_requirement)

    old_citation = (
        session.query(SourceCitation).filter_by(requirement_id=old_requirement.id).first()
    )

    new_requirement = RegulatoryRequirement(
        stable_key=old_requirement.stable_key,
        revision_number=old_requirement.revision_number + 1,
        document_version_id=old_requirement.document_version_id,
        section_id=old_requirement.section_id,
        clause_type=corrections.get("clause_type", old_requirement.clause_type),
        requirement_text=corrections.get("requirement_text", old_requirement.requirement_text),
        status=RequirementStatus.DRAFT,  # citation must exist before ACTIVE -- see below
        effective_date=old_requirement.effective_date,
        contains_high_risk_language=old_requirement.contains_high_risk_language,
        high_risk_notes=old_requirement.high_risk_notes,
        confidence_extraction=old_requirement.confidence_extraction,
        confidence_source_match=old_requirement.confidence_source_match,
        confidence_classification=old_requirement.confidence_classification,
        confidence_applicability=old_requirement.confidence_applicability,
        confidence_interpretation=old_requirement.confidence_interpretation,
        extraction_run_id=old_requirement.extraction_run_id,
    )
    session.add(new_requirement)
    session.flush()

    if old_citation is not None:
        session.add(
            SourceCitation(
                requirement_id=new_requirement.id,
                document_page_id=old_citation.document_page_id,
                char_start=old_citation.char_start,
                char_end=old_citation.char_end,
                quoted_text=old_citation.quoted_text,
                match_score=old_citation.match_score,
            )
        )
        session.flush()

    # Now that a citation exists, the DB trigger allows ACTIVE.
    new_requirement.status = RequirementStatus.ACTIVE
    session.flush()

    old_requirement.status = RequirementStatus.SUPERSEDED
    old_requirement.superseded_by_id = new_requirement.id
    session.flush()

    after = _requirement_snapshot(new_requirement)
    session.add(
        Review(
            requirement_id=old_requirement.id,
            reviewer_identifier=reviewer,
            decision=ReviewDecision.CORRECTED,
            before_snapshot=before,
            after_snapshot=after,
            notes=notes,
            reviewed_at=now,
        )
    )

    # Carry obligations forward to the new revision (same pattern: new
    # row, old one superseded -- Obligation has no immutability trigger,
    # but the append-a-revision pattern stays consistent regardless).
    old_obligations = session.query(Obligation).filter_by(requirement_id=old_requirement.id).all()
    for old_obligation in old_obligations:
        new_obligation = Obligation(
            stable_key=old_obligation.stable_key,
            revision_number=old_obligation.revision_number + 1,
            requirement_id=new_requirement.id,
            actor=old_obligation.actor,
            action=old_obligation.action,
            object=old_obligation.object,
            frequency=old_obligation.frequency,
            deadline_description=old_obligation.deadline_description,
            status=RequirementStatus.ACTIVE,
            confidence_extraction=old_obligation.confidence_extraction,
            confidence_source_match=old_obligation.confidence_source_match,
            confidence_classification=old_obligation.confidence_classification,
            extraction_run_id=old_obligation.extraction_run_id,
        )
        session.add(new_obligation)
        session.flush()
        old_obligation.status = RequirementStatus.SUPERSEDED
        old_obligation.superseded_by_id = new_obligation.id

    session.flush()
    return new_requirement


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    approve_all = subparsers.add_parser(
        "approve-all", help="Approve every DRAFT requirement (and obligations) for one document version"
    )
    approve_all.add_argument("document_version_id", type=uuid.UUID)
    approve_all.add_argument("--reviewer", required=True, help="Identifier of the human reviewer, e.g. an email")
    approve_all.add_argument("--notes", default=None)

    reject_document = subparsers.add_parser(
        "reject-document", help="Reject every DRAFT requirement for one document version (e.g. a redundant duplicate ingestion)"
    )
    reject_document.add_argument("document_version_id", type=uuid.UUID)
    reject_document.add_argument("--reviewer", required=True)
    reject_document.add_argument("--notes", default=None)

    list_relationships = subparsers.add_parser(
        "list-relationships", help="List DRAFT relationships pending review"
    )

    approve_relationship_cmd = subparsers.add_parser(
        "approve-relationship", help="Approve one DRAFT relationship"
    )
    approve_relationship_cmd.add_argument("relationship_id", type=uuid.UUID)
    approve_relationship_cmd.add_argument("--reviewer", required=True)
    approve_relationship_cmd.add_argument("--notes", default=None)

    reject_relationship_cmd = subparsers.add_parser(
        "reject-relationship", help="Reject one DRAFT relationship"
    )
    reject_relationship_cmd.add_argument("relationship_id", type=uuid.UUID)
    reject_relationship_cmd.add_argument("--reviewer", required=True)
    reject_relationship_cmd.add_argument("--notes", default=None)

    list_applicability = subparsers.add_parser(
        "list-applicability", help="List DRAFT applicability rules pending review"
    )
    list_applicability.add_argument("--requirement-id", type=uuid.UUID, default=None, help="Only list rules for one requirement")

    approve_applicability_cmd = subparsers.add_parser(
        "approve-applicability", help="Approve one DRAFT applicability rule"
    )
    approve_applicability_cmd.add_argument("rule_id", type=uuid.UUID)
    approve_applicability_cmd.add_argument("--reviewer", required=True)
    approve_applicability_cmd.add_argument("--notes", default=None)

    reject_applicability_cmd = subparsers.add_parser(
        "reject-applicability", help="Reject one DRAFT applicability rule"
    )
    reject_applicability_cmd.add_argument("rule_id", type=uuid.UUID)
    reject_applicability_cmd.add_argument("--reviewer", required=True)
    reject_applicability_cmd.add_argument("--notes", default=None)

    args = parser.parse_args()
    session = get_session()
    try:
        if args.command == "approve-all":
            requirements = (
                session.query(RegulatoryRequirement)
                .filter_by(document_version_id=args.document_version_id, status=RequirementStatus.DRAFT)
                .all()
            )
            if not requirements:
                print("No DRAFT requirements found for that document version.")
                return
            for requirement in requirements:
                approve_requirement(session, requirement, args.reviewer, args.notes)
            session.commit()
            print(f"Approved {len(requirements)} requirement(s) (and their obligations).")
        elif args.command == "reject-document":
            count = reject_all_for_document_version(session, args.document_version_id, args.reviewer, args.notes)
            session.commit()
            print(f"Rejected {count} requirement(s) (and their obligations). They stay DRAFT, never activated.")
        elif args.command == "list-relationships":
            relationships = (
                session.query(RegulatoryRelationship)
                .filter_by(status=RequirementStatus.DRAFT)
                .all()
            )
            if not relationships:
                print("No DRAFT relationships pending review.")
                return
            for r in relationships:
                target = r.external_reference_text or f"document {r.to_document_id}"
                print(f"{r.id}  {r.relationship_type}  -> {target}  (confidence={r.confidence_extraction})")
        elif args.command == "approve-relationship":
            relationship = session.get(RegulatoryRelationship, args.relationship_id)
            if relationship is None:
                print("No relationship with that id.")
                return
            approve_relationship(session, relationship, args.reviewer, args.notes)
            session.commit()
            print("Approved.")
        elif args.command == "reject-relationship":
            relationship = session.get(RegulatoryRelationship, args.relationship_id)
            if relationship is None:
                print("No relationship with that id.")
                return
            reject_relationship(session, relationship, args.reviewer, args.notes)
            session.commit()
            print("Rejected. Stays DRAFT, never activated.")
        elif args.command == "list-applicability":
            query = session.query(ApplicabilityRule).filter_by(status=RequirementStatus.DRAFT)
            if args.requirement_id:
                query = query.filter_by(requirement_id=args.requirement_id)
            rules = query.all()
            if not rules:
                print("No DRAFT applicability rules pending review.")
                return
            for a in rules:
                entity = a.entity_type_text or (
                    session.get(EntityType, a.entity_type_id).name if a.entity_type_id else None
                )
                product = a.product_type_text or (
                    session.get(ProductType, a.product_type_id).name if a.product_type_id else None
                )
                activity = a.business_activity_text or (
                    session.get(BusinessActivity, a.business_activity_id).name if a.business_activity_id else None
                )
                dims = ", ".join(d for d in [entity, product, activity] if d) or "(no dimension)"
                print(f"{a.id}  req={a.requirement_id}  {a.scope_type}: {dims}  condition={a.condition_text!r}  (confidence={a.confidence_extraction})")
        elif args.command == "approve-applicability":
            rule = session.get(ApplicabilityRule, args.rule_id)
            if rule is None:
                print("No applicability rule with that id.")
                return
            approve_applicability(session, rule, args.reviewer, args.notes)
            session.commit()
            print("Approved.")
        elif args.command == "reject-applicability":
            rule = session.get(ApplicabilityRule, args.rule_id)
            if rule is None:
                print("No applicability rule with that id.")
                return
            reject_applicability(session, rule, args.reviewer, args.notes)
            session.commit()
            print("Rejected. Stays DRAFT, never activated.")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
