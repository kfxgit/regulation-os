"""Source verification: locate an extracted source_quote inside the
page's raw OCR text, and score how well it actually matches.

This is confidence_source_match -- computed here, by deterministic code,
never self-reported by Claude (see app/extraction/schema.py docstring).
The AI does not get to grade its own citation accuracy.

Claude is instructed to quote verbatim (app/extraction/extract.py), so
most citations should match exactly. Fuzzy alignment is the fallback for
near-misses: OCR noise, stray whitespace, a smart-quote vs straight-quote
mismatch -- not for AI paraphrasing, which should score low and get
flagged for human review rather than silently accepted.
"""

from dataclasses import dataclass

from rapidfuzz import fuzz

# Below this score, a citation should be flagged for human review rather
# than trusted -- see CLAUDE.md section 4, "no citation = unpublishable".
MIN_ACCEPTABLE_MATCH_SCORE = 0.85


@dataclass
class CitationMatch:
    char_start: int
    char_end: int
    match_score: float  # 0.0-1.0


def find_citation(source_quote: str, page_raw_text: str) -> CitationMatch:
    """Find where source_quote occurs in page_raw_text.

    Tries an exact substring match first (match_score = 1.0). Falls back
    to fuzzy alignment, which finds the best-matching span even when it
    isn't a perfect substring, and scores it 0.0-1.0.
    """
    exact_index = page_raw_text.find(source_quote)
    if exact_index != -1:
        return CitationMatch(
            char_start=exact_index,
            char_end=exact_index + len(source_quote),
            match_score=1.0,
        )

    alignment = fuzz.partial_ratio_alignment(source_quote, page_raw_text)
    return CitationMatch(
        char_start=alignment.dest_start,
        char_end=alignment.dest_end,
        match_score=alignment.score / 100.0,
    )
