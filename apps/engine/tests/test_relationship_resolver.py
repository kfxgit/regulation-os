from datetime import date

from app.extraction.relationship_resolver import (
    ParsedReference,
    parse_document_reference,
    resolve_document_reference,
)
from tests.factories import make_document_version


def test_parse_document_reference_various_formats():
    cases = [
        ("BSD Circular No. 05 dated February 14, 2008", ParsedReference("BSD", "5", "2008")),
        ("IBD Circular No. 2 of April 29, 2004", ParsedReference("IBD", "2", "2004")),
        ("BPRD Circular No. 08", ParsedReference("BPRD", "8", None)),
        ("BPRD Circular No. 10", ParsedReference("BPRD", "10", None)),
        ("BC & CPD Circular No. 06 of 2021", ParsedReference("BC&CPD", "6", "2021")),
        ("DI&SD Circular No. 1", ParsedReference("DI&SD", "1", None)),
        ("BPRD Circular Letter No.1 of 2010", ParsedReference("BPRD", "1", "2010")),
    ]
    for text, expected in cases:
        assert parse_document_reference(text) == expected


def test_parse_document_reference_returns_none_for_unparseable_text():
    assert parse_document_reference("BSD File letter No. BSD/SU-61/101/7494/2004 of 2004") is None
    assert parse_document_reference("some unrelated sentence") is None


def test_resolve_exact_department_number_and_year_match(db_session):
    make_document_version(db_session, reference_number="BSD Circular No. 05 of 2008", issue_date=date(2008, 2, 14))
    db_session.commit()

    resolved = resolve_document_reference(db_session, "BSD Circular No. 05 dated February 14, 2008")
    assert resolved is not None
    assert resolved.reference_number == "BSD Circular No. 05 of 2008"


def test_resolve_does_not_cross_match_different_numbers(db_session):
    """The exact bug fuzzy matching would have caused: No. 08 must never
    match No. 10, even though the strings are 95% similar.

    Uses a ZZZTEST department code to avoid colliding with real
    documents already in the shared database (e.g. our own real corpus
    has multiple genuinely different "BPRD Circular No. 08" documents --
    reusing that exact name here would make this test's result depend on
    unrelated production data)."""
    make_document_version(db_session, reference_number="ZZZTEST Circular No. 08", issue_date=date(2016, 1, 1))
    make_document_version(db_session, reference_number="ZZZTEST Circular No. 10", issue_date=date(2017, 1, 1))
    db_session.commit()

    resolved = resolve_document_reference(db_session, "ZZZTEST Circular No. 08")
    assert resolved is not None
    assert resolved.reference_number == "ZZZTEST Circular No. 08"


def test_resolve_refuses_ambiguous_same_department_and_number_different_years(db_session):
    """Same department+number, genuinely different documents issued in
    different years (SBP circular numbers reset annually) -- with a year
    stated on the query side that doesn't match either, must not guess."""
    make_document_version(db_session, reference_number="ZZZTEST Circular No. 1 of 2010", issue_date=date(2010, 1, 1))
    make_document_version(db_session, reference_number="ZZZTEST Circular No. 1 of 2019", issue_date=date(2019, 1, 1))
    db_session.commit()

    resolved = resolve_document_reference(db_session, "ZZZTEST Circular No. 1 of 2015")
    assert resolved is None  # neither year matches -- don't guess


def test_resolve_matches_by_year_when_ambiguous_without_it(db_session):
    make_document_version(db_session, reference_number="ZZZTEST Circular No. 1 of 2010", issue_date=date(2010, 1, 1))
    make_document_version(db_session, reference_number="ZZZTEST Circular No. 1 of 2019", issue_date=date(2019, 1, 1))
    db_session.commit()

    resolved = resolve_document_reference(db_session, "ZZZTEST Circular Letter No.1 of 2019")
    assert resolved is not None
    assert resolved.reference_number == "ZZZTEST Circular No. 1 of 2019"


def test_resolve_refuses_to_guess_without_year_when_multiple_candidates_exist(db_session):
    make_document_version(db_session, reference_number="ZZZTEST Circular No. 1 of 2010", issue_date=date(2010, 1, 1))
    make_document_version(db_session, reference_number="ZZZTEST Circular No. 1 of 2019", issue_date=date(2019, 1, 1))
    db_session.commit()

    # no year in the query at all -- two real, different candidates match
    resolved = resolve_document_reference(db_session, "ZZZTEST Circular No. 1")
    assert resolved is None


def test_resolve_returns_none_for_reference_not_in_corpus(db_session):
    make_document_version(db_session, reference_number="ZZZTEST Circular No. 08", issue_date=date(2016, 1, 1))
    db_session.commit()

    resolved = resolve_document_reference(db_session, "BSD Circular No. 05 dated February 14, 2008")
    assert resolved is None
