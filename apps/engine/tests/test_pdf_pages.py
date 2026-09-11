from pathlib import Path

from app.extraction.pdf_pages import render_pdf_pages

FIXTURE = Path(__file__).parent / "fixtures" / "sample.pdf"


def test_render_pdf_pages_returns_one_image_per_page():
    images = render_pdf_pages(str(FIXTURE))
    assert len(images) == 1
    assert images[0].size[0] > 0
    assert images[0].size[1] > 0
