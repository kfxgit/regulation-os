from pathlib import Path

from app.extraction.ocr import transcribe_page
from app.extraction.pdf_pages import render_pdf_pages
from tests.conftest import live_api

FIXTURE = Path(__file__).parent / "fixtures" / "sample.pdf"


@live_api
def test_transcribe_page_reads_the_actual_text():
    images = render_pdf_pages(str(FIXTURE))
    text = transcribe_page(images[0])
    assert "dummy pdf file" in text.lower()
