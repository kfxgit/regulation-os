"""Extract document-to-document relationships from a clause's text, via
Claude with a Pydantic output contract (app/extraction/schema.py).

Same pattern as extract.py: narrow, focused call, structured output.
Nothing here writes to the database -- that happens in the pipeline
script (scripts/extract_relationships.py), after a fuzzy-match attempt
to resolve each reference to a Document row we actually hold.
"""

from app.core.ai_client import DEFAULT_MODEL, get_anthropic_client
from app.extraction.schema import ExtractedRelationships

RELATIONSHIP_PROMPT_TEMPLATE = """This is a clause from an official regulatory document. It may reference one or more other specific regulatory documents (a circular, letter, or notification it amends, replaces, or supersedes).

Rules:
- Only extract a relationship if this clause names a SPECIFIC document: something with an identifiable circular/letter number, a date, or both (e.g. "BSD Circular No. 05 dated February 14, 2008", "IBD Circular No. 2 of April 29, 2004").
- Do NOT extract a general framework, standard, or regime name as a document reference -- "the Basel Framework", "Basel III", "SBP regulations", "the prudential regulations" are not specific documents. Skip these.
- target_document_reference must be the referenced document exactly as named in the text -- do not normalize, abbreviate, or guess a fuller name than what is written.
- relationship_type: choose the closest match.
  - AMENDS: this document changes part of the referenced one, without fully replacing it
  - REPLACES / PARTIALLY_REPLACES: this document replaces all or part of the referenced one
  - SUPERSEDES: this document supersedes the referenced one entirely
  - REFERENCES: this document cites the referenced one without amending/replacing it (e.g. "as contained in X")
  - CLARIFIES: this document explains or clarifies the referenced one
  - REPEALS: this document revokes the referenced one
- If the clause does not reference another document, return an empty list. Do not invent a relationship to fill this field.
- A single clause may reference several documents (e.g. a master circular superseding a list of prior letters) -- extract each one separately.

Clause text:
---
{clause_text}
---"""


def extract_relationships(clause_text: str, model: str = DEFAULT_MODEL) -> ExtractedRelationships:
    client = get_anthropic_client()
    response = client.messages.parse(
        model=model,
        max_tokens=4096,
        output_config={"effort": "medium"},
        messages=[
            {
                "role": "user",
                "content": RELATIONSHIP_PROMPT_TEMPLATE.format(clause_text=clause_text),
            }
        ],
        output_format=ExtractedRelationships,
    )
    return response.parsed_output
