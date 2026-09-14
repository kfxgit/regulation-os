import uuid

from app.models import Obligation, RegulatoryRequirement, Review, SourceCitation
from app.models.enums import ClauseType, RequirementStatus
from scripts.review import (
    approve_requirement,
    correct_requirement,
    reject_all_for_document_version,
    reject_requirement,
)
from tests.factories import (
    make_citation,
    make_document_page,
    make_document_version,
    make_extraction_run,
    make_obligation,
    make_requirement,
)


def _setup(db_session):
    document_version = make_document_version(db_session)
    page = make_document_page(db_session, document_version)
    extraction_run = make_extraction_run(db_session, document_version)
    requirement = make_requirement(db_session, document_version, extraction_run)
    make_citation(db_session, requirement, page)
    obligation = make_obligation(db_session, requirement, extraction_run)
    db_session.commit()
    return requirement, obligation


def test_approve_activates_requirement_and_obligation_and_records_reviews(db_session):
    requirement, obligation = _setup(db_session)

    approve_requirement(db_session, requirement, reviewer="reviewer@example.com")
    db_session.commit()

    reloaded_requirement = db_session.get(type(requirement), requirement.id)
    reloaded_obligation = db_session.get(type(obligation), obligation.id)
    assert reloaded_requirement.status == RequirementStatus.ACTIVE
    assert reloaded_obligation.status == RequirementStatus.ACTIVE

    reviews = (
        db_session.query(Review)
        .filter(
            (Review.requirement_id == requirement.id) | (Review.obligation_id == obligation.id)
        )
        .all()
    )
    assert len(reviews) == 2  # one for the requirement, one for the obligation

    requirement_review = next(r for r in reviews if r.requirement_id == requirement.id)
    assert requirement_review.decision == "APPROVED"
    assert requirement_review.before_snapshot["status"] == "DRAFT"
    assert requirement_review.after_snapshot["status"] == "ACTIVE"

    obligation_review = next(r for r in reviews if r.obligation_id == obligation.id)
    assert obligation_review.decision == "APPROVED"


def test_approve_is_idempotent_no_duplicate_reviews(db_session):
    requirement, obligation = _setup(db_session)

    approve_requirement(db_session, requirement, reviewer="reviewer@example.com")
    db_session.commit()

    # Re-approving an already-ACTIVE requirement should do nothing --
    # both rows are skipped, no new Review rows created.
    requirement = db_session.get(type(requirement), requirement.id)
    approve_requirement(db_session, requirement, reviewer="reviewer@example.com")
    db_session.commit()

    reviews = (
        db_session.query(Review)
        .filter(
            (Review.requirement_id == requirement.id) | (Review.obligation_id == obligation.id)
        )
        .all()
    )
    assert len(reviews) == 2  # still just the original two, not four


def test_reject_leaves_status_draft_but_records_review(db_session):
    requirement, obligation = _setup(db_session)

    reject_requirement(db_session, requirement, reviewer="reviewer@example.com", notes="duplicate")
    db_session.commit()

    reloaded_requirement = db_session.get(type(requirement), requirement.id)
    reloaded_obligation = db_session.get(type(obligation), obligation.id)
    # Rejected rows are never deleted and never activated -- they just
    # stay DRAFT forever, with the rejection itself as the permanent record.
    assert reloaded_requirement.status == "DRAFT"
    assert reloaded_obligation.status == "DRAFT"

    reviews = (
        db_session.query(Review)
        .filter(
            (Review.requirement_id == requirement.id) | (Review.obligation_id == obligation.id)
        )
        .all()
    )
    assert len(reviews) == 2
    assert all(r.decision == "REJECTED" for r in reviews)


def test_reject_all_for_document_version(db_session):
    document_version = make_document_version(db_session)
    page = make_document_page(db_session, document_version)
    extraction_run = make_extraction_run(db_session, document_version)
    req_a = make_requirement(db_session, document_version, extraction_run, stable_key=uuid.uuid4())
    req_b = make_requirement(db_session, document_version, extraction_run, stable_key=uuid.uuid4())
    make_citation(db_session, req_a, page)
    make_citation(db_session, req_b, page)
    db_session.commit()

    count = reject_all_for_document_version(db_session, document_version.id, reviewer="reviewer@example.com")
    db_session.commit()

    assert count == 2
    assert db_session.get(RegulatoryRequirement, req_a.id).status == "DRAFT"
    assert db_session.get(RegulatoryRequirement, req_b.id).status == "DRAFT"


def test_correct_requirement_creates_new_revision_and_supersedes_old(db_session):
    requirement, obligation = _setup(db_session)
    original_stable_key = requirement.stable_key

    new_requirement = correct_requirement(
        db_session,
        requirement,
        {"clause_type": ClauseType.DEFINITION},
        reviewer="reviewer@example.com",
        notes="this is a definition, not a rule",
    )
    db_session.commit()

    # old row: superseded, content untouched (immutability trigger would
    # reject anything else)
    old_reloaded = db_session.get(RegulatoryRequirement, requirement.id)
    assert old_reloaded.status == "SUPERSEDED"
    assert old_reloaded.superseded_by_id == new_requirement.id
    assert old_reloaded.clause_type == "RULE"  # unchanged

    # new row: same stable_key, revision + 1, corrected clause_type, ACTIVE
    new_reloaded = db_session.get(RegulatoryRequirement, new_requirement.id)
    assert new_reloaded.stable_key == original_stable_key
    assert new_reloaded.revision_number == requirement.revision_number + 1
    assert new_reloaded.clause_type == "DEFINITION"
    assert new_reloaded.status == "ACTIVE"

    # new row has its own citation (required for ACTIVE by the DB trigger)
    new_citation = db_session.query(SourceCitation).filter_by(requirement_id=new_requirement.id).first()
    assert new_citation is not None

    # the obligation was carried forward to a new revision too
    old_obligation_reloaded = db_session.get(Obligation, obligation.id)
    assert old_obligation_reloaded.status == "SUPERSEDED"
    new_obligation = (
        db_session.query(Obligation).filter_by(requirement_id=new_requirement.id).first()
    )
    assert new_obligation is not None
    assert new_obligation.status == "ACTIVE"
    assert new_obligation.stable_key == obligation.stable_key
    assert new_obligation.revision_number == obligation.revision_number + 1

    # exactly one CORRECTED review recorded
    review = db_session.query(Review).filter_by(requirement_id=requirement.id).first()
    assert review.decision == "CORRECTED"
    assert review.before_snapshot["clause_type"] == "RULE"
    assert review.after_snapshot["clause_type"] == "DEFINITION"
