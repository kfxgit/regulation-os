"""PDF -> page images, via pdf2image (which wraps the Poppler binaries
on PATH). This is the first step of the pipeline: PDF -> OCR -> ...

Rendering happens once per document version; the resulting images are
what the OCR step (Claude vision) reads, and what DocumentPage.image_uri
will eventually point at once storage is wired up.
"""

from pdf2image import convert_from_path
from PIL.Image import Image

DEFAULT_DPI = 200


def render_pdf_pages(pdf_path: str, dpi: int = DEFAULT_DPI) -> list[Image]:
    """Render every page of a PDF to a Pillow Image, in page order."""
    return convert_from_path(pdf_path, dpi=dpi)
