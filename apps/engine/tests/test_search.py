import uuid

from app.models import EntityType
from app.models.enums import ClauseType, RequirementStatus
from app.search import search_requirements
from tests.factories import (
    make_applicability_rule,
    make_citation,
    make_document_page,
    make_document_version,
    make_extraction_run,
    make_requirement,
)


def _active_requirement(session, document_version, extraction_run, page, **overrides):
    """search_requirements() defaults to status=ACTIVE, but the citation-
    required trigger forbids inserting a row as ACTIVE directly (no
    citation can exist before the row itself does). Same pattern as
    scripts/review.py's correct_requirement(): insert DRAFT, add the
    citation, then flip to ACTIVE."""
    requirement = make_requirement(
        session, document_version, extraction_run, status=RequirementStatus.DRAFT, **overrides
    )
    make_citation(session, requirement, page)
    requirement.status = RequirementStatus.ACTIVE
    session.flush()
    return requirement


def test_full_text_search_finds_matching_requirement(db_session):
    document_version = make_document_version(db_session)
    page = make_document_page(db_session, document_version)
    extraction_run = make_extraction_run(db_session, document_version)
    match = _active_requirement(
        db_session,
        document_version,
        extraction_run,
        page,
        stable_key=uuid.uuid4(),
        requirement_text="Banks must maintain a minimum capital adequacy ratio of 10 percent.",
    )
    _active_requirement(
        db_session,
        document_version,
        extraction_run,
        page,
        stable_key=uuid.uuid4(),
        requirement_text="Digital wallets must implement multi-factor authentication for login.",
    )
    db_session.commit()

    results = search_requirements(db_session, query="capital adequacy")

    ids = [r.requirement.id for r in results]
    assert match.id in ids
    assert all(r.rank is not None for r in results)


def test_full_text_search_ranks_stronger_match_first(db_session):
    document_version = make_document_version(db_session)
    page = make_document_page(db_session, document_version)
    extraction_run = make_extraction_run(db_session, document_version)
    strong = _active_requirement(
        db_session,
        document_version,
        extraction_run,
        page,
        stable_key=uuid.uuid4(),
        requirement_text="Liquidity coverage ratio liquidity coverage ratio must be reported quarterly.",
    )
    weak = _active_requirement(
        db_session,
        document_version,
        extraction_run,
        page,
        stable_key=uuid.uuid4(),
        requirement_text="Banks must also consider liquidity coverage among several other ratio disclosures.",
    )
    db_session.commit()

    results = search_requirements(db_session, query="liquidity coverage ratio")

    ids = [r.requirement.id for r in results]
    assert ids.index(strong.id) < ids.index(weak.id)


def test_search_excludes_non_matching_text(db_session):
    # A nonsense token, not "mutual fund" or similar real banking
    # terminology: this runs against the real shared regos database
    # (hundreds of real SBP clauses already committed), so a query built
    # from real vocabulary could coincidentally match real production
    # rows and make an exact-empty assertion flaky.
    document_version = make_document_version(db_session)
    page = make_document_page(db_session, document_version)
    extraction_run = make_extraction_run(db_session, document_version)
    _active_requirement(
        db_session,
        document_version,
        extraction_run,
        page,
        stable_key=uuid.uuid4(),
        requirement_text="Exchange companies must report foreign currency positions daily.",
    )
    db_session.commit()

    results = search_requirements(db_session, query="zzqnonexistentquerytoken")

    assert results == []


def test_search_defaults_to_active_status_only(db_session):
    document_version = make_document_version(db_session)
    extraction_run = make_extraction_run(db_session, document_version)
    draft = make_requirement(
        db_session,
        document_version,
        extraction_run,
        stable_key=uuid.uuid4(),
        requirement_text="Banks must submit a zzqdraftreport, pending review.",
        status=RequirementStatus.DRAFT,
    )
    db_session.commit()

    active_only = search_requirements(db_session, query="zzqdraftreport")
    assert draft.id not in [r.requirement.id for r in active_only]

    explicit_draft = search_requirements(db_session, query="zzqdraftreport", status="DRAFT")
    assert draft.id in [r.requirement.id for r in explicit_draft]


def test_search_filters_by_clause_type(db_session):
    document_version = make_document_version(db_session)
    page = make_document_page(db_session, document_version)
    extraction_run = make_extraction_run(db_session, document_version)
    definition = _active_requirement(
        db_session,
        document_version,
        extraction_run,
        page,
        stable_key=uuid.uuid4(),
        clause_type=ClauseType.DEFINITION,
        requirement_text="A Non-Bank Finance Company is an entity licensed under the NBFC rules.",
    )
    rule = _active_requirement(
        db_session,
        document_version,
        extraction_run,
        page,
        stable_key=uuid.uuid4(),
        clause_type=ClauseType.RULE,
        requirement_text="A Non-Bank Finance Company must maintain minimum capital.",
    )
    db_session.commit()

    results = search_requirements(db_session, clause_type="DEFINITION")

    ids = [r.requirement.id for r in results]
    assert definition.id in ids
    assert rule.id not in ids


def test_search_filters_by_high_risk_only(db_session):
    document_version = make_document_version(db_session)
    page = make_document_page(db_session, document_version)
    extraction_run = make_extraction_run(db_session, document_version)
    high_risk = _active_requirement(
        db_session,
        document_version,
        extraction_run,
        page,
        stable_key=uuid.uuid4(),
        requirement_text="Banks must not exceed a leverage ratio of 5 percent.",
        contains_high_risk_language=True,
    )
    ordinary = _active_requirement(
        db_session,
        document_version,
        extraction_run,
        page,
        stable_key=uuid.uuid4(),
        requirement_text="Banks should maintain accurate internal records.",
        contains_high_risk_language=False,
    )
    db_session.commit()

    results = search_requirements(db_session, high_risk_only=True)

    ids = [r.requirement.id for r in results]
    assert high_risk.id in ids
    assert ordinary.id not in ids


def test_search_filters_by_entity_type(db_session):
    bank = db_session.query(EntityType).filter_by(code="BANK").first()
    assert bank is not None, "BANK must be seeded -- run scripts/seed.py"

    document_version = make_document_version(db_session)
    page = make_document_page(db_session, document_version)
    extraction_run = make_extraction_run(db_session, document_version)
    scoped_to_bank = _active_requirement(
        db_session,
        document_version,
        extraction_run,
        page,
        stable_key=uuid.uuid4(),
        requirement_text="Banks must file this specific unique-text return quarterly.",
    )
    not_scoped = _active_requirement(
        db_session,
        document_version,
        extraction_run,
        page,
        stable_key=uuid.uuid4(),
        requirement_text="This clause has no applicability scoping at all.",
    )
    make_applicability_rule(
        db_session,
        scoped_to_bank,
        entity_type_id=bank.id,
        entity_type_text=None,
        status=RequirementStatus.ACTIVE,
    )
    db_session.commit()

    results = search_requirements(db_session, entity_type_code="BANK")

    ids = [r.requirement.id for r in results]
    assert scoped_to_bank.id in ids
    assert not_scoped.id not in ids


def test_search_pagination(db_session):
    # Same reasoning as test_search_excludes_non_matching_text: a nonsense
    # token keeps the total match count exactly 3 (just this test's rows),
    # not "3 plus however many real reserve-requirement clauses already
    # exist in the shared database".
    document_version = make_document_version(db_session)
    page = make_document_page(db_session, document_version)
    extraction_run = make_extraction_run(db_session, document_version)
    for i in range(3):
        _active_requirement(
            db_session,
            document_version,
            extraction_run,
            page,
            stable_key=uuid.uuid4(),
            requirement_text=f"Pagination test clause number {i} about zzqpaginationtoken.",
        )
    db_session.commit()

    page1 = search_requirements(db_session, query="zzqpaginationtoken", limit=2, offset=0)
    page2 = search_requirements(db_session, query="zzqpaginationtoken", limit=2, offset=2)

    assert len(page1) == 2
    assert len(page2) == 1
    assert {r.requirement.id for r in page1}.isdisjoint({r.requirement.id for r in page2})
