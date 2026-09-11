from pathlib import Path

from app.extraction.pipeline import ingest_page_text, ingest_pdf
from app.models import Obligation, SourceCitation
from app.models.enums import ExtractionRunStatus
from tests.conftest import live_api
from tests.factories import make_document_page, make_document_version, make_extraction_run

FIXTURE = Path(__file__).parent / "fixtures" / "sample.pdf"

CAR_PAGE_TEXT = """3.2 Capital Adequacy Ratio

Every bank shall maintain, at all times, a minimum Capital Adequacy Ratio (CAR) of 10% of its risk-weighted assets, calculated on a consolidated basis as prescribed under Basel III guidelines. Banks that fail to meet this requirement must submit a capital restoration plan to the State Bank of Pakistan within thirty (30) days of the shortfall being identified."""


@live_api
def test_ingest_page_text_persists_requirements_citations_and_obligations(db_session):
    document_version = make_document_version(db_session)
    extraction_run = make_extraction_run(db_session, document_version)
    page = make_document_page(db_session, document_version, raw_text=CAR_PAGE_TEXT)

    created = ingest_page_text(db_session, document_version, page, extraction_run)
    db_session.commit()

    assert len(created) >= 1
    car_requirement = next(r for r in created if "10%" in r.requirement_text)

    # DRAFT, never auto-approved (see CLAUDE.md "no silent publishing").
    # Compared as a plain string: after commit(), SQLAlchemy expires the
    # object and reloads status as the raw DB string, not the enum
    # instance -- RequirementStatus is a str subclass so "==" still works.
    assert car_requirement.status == "DRAFT"

    # Five confidence scores present and distinct fields, source_match
    # computed by our fuzzy-match code, not self-reported by the AI.
    assert car_requirement.confidence_extraction is not None
    assert car_requirement.confidence_source_match is not None
    assert car_requirement.confidence_source_match > 0.9  # exact quote from real text

    citation = (
        db_session.query(SourceCitation)
        .filter_by(requirement_id=car_requirement.id)
        .first()
    )
    assert citation is not None
    assert citation.quoted_text in CAR_PAGE_TEXT

    obligations = (
        db_session.query(Obligation).filter_by(requirement_id=car_requirement.id).all()
    )
    assert len(obligations) >= 1
    assert obligations[0].actor


@live_api
def test_ingest_pdf_runs_end_to_end_without_crashing(db_session):
    document_version = make_document_version(db_session)

    created = ingest_pdf(db_session, document_version, str(FIXTURE))
    db_session.commit()

    # The fixture PDF has no regulatory content ("Dummy PDF file"), so
    # zero or more requirements is fine -- what matters is that OCR,
    # extraction, and persistence all ran without error.
    assert isinstance(created, list)

    from app.models import DocumentPage, ExtractionRun

    page = (
        db_session.query(DocumentPage)
        .filter_by(document_version_id=document_version.id)
        .first()
    )
    assert page is not None
    assert "dummy" in page.raw_text.lower()

    run = (
        db_session.query(ExtractionRun)
        .filter_by(document_version_id=document_version.id)
        .first()
    )
    assert run.status == ExtractionRunStatus.SUCCEEDED
