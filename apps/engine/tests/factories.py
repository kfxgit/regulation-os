"""Minimal valid prerequisite rows for the integrity tests. Every
regulatory_requirement needs a document_version and an extraction_run to
exist first (foreign keys), so these build just enough of that chain."""

import uuid
from datetime import date, datetime, timezone

from app.models import (
    Document,
    DocumentPage,
    DocumentVersion,
    ExtractionRun,
    Obligation,
    Regulator,
    RegulatoryRequirement,
    SourceCitation,
)
from app.models.enums import ClauseType, DocumentType, ExtractionRunStatus, OcrStatus, RequirementStatus


def make_regulator(session, short_code="TEST"):
    regulator = Regulator(
        name="Test Regulator",
        short_code=short_code,
        country="Testland",
    )
    session.add(regulator)
    session.flush()
    return regulator


def make_document_version(session, regulator=None):
    regulator = regulator or make_regulator(session, short_code=f"TEST-{uuid.uuid4().hex[:8]}")

    document = Document(
        regulator_id=regulator.id,
        title="Test Circular",
        document_type=DocumentType.CIRCULAR,
        reference_number="TEST-001",
        issue_date=date(2024, 1, 1),
    )
    session.add(document)
    session.flush()

    document_version = DocumentVersion(
        document_id=document.id,
        version_number=1,
        file_hash="0" * 64,
        file_uri="file:///test.pdf",
        ocr_status=OcrStatus.DONE,
    )
    session.add(document_version)
    session.flush()
    return document_version


def make_document_page(session, document_version, page_number=1, raw_text=None):
    page = DocumentPage(
        document_version_id=document_version.id,
        page_number=page_number,
        raw_text=raw_text or "Banks must maintain a minimum capital adequacy ratio of 10%.",
    )
    session.add(page)
    session.flush()
    return page


def make_extraction_run(session, document_version):
    run = ExtractionRun(
        document_version_id=document_version.id,
        model_name="gemini-test",
        model_version="test",
        prompt_version="v1",
        status=ExtractionRunStatus.SUCCEEDED,
        started_at=datetime.now(timezone.utc),
    )
    session.add(run)
    session.flush()
    return run


def make_requirement(session, document_version, extraction_run, **overrides):
    defaults = dict(
        stable_key=uuid.uuid4(),
        revision_number=1,
        document_version_id=document_version.id,
        clause_type=ClauseType.RULE,
        requirement_text="Banks must maintain a minimum capital adequacy ratio of 10%.",
        status=RequirementStatus.DRAFT,
        contains_high_risk_language=True,
        extraction_run_id=extraction_run.id,
    )
    defaults.update(overrides)
    requirement = RegulatoryRequirement(**defaults)
    session.add(requirement)
    session.flush()
    return requirement


def make_obligation(session, requirement, extraction_run, **overrides):
    defaults = dict(
        stable_key=uuid.uuid4(),
        revision_number=1,
        requirement_id=requirement.id,
        actor="Banks",
        action="maintain",
        object="minimum capital adequacy ratio",
        status=RequirementStatus.DRAFT,
        extraction_run_id=extraction_run.id,
    )
    defaults.update(overrides)
    obligation = Obligation(**defaults)
    session.add(obligation)
    session.flush()
    return obligation


def make_citation(session, requirement, document_page):
    citation = SourceCitation(
        requirement_id=requirement.id,
        document_page_id=document_page.id,
        char_start=0,
        char_end=10,
        quoted_text="Banks must",
    )
    session.add(citation)
    session.flush()
    return citation
