from pathlib import Path

from app.extraction.metadata import extract_document_metadata
from app.extraction.pdf_pages import render_pdf_pages
from app.models.enums import DocumentType
from tests.conftest import live_api

FIXTURE = Path(__file__).parent / "fixtures" / "sample.pdf"


@live_api
def test_extract_document_metadata_from_real_circular():
    """Uses the real BPRD circular if present in data/incoming/; falls
    back to skip if it's not there (it's gitignored, not a repo fixture)."""
    real_circular = Path(__file__).parent.parent / "data" / "incoming" / "BPRD_Circular_No_01.pdf"
    if not real_circular.exists():
        import pytest

        pytest.skip("real circular not present in data/incoming/")

    images = render_pdf_pages(str(real_circular))
    meta = extract_document_metadata(images[0])

    assert "Low Cost Housing" in meta.title
    assert meta.reference_number is not None and "BPRD Circular No. 01" in meta.reference_number
    assert meta.issue_date is not None and meta.issue_date.isoformat() == "2019-03-11"
    assert meta.document_type == DocumentType.CIRCULAR


@live_api
def test_extract_document_metadata_handles_the_placeholder_fixture():
    """The trivial fixture PDF has no real metadata on it -- this proves
    the call doesn't crash and returns null fields rather than inventing
    a reference number or date that isn't there."""
    images = render_pdf_pages(str(FIXTURE))
    meta = extract_document_metadata(images[0])

    assert meta.title  # some title is always produced (even if just "Dummy PDF file")
    # No fabricated reference number or date for a page that states neither.
    assert meta.reference_number is None
    assert meta.issue_date is None
