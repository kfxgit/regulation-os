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
from app.models import Obligation, RegulatoryRequirement, Review
from app.models.enums import ClauseType, ObligationFrequency, RequirementStatus, ReviewDecision


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


def approve_requirement(session, requirement: RegulatoryRequirement, reviewer: str, notes: str | None = None):
    """Approve one DRAFT requirement and every obligation linked to it.
    Records a Review row per row activated. Skips anything not DRAFT,
    so this is safe to re-run."""
    now = datetime.now(timezone.utc)

    if requirement.status == RequirementStatus.DRAFT:
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    approve_all = subparsers.add_parser(
        "approve-all", help="Approve every DRAFT requirement (and obligations) for one document version"
    )
    approve_all.add_argument("document_version_id", type=uuid.UUID)
    approve_all.add_argument("--reviewer", required=True, help="Identifier of the human reviewer, e.g. an email")
    approve_all.add_argument("--notes", default=None)

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
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
