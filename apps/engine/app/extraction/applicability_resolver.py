"""Resolve extracted entity/product/business-activity text against our
taxonomy tables (EntityType/ProductType/BusinessActivity), or correctly
decline to.

Same philosophy as relationship_resolver.py: our taxonomies are thin
seed lists, not a comprehensive reference, so most real extractions
won't resolve -- and guessing a close-but-wrong match (e.g. "Islamic
Banking Subsidiaries" matching "Islamic Bank") is worse than leaving it
as unresolved text. Only normalized exact matches (case-insensitive,
simple plural stripped, underscores treated as spaces) resolve; every
code AND name is checked, since our codes are often the real-world
abbreviation ("DFI") while the name is the expanded form ("Development
Finance Institution") that rarely appears verbatim in a clause.
"""

import re

# Real abbreviations seen in actual clauses that don't match their
# taxonomy row's code directly (the row is seeded under its full name's
# code instead) -- normalized alias -> normalized target code.
_ENTITY_ALIASES = {
    "mfb": "microfinance bank",
    "member fi": "fi",
    "lead/agent fi": "fi",
}


def _normalize(text: str) -> str:
    text = text.strip().lower()
    text = text.replace("_", " ")
    text = re.sub(r"\s+", " ", text)
    if text.endswith("ies"):
        text = text[:-3] + "y"
    elif text.endswith("s") and not text.endswith("ss"):
        text = text[:-1]
    return text


def _resolve(session, model_cls, text: str):
    normalized = _normalize(text)
    for row in session.query(model_cls).all():
        if _normalize(row.code) == normalized or _normalize(row.name) == normalized:
            return row
    return None


def resolve_entity_type(session, text: str):
    from app.models import EntityType

    resolved = _resolve(session, EntityType, text)
    if resolved is not None:
        return resolved
    alias_target = _ENTITY_ALIASES.get(_normalize(text))
    if alias_target is not None:
        return _resolve(session, EntityType, alias_target)
    return None


def resolve_product_type(session, text: str):
    from app.models import ProductType

    return _resolve(session, ProductType, text)


def resolve_business_activity(session, text: str):
    from app.models import BusinessActivity

    return _resolve(session, BusinessActivity, text)
