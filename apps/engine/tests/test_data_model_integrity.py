"""The 7 database tests that prove the non-negotiable principles in
CLAUDE.md section 4. Each test proves the rule is actually enforced by
the database, not just documented in a comment.
"""

import uuid

import pytest
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.models import Obligation, RegulatoryRelationship, Review
from app.models.enums import ObligationFrequency, RelationshipType, RequirementStatus, ReviewDecision
from tests.factories import (
    make_citation,
    make_document_page,
    make_document_version,
    make_extraction_run,
    make_requirement,
)


@pytest.fixture()
def base_chain(db_session):
    """document_version -> document_page -> extraction_run, the minimum
    a requirement needs to exist."""
    document_version = make_document_version(db_session)
    document_page = make_document_page(db_session, document_version)
    extraction_run = make_extraction_run(db_session, document_version)
    return document_version, document_page, extraction_run


# 1. REQUIREMENTS ARE IMMUTABLE
def test_requirement_content_is_immutable(db_session, base_chain):
    document_version, _document_page, extraction_run = base_chain
    requirement = make_requirement(db_session, document_version, extraction_run)
    db_session.commit()

    original_text = requirement.requirement_text
    requirement.requirement_text = "changed after the fact"

    with pytest.raises(DBAPIError):
        db_session.commit()
    db_session.rollback()

    reloaded = db_session.get(type(requirement), requirement.id)
    assert reloaded.requirement_text == original_text


# 2. stable_key + revision must be unique together
def test_stable_key_revision_must_be_unique(db_session, base_chain):
    document_version, _document_page, extraction_run = base_chain
    stable_key = uuid.uuid4()
    make_requirement(
        db_session, document_version, extraction_run, stable_key=stable_key, revision_number=1
    )
    db_session.commit()

    with pytest.raises(IntegrityError):
        make_requirement(
            db_session, document_version, extraction_run, stable_key=stable_key, revision_number=1
        )
    db_session.rollback()


# 3. NO CITATION = UNPUBLISHABLE
def test_active_requires_at_least_one_citation(db_session, base_chain):
    document_version, document_page, extraction_run = base_chain
    requirement = make_requirement(db_session, document_version, extraction_run)
    db_session.commit()

    requirement.status = RequirementStatus.ACTIVE
    with pytest.raises(DBAPIError):
        db_session.commit()
    db_session.rollback()

    requirement = db_session.get(type(requirement), requirement.id)
    make_citation(db_session, requirement, document_page)
    db_session.commit()

    requirement.status = RequirementStatus.ACTIVE
    db_session.commit()  # now allowed

    reloaded = db_session.get(type(requirement), requirement.id)
    assert reloaded.status == RequirementStatus.ACTIVE


# 4. NO SILENT DEFAULTS on high-risk fields
def test_high_risk_fields_stay_null_not_defaulted(db_session, base_chain):
    document_version, _document_page, extraction_run = base_chain
    requirement = make_requirement(db_session, document_version, extraction_run)
    db_session.commit()

    obligation = Obligation(
        stable_key=uuid.uuid4(),
        revision_number=1,
        requirement_id=requirement.id,
        actor="Banks",
        action="maintain",
        object="minimum capital adequacy ratio",
        extraction_run_id=extraction_run.id,
        # frequency and deadline_description intentionally omitted
    )
    db_session.add(obligation)
    db_session.commit()

    reloaded = db_session.get(Obligation, obligation.id)
    assert reloaded.frequency is None
    assert reloaded.deadline_description is None
    assert requirement.confidence_extraction is None
    assert requirement.confidence_source_match is None


# 5. NOTHING IS DELETED -- superseding keeps the old row, unchanged, linked
def test_supersede_preserves_old_row(db_session, base_chain):
    document_version, document_page, extraction_run = base_chain
    stable_key = uuid.uuid4()

    rev1 = make_requirement(
        db_session, document_version, extraction_run, stable_key=stable_key, revision_number=1
    )
    db_session.commit()
    original_text = rev1.requirement_text
    original_created_at = rev1.created_at

    rev2 = make_requirement(
        db_session,
        document_version,
        extraction_run,
        stable_key=stable_key,
        revision_number=2,
        requirement_text="Banks must maintain a minimum capital adequacy ratio of 12%.",
    )
    db_session.commit()

    rev1.status = RequirementStatus.SUPERSEDED
    rev1.superseded_by_id = rev2.id
    db_session.commit()  # only status + superseded_by_id changed -- allowed

    reloaded_rev1 = db_session.get(type(rev1), rev1.id)
    assert reloaded_rev1.status == RequirementStatus.SUPERSEDED
    assert reloaded_rev1.superseded_by_id == rev2.id
    assert reloaded_rev1.requirement_text == original_text  # content untouched
    assert reloaded_rev1.created_at == original_created_at

    rows_for_stable_key = (
        db_session.query(type(rev1)).filter_by(stable_key=stable_key).all()
    )
    assert len(rows_for_stable_key) == 2  # both revisions still present


# 6. FIVE SEPARATE CONFIDENCE SCORES, never one generic score
def test_five_confidence_scores_are_independent(db_session, base_chain):
    document_version, _document_page, extraction_run = base_chain
    requirement = make_requirement(
        db_session,
        document_version,
        extraction_run,
        confidence_extraction=0.95,
        confidence_source_match=0.80,
        confidence_classification=0.70,
        confidence_applicability=0.60,
        confidence_interpretation=0.50,
    )
    db_session.commit()

    reloaded = db_session.get(type(requirement), requirement.id)
    scores = {
        reloaded.confidence_extraction,
        reloaded.confidence_source_match,
        reloaded.confidence_classification,
        reloaded.confidence_applicability,
        reloaded.confidence_interpretation,
    }
    assert scores == {0.95, 0.80, 0.70, 0.60, 0.50}  # 5 distinct values, 5 distinct columns


# 7. Review links to exactly one of requirement / obligation
def test_review_must_link_exactly_one_target(db_session, base_chain):
    document_version, document_page, extraction_run = base_chain
    requirement = make_requirement(db_session, document_version, extraction_run)
    make_citation(db_session, requirement, document_page)
    db_session.commit()

    obligation = Obligation(
        stable_key=uuid.uuid4(),
        revision_number=1,
        requirement_id=requirement.id,
        actor="Banks",
        action="maintain",
        object="minimum capital adequacy ratio",
        extraction_run_id=extraction_run.id,
    )
    db_session.add(obligation)
    db_session.commit()

    import datetime as dt

    # exactly one target: valid
    valid_review = Review(
        requirement_id=requirement.id,
        obligation_id=None,
        reviewer_identifier="reviewer@example.com",
        decision=ReviewDecision.APPROVED,
        before_snapshot={"status": "DRAFT"},
        after_snapshot={"status": "ACTIVE"},
        reviewed_at=dt.datetime.now(dt.timezone.utc),
    )
    db_session.add(valid_review)
    db_session.commit()

    # both targets set: invalid
    both_review = Review(
        requirement_id=requirement.id,
        obligation_id=obligation.id,
        reviewer_identifier="reviewer@example.com",
        decision=ReviewDecision.APPROVED,
        before_snapshot={},
        after_snapshot={},
        reviewed_at=dt.datetime.now(dt.timezone.utc),
    )
    db_session.add(both_review)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # neither target set: invalid
    neither_review = Review(
        requirement_id=None,
        obligation_id=None,
        reviewer_identifier="reviewer@example.com",
        decision=ReviewDecision.APPROVED,
        before_snapshot={},
        after_snapshot={},
        reviewed_at=dt.datetime.now(dt.timezone.utc),
    )
    db_session.add(neither_review)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # a Review can also target a relationship (the 3rd option), alone
    relationship = RegulatoryRelationship(
        from_document_id=document_version.document_id,
        to_document_id=None,
        external_reference_text="some external circular",
        relationship_type=RelationshipType.AMENDS,
    )
    db_session.add(relationship)
    db_session.commit()

    relationship_review = Review(
        relationship_id=relationship.id,
        reviewer_identifier="reviewer@example.com",
        decision=ReviewDecision.APPROVED,
        before_snapshot={"status": "DRAFT"},
        after_snapshot={"status": "ACTIVE"},
        reviewed_at=dt.datetime.now(dt.timezone.utc),
    )
    db_session.add(relationship_review)
    db_session.commit()

    # requirement + relationship together: still invalid (must be exactly one)
    two_targets_review = Review(
        requirement_id=requirement.id,
        relationship_id=relationship.id,
        reviewer_identifier="reviewer@example.com",
        decision=ReviewDecision.APPROVED,
        before_snapshot={},
        after_snapshot={},
        reviewed_at=dt.datetime.now(dt.timezone.utc),
    )
    db_session.add(two_targets_review)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# 8. RegulatoryRelationship must link to exactly one target: an in-corpus
# Document, or an external_reference_text for one we don't hold (yet) --
# never both, never neither. Most real references point outside our
# corpus, so this isn't an edge case -- it's the common case.
def test_relationship_must_link_exactly_one_target(db_session):
    from_version = make_document_version(db_session)
    to_version = make_document_version(db_session)

    # exactly one target (external reference): valid
    external_ref = RegulatoryRelationship(
        from_document_id=from_version.document_id,
        to_document_id=None,
        external_reference_text="BSD Circular No. 05 dated February 14, 2008",
        relationship_type=RelationshipType.SUPERSEDES,
    )
    db_session.add(external_ref)
    db_session.commit()

    # exactly one target (resolved document): valid
    resolved_ref = RegulatoryRelationship(
        from_document_id=from_version.document_id,
        to_document_id=to_version.document_id,
        external_reference_text=None,
        relationship_type=RelationshipType.AMENDS,
    )
    db_session.add(resolved_ref)
    db_session.commit()

    # both set: invalid
    both = RegulatoryRelationship(
        from_document_id=from_version.document_id,
        to_document_id=to_version.document_id,
        external_reference_text="some circular",
        relationship_type=RelationshipType.AMENDS,
    )
    db_session.add(both)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # neither set: invalid
    neither = RegulatoryRelationship(
        from_document_id=from_version.document_id,
        to_document_id=None,
        external_reference_text=None,
        relationship_type=RelationshipType.AMENDS,
    )
    db_session.add(neither)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
