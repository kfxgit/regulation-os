"""Document metadata extraction: read title/reference/date/type off a
document's own first page image, instead of requiring them typed in by
hand for every file in a batch.

Same separation-of-concerns pattern as OCR vs extraction: this is a
narrow, focused call, not folded into the clause-extraction prompt.
"""

from PIL.Image import Image

from app.core.ai_client import DEFAULT_MODEL, get_anthropic_client
from app.extraction.images import image_to_base64_png
from app.extraction.schema import ExtractedDocumentMetadata

METADATA_PROMPT = """This is the first page of an official regulatory document (a circular, notification, law, rule, guideline, or amendment).

Read off:
- title: the document's title or subject line (often a bold heading).
- reference_number: the official reference/circular number, e.g. "BPRD Circular No. 01 of 2019". If the page does not clearly state one, leave it null -- do not guess or construct one.
- issue_date: the date the document was issued, as stated on the page. If not clearly stated, leave it null -- do not guess.
- document_type: what kind of document this is.

Only use what is actually written on the page. Do not infer a value that is not shown."""


def extract_document_metadata(image: Image, model: str = DEFAULT_MODEL) -> ExtractedDocumentMetadata:
    client = get_anthropic_client()
    image_b64 = image_to_base64_png(image)

    response = client.messages.parse(
        model=model,
        max_tokens=2048,
        output_config={"effort": "low"},  # reading a header, not interpreting a clause
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/png", "data": image_b64},
                    },
                    {"type": "text", "text": METADATA_PROMPT},
                ],
            }
        ],
        output_format=ExtractedDocumentMetadata,
    )
    return response.parsed_output
