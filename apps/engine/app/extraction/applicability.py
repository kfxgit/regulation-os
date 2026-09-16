"""Extract applicability scoping (who/what a clause applies to) from a
requirement's text, via Claude with a Pydantic output contract
(app/extraction/schema.py).

Same pattern as extract.py and relationships.py: narrow, focused call,
structured output, no database writes here.
"""

from app.core.ai_client import DEFAULT_MODEL, get_anthropic_client
from app.extraction.schema import ExtractedApplicabilityRules

APPLICABILITY_PROMPT_TEMPLATE = """This is a clause from an official regulatory document. It may state who or what it applies to -- a type of entity (e.g. banks, DFIs), a type of product (e.g. digital wallets), a business activity, or an additional qualifying condition.

Rules:
- Only extract a rule if the clause actually names or clearly implies a scope. Many clauses (e.g. a definition, a generic "must" statement with no named actor) have no applicability scoping at all -- return an empty list for those.
- scope_type: INCLUDES if the clause says this applies to something; EXCLUDES if the clause says this does NOT apply to something, or carves out an exception for it (e.g. "no minimum requirement is stipulated for DFIs").
- When several distinct entity types are named together (e.g. "Banks/DFIs", "Banks, DFIs and MFBs"), extract ONE separate rule per entity type -- never combine them into one entity_type string like "Banks/DFIs". Each rule's entity_type should name exactly one kind of entity.
- entity_type/product_type: use the exact words from the text for that one entity or product, not a paraphrase or a normalized/expanded name. Leave null if that dimension isn't mentioned.
- business_activity means a LINE OF BUSINESS or business function the entity is engaged in (e.g. "deposit taking", "cross-border remittance", "payment processing") -- NOT the specific action the clause requires. "Banks must submit their CAR returns quarterly" has no business_activity to extract (that's an obligation, not a scoping) -- leave it null.
- condition_text: capture any additional qualifying condition beyond entity/product/activity, exactly as stated (e.g. a shareholding percentage, a channel, a transaction size threshold). Administrative details like who at the bank should receive a letter are not a condition -- leave null for those.
- Do not invent a scope that isn't actually stated. If the clause applies to "everyone" with no restriction stated, that is not a scoping to extract -- leave the list empty.

Clause text:
---
{clause_text}
---"""


def extract_applicability(clause_text: str, model: str = DEFAULT_MODEL) -> ExtractedApplicabilityRules:
    client = get_anthropic_client()
    response = client.messages.parse(
        model=model,
        max_tokens=4096,
        output_config={"effort": "medium"},
        messages=[
            {
                "role": "user",
                "content": APPLICABILITY_PROMPT_TEMPLATE.format(clause_text=clause_text),
            }
        ],
        output_format=ExtractedApplicabilityRules,
    )
    return response.parsed_output
