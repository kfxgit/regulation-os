"""Shared image helpers for the extraction pipeline."""

import base64
from io import BytesIO

from PIL.Image import Image


def image_to_base64_png(image: Image) -> str:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.standard_b64encode(buffer.getvalue()).decode("utf-8")
