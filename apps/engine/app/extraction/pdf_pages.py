"""PDF -> page images, via pdf2image (which wraps the Poppler binaries
on PATH). This is the first step of the pipeline: PDF -> OCR -> ...

Rendering happens once per document version; the resulting images are
what the OCR step (Claude vision) reads, and what DocumentPage.image_uri
will eventually point at once storage is wired up.
"""

from pdf2image import convert_from_path
from PIL.Image import Image, Resampling

DEFAULT_DPI = 200

# The Anthropic API rejects any image with a dimension over 8000px.
# Found in practice: an unusually tall/long page (e.g. a scanned page
# ~46 inches tall) renders past that at DEFAULT_DPI. Downscale rather
# than fail -- OCR on a slightly-smaller image beats no OCR at all.
MAX_IMAGE_DIMENSION = 8000


def _clamp_to_max_dimension(image: Image) -> Image:
    width, height = image.size
    longest = max(width, height)
    if longest <= MAX_IMAGE_DIMENSION:
        return image
    scale = MAX_IMAGE_DIMENSION / longest
    new_size = (round(width * scale), round(height * scale))
    return image.resize(new_size, Resampling.LANCZOS)


def render_pdf_pages(pdf_path: str, dpi: int = DEFAULT_DPI) -> list[Image]:
    """Render every page of a PDF to a Pillow Image, in page order."""
    images = convert_from_path(pdf_path, dpi=dpi)
    return [_clamp_to_max_dimension(image) for image in images]
