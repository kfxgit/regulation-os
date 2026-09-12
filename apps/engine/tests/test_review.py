from app.models import Review
from app.models.enums import RequirementStatus
from scripts.review import approve_requirement
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
