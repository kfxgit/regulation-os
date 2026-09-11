from app.extraction.extract import extract_requirements
from app.models.enums import ClauseType
from tests.conftest import live_api

SAMPLE_PAGE_TEXT = """3.2 Capital Adequacy Ratio

Every bank shall maintain, at all times, a minimum Capital Adequacy Ratio (CAR) of 10% of its risk-weighted assets, calculated on a consolidated basis as prescribed under Basel III guidelines. Banks that fail to meet this requirement must submit a capital restoration plan to the State Bank of Pakistan within thirty (30) days of the shortfall being identified.

3.3 Definitions

"Risk-Weighted Assets" means the assets of a bank adjusted for credit, market, and operational risk in accordance with the applicable SBP guidelines."""


@live_api
def test_extract_requirements_from_realistic_clause():
    result = extract_requirements(SAMPLE_PAGE_TEXT)

    assert len(result.requirements) >= 2  # the CAR rule + the definition, at minimum

    car_requirement = next(
        (r for r in result.requirements if "10%" in r.requirement_text), None
    )
    assert car_requirement is not None
    assert car_requirement.clause_type == ClauseType.RULE
    assert car_requirement.contains_high_risk_language is True

    # source_quote must be an exact substring -- this is what source
    # verification (fuzzy match against DocumentPage.raw_text) depends on.
    assert car_requirement.source_quote in SAMPLE_PAGE_TEXT

    assert len(car_requirement.obligations) >= 1
    obligation = car_requirement.obligations[0]
    assert obligation.actor
    assert obligation.action

    definition = next(
        (r for r in result.requirements if r.clause_type == ClauseType.DEFINITION), None
    )
    assert definition is not None
    assert definition.contains_high_risk_language is False
