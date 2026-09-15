from pathlib import Path

from PIL import Image as PILImage

from app.extraction.pdf_pages import MAX_IMAGE_DIMENSION, _clamp_to_max_dimension, render_pdf_pages

FIXTURE = Path(__file__).parent / "fixtures" / "sample.pdf"


def test_render_pdf_pages_returns_one_image_per_page():
    images = render_pdf_pages(str(FIXTURE))
    assert len(images) == 1
    assert images[0].size[0] > 0
    assert images[0].size[1] > 0


def test_clamp_leaves_small_image_untouched():
    image = PILImage.new("RGB", (1000, 500))
    clamped = _clamp_to_max_dimension(image)
    assert clamped.size == (1000, 500)


def test_clamp_downscales_oversized_image_preserving_aspect_ratio():
    """Reproduces the real failure: an unusually tall scanned page
    (1654x9189, found in a real SBP circular) exceeds the Anthropic
    API's 8000px-per-dimension limit."""
    image = PILImage.new("RGB", (1654, 9189))
    clamped = _clamp_to_max_dimension(image)
    assert max(clamped.size) <= MAX_IMAGE_DIMENSION
    # aspect ratio preserved (within rounding)
    original_ratio = 1654 / 9189
    clamped_ratio = clamped.size[0] / clamped.size[1]
    assert abs(original_ratio - clamped_ratio) < 0.001
