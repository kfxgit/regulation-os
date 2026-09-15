"""Extraction step: page raw text -> structured requirements/obligations,
via Claude with a Pydantic output contract (app/extraction/schema.py).

Separate call from OCR (ocr.py) -- this is the interpretation layer, not
the mechanical transcription layer. Higher effort than OCR: this is the
intelligence-sensitive step. Output is always a DRAFT candidate (see
CLAUDE.md section 4, "no silent publishing") -- nothing here writes to
the database directly; that's a later step, after human review.
"""

from app.core.ai_client import DEFAULT_MODEL, get_anthropic_client
from app.extraction.schema import PageExtractionResult

EXTRACTION_PROMPT_TEMPLATE = """You are extracting structured regulatory requirements from a page of an official regulatory document.

Rules:
- Only extract what this page text actually says. Never infer, assume, or fill in missing details.
- requirement_text must be faithful to the source -- do not drop conditions, exceptions, or qualifiers.
- source_quote must be an exact, verbatim substring of the page text below. Copy it character-for-character, do not paraphrase it.
- If a clause states a deadline, threshold, percentage, or amount, quote it exactly. Never round, generalize, or approximate a number.
- If nothing on this page states a requirement (e.g. it is a cover page, table of contents, or blank page), return an empty requirements list.
- Every extracted requirement needs its own confidence scores. Do not reuse one score across multiple requirements.

Page text:
---
{page_text}
---"""


def extract_requirements(page_text: str, model: str = DEFAULT_MODEL) -> PageExtractionResult:
    client = get_anthropic_client()
    response = client.messages.parse(
        model=model,
        # Found in practice: 8192 was too low. Opus 5 runs thinking by
        # default at effort="high", and thinking + JSON output share this
        # same budget -- a dense page (a master circular, a table-heavy
        # page) can produce enough requirements that the JSON gets cut off
        # mid-string, which Pydantic then fails to parse. Generous headroom
        # here, not a tight guess -- but the SDK itself refuses anything
        # above ~21333 on this non-streaming call (its own timeout math
        # says that could exceed 10 minutes and demands streaming), so
        # this is as high as it goes without a bigger change to add
        # streaming.
        max_tokens=20000,
        # Interpretation/classification -- the intelligence-sensitive step,
        # unlike OCR's mechanical transcription. Higher effort here.
        output_config={"effort": "high"},
        messages=[
            {
                "role": "user",
                "content": EXTRACTION_PROMPT_TEMPLATE.format(page_text=page_text),
            }
        ],
        output_format=PageExtractionResult,
    )
    return response.parsed_output
