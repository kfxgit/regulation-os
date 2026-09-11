"""Ties OCR + extraction + verification together and persists the result
as DRAFT rows. This is the last step of "PDF -> ... -> PostgreSQL
knowledge base" (CLAUDE.md section 5).

Nothing here ever sets status=ACTIVE -- everything lands as DRAFT. A
human reviewer approves or corrects it before it becomes real (section 4,
"no silent publishing"). Callers control the transaction: this module
flushes (so generated ids are available) but never commits.

Two entry points:
  - ingest_page_text()  -- the core logic (extract, verify, persist) for
    one page, given its text directly. Does not need OCR or a real PDF,
    so it's the one to test with realistic synthetic clause text.
  - ingest_pdf()         -- the full pipeline: render a real PDF, OCR
    each page, then call ingest_page_text() per page.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.ai_client import DEFAULT_MODEL
from app.extraction.extract import extract_requirements
from app.extraction.ocr import transcribe_page
from app.extraction.pdf_pages import render_pdf_pages
from app.extraction.verification import find_citation
from app.models import (
    Document,
    DocumentPage,
    DocumentVersion,
    ExtractionRun,
    Obligation,
    RegulatoryRequirement,
    SourceCitation,
)
from app.models.enums import ExtractionRunStatus, RequirementStatus


def ingest_page_text(
    session: Session,
    document_version: DocumentVersion,
    page: DocumentPage,
    extraction_run: ExtractionRun,
    model: str = DEFAULT_MODEL,
) -> list[RegulatoryRequirement]:
    """Extract requirements/obligations from one page's raw text and
    persist them as DRAFT rows, with fuzzy-matched source citations.
    Returns the created RegulatoryRequirement rows."""
    result = extract_requirements(page.raw_text, model=model)
    created: list[RegulatoryRequirement] = []

    for extracted_req in result.requirements:
        req_match = find_citation(extracted_req.source_quote, page.raw_text)

        db_requirement = RegulatoryRequirement(
            stable_key=uuid.uuid4(),
            revision_number=1,
            document_version_id=document_version.id,
            clause_type=extracted_req.clause_type,
            requirement_text=extracted_req.requirement_text,
            status=RequirementStatus.DRAFT,
            effective_date=extracted_req.effective_date,
            confidence_extraction=extracted_req.confidence_extraction,
            confidence_source_match=req_match.match_score,
            confidence_classification=extracted_req.confidence_classification,
            confidence_interpretation=extracted_req.confidence_interpretation,
            extraction_run_id=extraction_run.id,
        )
        session.add(db_requirement)
        session.flush()

        session.add(
            SourceCitation(
                requirement_id=db_requirement.id,
                document_page_id=page.id,
                char_start=req_match.char_start,
                char_end=req_match.char_end,
                quoted_text=extracted_req.source_quote,
                match_score=req_match.match_score,
            )
        )

        for extracted_obl in extracted_req.obligations:
            obl_match = find_citation(extracted_obl.source_quote, page.raw_text)
            session.add(
                Obligation(
                    stable_key=uuid.uuid4(),
                    revision_number=1,
                    requirement_id=db_requirement.id,
                    actor=extracted_obl.actor,
                    action=extracted_obl.action,
                    object=extracted_obl.object,
                    frequency=extracted_obl.frequency,
                    deadline_description=extracted_obl.deadline_description,
                    status=RequirementStatus.DRAFT,
                    confidence_extraction=extracted_obl.confidence_extraction,
                    confidence_source_match=obl_match.match_score,
                    confidence_classification=extracted_obl.confidence_classification,
                    extraction_run_id=extraction_run.id,
                )
            )

        created.append(db_requirement)

    session.flush()
    return created


def ingest_pdf(
    session: Session,
    document_version: DocumentVersion,
    pdf_path: str,
    model: str = DEFAULT_MODEL,
) -> list[RegulatoryRequirement]:
    """Full pipeline: render every page of pdf_path, OCR it, extract and
    persist. Returns every created RegulatoryRequirement across all pages."""
    extraction_run = ExtractionRun(
        document_version_id=document_version.id,
        model_name=model,
        model_version=model,
        prompt_version="v1",
        status=ExtractionRunStatus.RUNNING,
        started_at=datetime.now(timezone.utc),
    )
    session.add(extraction_run)
    session.flush()

    all_created: list[RegulatoryRequirement] = []
    try:
        images = render_pdf_pages(pdf_path)
        for page_number, image in enumerate(images, start=1):
            raw_text = transcribe_page(image, model=model)
            page = DocumentPage(
                document_version_id=document_version.id,
                page_number=page_number,
                raw_text=raw_text,
            )
            session.add(page)
            session.flush()

            all_created.extend(
                ingest_page_text(session, document_version, page, extraction_run, model=model)
            )
    except Exception as exc:
        extraction_run.status = ExtractionRunStatus.FAILED
        extraction_run.error_message = str(exc)
        extraction_run.completed_at = datetime.now(timezone.utc)
        session.flush()
        raise

    extraction_run.status = ExtractionRunStatus.SUCCEEDED
    extraction_run.completed_at = datetime.now(timezone.utc)
    session.flush()
    return all_created
