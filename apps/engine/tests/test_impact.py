"""Tests use a ZZZTEST department code (same pattern as
test_relationship_resolver.py) to avoid colliding with real circular
reference numbers already committed in the shared regos database."""

from app.impact import get_document_impact
from app.models import Document
from app.models.enums import RelationshipType
from tests.factories import make_document_version, make_relationship


def test_outgoing_relationship_shows_up_for_the_citing_document(db_session):
    citing_version = make_document_version(
        db_session, reference_number="ZZZTEST Circular No. 77 of 2021", title="ZZZTEST citing circular"
    )
    relationship = make_relationship(
        db_session,
        citing_version,
        external_reference_text="ZZZTEST Circular No. 55 of 2015",
        relationship_type=RelationshipType.SUPERSEDES,
        status="ACTIVE",
    )
    db_session.commit()

    citing_document = db_session.get(Document, citing_version.document_id)
    impact = get_document_impact(db_session, citing_document)

    assert len(impact.outgoing) == 1
    assert impact.outgoing[0].relationship.id == relationship.id
    assert impact.incoming_resolved == []


def test_incoming_candidate_matches_by_department_number_and_year(db_session):
    citing_version = make_document_version(
        db_session, reference_number="ZZZTEST Circular No. 88 of 2022", title="ZZZTEST citing circular"
    )
    make_relationship(
        db_session,
        citing_version,
        external_reference_text="ZZZTEST Circular No. 55 of 2015",
        relationship_type=RelationshipType.SUPERSEDES,
        status="ACTIVE",
    )
    old_version = make_document_version(
        db_session, reference_number="ZZZTEST Circular No. 55 of 2015", title="ZZZTEST old circular, ingested later"
    )
    db_session.commit()

    old_document = db_session.get(Document, old_version.document_id)
    impact = get_document_impact(db_session, old_document)

    assert len(impact.incoming_candidates) == 1
    assert impact.incoming_candidates[0].other_document.id == citing_version.document_id
    assert impact.incoming_resolved == []  # not a resolved FK, just a candidate match


def test_incoming_candidate_excludes_year_mismatch(db_session):
    # SBP circular numbers reset yearly -- same department+number but a
    # different year on both sides means a genuinely different document,
    # not a match.
    citing_version = make_document_version(
        db_session, reference_number="ZZZTEST Circular No. 66 of 2023", title="ZZZTEST citing circular"
    )
    make_relationship(
        db_session,
        citing_version,
        external_reference_text="ZZZTEST Circular No. 33 of 2019",
        relationship_type=RelationshipType.AMENDS,
        status="ACTIVE",
    )
    unrelated_version = make_document_version(
        db_session, reference_number="ZZZTEST Circular No. 33 of 2012", title="ZZZTEST unrelated circular, same number different year"
    )
    db_session.commit()

    unrelated_document = db_session.get(Document, unrelated_version.document_id)
    impact = get_document_impact(db_session, unrelated_document)

    assert impact.incoming_candidates == []


def test_resolved_fk_shows_up_as_incoming_resolved_not_a_candidate(db_session):
    citing_version = make_document_version(
        db_session, reference_number="ZZZTEST Circular No. 44 of 2024", title="ZZZTEST citing circular"
    )
    old_version = make_document_version(
        db_session, reference_number="ZZZTEST Circular No. 22 of 2018", title="ZZZTEST old circular, already in corpus"
    )
    relationship = make_relationship(
        db_session,
        citing_version,
        to_document_id=old_version.document_id,
        external_reference_text=None,
        relationship_type=RelationshipType.REPLACES,
        status="ACTIVE",
    )
    db_session.commit()

    old_document = db_session.get(Document, old_version.document_id)
    impact = get_document_impact(db_session, old_document)

    assert len(impact.incoming_resolved) == 1
    assert impact.incoming_resolved[0].relationship.id == relationship.id
    assert impact.incoming_resolved[0].other_document.id == citing_version.document_id
    assert impact.incoming_candidates == []  # already resolved, not a mere candidate


def test_draft_relationships_are_excluded(db_session):
    citing_version = make_document_version(
        db_session, reference_number="ZZZTEST Circular No. 99 of 2025", title="ZZZTEST citing circular"
    )
    make_relationship(
        db_session,
        citing_version,
        external_reference_text="ZZZTEST Circular No. 11 of 2010",
        relationship_type=RelationshipType.AMENDS,
        status="DRAFT",  # not yet reviewed -- must not show up as real impact
    )
    db_session.commit()

    citing_document = db_session.get(Document, citing_version.document_id)
    impact = get_document_impact(db_session, citing_document)

    assert impact.outgoing == []
