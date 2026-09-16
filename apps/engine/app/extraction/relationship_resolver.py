"""Resolve an extracted document reference (e.g. "BSD Circular No. 05
dated February 14, 2008") to a Document row we actually hold.

Why not just fuzzy-match the strings: tried it (rapidfuzz token_set_ratio)
and it's unsafe here. "BPRD Circular No. 08" vs "BPRD Circular No. 10"
scores 95% similar -- HIGHER than a genuine cross-document match scored
in testing (94%) -- because circular reference strings share almost all
their words ("Circular", "No.", the department code) and differ only in
the one token that actually matters: the number. A generic similarity
score is the wrong tool for an identifier comparison.

Instead: parse the (department code, circular number, year) out of both
the query and every candidate, and require an exact match on department
+ number (+ year, when both sides have one -- SBP circular numbers reset
per year, so the same department+number can legitimately refer to two
different documents issued years apart). No year on one side is only
treated as unambiguous if exactly one candidate shares that
department+number regardless of year; if there's more than one, we
refuse to guess and leave it unresolved rather than risk linking the
wrong document.
"""

import re
from dataclasses import dataclass
from typing import Optional

from app.models import Document

# Department/office code, then "Circular" (or "File letter"), optionally
# "Letter", then "No." and a number. Handles "BC & CPD", "DI&SD", "BSD",
# "BPRD", "IBD", "CPD", "FD" etc.
_REFERENCE_PATTERN = re.compile(
    r"(?P<dept>[A-Z][A-Z&]*(?:\s*&\s*[A-Z]+)?)\s*"
    r"(?:Circular|File\s+letter)\s*"
    r"(?:Letter\s*)?"
    r"No\.?\s*(?P<number>\d+)",
    re.IGNORECASE,
)

# A 4-digit year, 1900-2099, anywhere in the string.
_YEAR_PATTERN = re.compile(r"\b(19\d{2}|20\d{2})\b")


@dataclass(frozen=True)
class ParsedReference:
    department: str
    number: str
    year: Optional[str]


def parse_document_reference(text: str) -> Optional[ParsedReference]:
    match = _REFERENCE_PATTERN.search(text)
    if not match:
        return None
    department = re.sub(r"\s+", "", match.group("dept")).upper()
    number = match.group("number").lstrip("0") or "0"
    year_match = _YEAR_PATTERN.search(text)
    year = year_match.group(1) if year_match else None
    return ParsedReference(department=department, number=number, year=year)


def resolve_document_reference(session, target_document_reference: str) -> Optional[Document]:
    """Find the one Document in our corpus this reference clearly means,
    or None if it isn't in our corpus (or the match would be ambiguous)."""
    parsed_query = parse_document_reference(target_document_reference)
    if parsed_query is None:
        return None

    candidates: list[tuple[Document, ParsedReference]] = []
    for document in session.query(Document).all():
        parsed_candidate = parse_document_reference(document.reference_number)
        if parsed_candidate is None:
            continue
        if (
            parsed_candidate.department == parsed_query.department
            and parsed_candidate.number == parsed_query.number
        ):
            candidates.append((document, parsed_candidate))

    if not candidates:
        return None

    if parsed_query.year is not None:
        year_matches = [d for d, p in candidates if p.year == parsed_query.year]
        return year_matches[0] if len(year_matches) == 1 else None

    # No year on the query side: only safe if every remaining candidate
    # is actually the same document (e.g. an Annex row sharing its
    # parent's reference_number), not genuinely different documents.
    unique_documents = {d.id for d, _ in candidates}
    return candidates[0][0] if len(unique_documents) == 1 else None
