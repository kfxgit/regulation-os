"""Tests for the extraction contract itself (app/extraction/schema.py) --
no database involved. Proves the contract actually rejects incomplete or
unexpected AI output instead of silently accepting it."""

import pytest
from pydantic import ValidationError

from app.extraction.schema import ExtractedRequirement, PageExtractionResult


def valid_requirement_kwargs(**overrides):
    defaults = dict(
        clause_type="RULE",
        requirement_text="Banks must maintain a minimum capital adequacy ratio of 10%.",
        source_quote="maintain a minimum capital adequacy ratio of ten percent (10%)",
        contains_high_risk_language=True,
        high_risk_notes="States a 10% capital ratio threshold.",
        confidence_extraction=0.95,
        confidence_classification=0.9,
        confidence_interpretation=0.85,
    )
    defaults.update(overrides)
    return defaults


def test_valid_requirement_parses():
    requirement = ExtractedRequirement(**valid_requirement_kwargs())
    assert requirement.clause_type == "RULE"
    assert requirement.obligations == []  # default empty, not missing


def test_missing_confidence_score_is_rejected():
    kwargs = valid_requirement_kwargs()
    del kwargs["confidence_extraction"]
    with pytest.raises(ValidationError):
        ExtractedRequirement(**kwargs)


def test_missing_high_risk_flag_is_rejected():
    """contains_high_risk_language has no default -- Claude must always
    make this call explicitly, never silently skip it."""
    kwargs = valid_requirement_kwargs()
    del kwargs["contains_high_risk_language"]
    with pytest.raises(ValidationError):
        ExtractedRequirement(**kwargs)


def test_unknown_field_is_rejected():
    """extra='forbid' -- if Claude's output includes a field we didn't
    ask for, that's a signal something is wrong, not something to ignore."""
    with pytest.raises(ValidationError):
        ExtractedRequirement(**valid_requirement_kwargs(made_up_field="oops"))


def test_confidence_out_of_range_is_rejected():
    with pytest.raises(ValidationError):
        ExtractedRequirement(**valid_requirement_kwargs(confidence_extraction=1.5))


def test_empty_source_quote_is_rejected():
    """No citation = unpublishable, starting at the contract level."""
    with pytest.raises(ValidationError):
        ExtractedRequirement(**valid_requirement_kwargs(source_quote=""))


def test_page_result_defaults_to_empty_list():
    result = PageExtractionResult()
    assert result.requirements == []
