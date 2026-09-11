"""OCR step: page image -> raw text, via Claude vision.

This call is deliberately narrow: transcribe only, never interpret. It
is a separate call from extraction (app/extraction/extract.py, next
stage) so the two stay distinct stages with independent confidence and
independent failure modes -- see CLAUDE.md section 5 for why this
still counts as the "mechanical" source-text layer even though it's
AI-based.
"""

import base64
from io import BytesIO

from PIL.Image import Image

from app.core.ai_client import DEFAULT_MODEL, get_anthropic_client

TRANSCRIBE_PROMPT = """Transcribe exactly what is written on this page image. This is a page from an official regulatory document.

Rules:
- Transcribe only. Do not summarize, paraphrase, interpret, or correct anything.
- Preserve paragraph breaks and numbering (e.g. "3.2", "(a)", "(i)") exactly as shown.
- If there is a table, represent it as plain text, keeping rows and columns clear (e.g. one row per line, columns separated by " | ").
- If a word or phrase is illegible, write [illegible] in its place. Do not guess.
- Output only the transcribed text. No preamble, no commentary, no markdown formatting."""


def _image_to_base64_png(image: Image) -> str:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.standard_b64encode(buffer.getvalue()).decode("utf-8")


def transcribe_page(image: Image, model: str = DEFAULT_MODEL) -> str:
    """Transcribe one page image to text.

    Note: the Anthropic API no longer exposes a `temperature` parameter
    (removed as of SDK 1.5.0 / the current Claude 5 API -- confirmed by
    inspecting the SDK, not assumed). Determinism is enforced through the
    prompt (strict "transcribe only" instructions) instead.
    """
    client = get_anthropic_client()
    image_b64 = _image_to_base64_png(image)

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": TRANSCRIBE_PROMPT},
                ],
            }
        ],
    )
    return response.content[0].text
