from app.extraction.verification import MIN_ACCEPTABLE_MATCH_SCORE, find_citation

PAGE_TEXT = (
    "3.2 Capital Adequacy Ratio\n\n"
    "Every bank shall maintain, at all times, a minimum Capital Adequacy "
    "Ratio (CAR) of 10% of its risk-weighted assets."
)


def test_exact_match_scores_1():
    quote = "a minimum Capital Adequacy Ratio (CAR) of 10%"
    match = find_citation(quote, PAGE_TEXT)
    assert match.match_score == 1.0
    assert PAGE_TEXT[match.char_start : match.char_end] == quote


def test_near_miss_still_found_with_lower_score():
    """Simulates OCR noise: a smart quote / spacing glitch instead of an
    exact match. Should still locate the span, with score < 1.0."""
    noisy_quote = "a minimum Capital Adeqacy Ratio (CAR) of 10%"  # 'Adeqacy' typo
    match = find_citation(noisy_quote, PAGE_TEXT)
    assert 0.0 < match.match_score < 1.0
    assert match.match_score > MIN_ACCEPTABLE_MATCH_SCORE  # one dropped letter is still a strong match


def test_unrelated_text_scores_low():
    """A quote that isn't actually from this page (e.g. a hallucinated
    or paraphrased 'quote') should score low, not be silently accepted."""
    unrelated_quote = "Directors must file quarterly compliance reports within sixty days"
    match = find_citation(unrelated_quote, PAGE_TEXT)
    assert match.match_score < MIN_ACCEPTABLE_MATCH_SCORE
