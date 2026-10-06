from app.extraction.applicability_resolver import (
    resolve_business_activity,
    resolve_entity_type,
    resolve_product_type,
)


def test_resolve_entity_type_matches_by_code_abbreviation(db_session):
    """DFI is seeded as code='DFI', name='Development Finance
    Institution' -- real clauses say 'DFIs', not the expanded name, so
    the code match is what actually matters here."""
    resolved = resolve_entity_type(db_session, "DFIs")
    assert resolved is not None
    assert resolved.code == "DFI"


def test_resolve_entity_type_matches_plain_name(db_session):
    resolved = resolve_entity_type(db_session, "Banks")
    assert resolved is not None
    assert resolved.code == "BANK"


def test_resolve_entity_type_matches_multi_word_name(db_session):
    resolved = resolve_entity_type(db_session, "Microfinance Banks")
    assert resolved is not None
    assert resolved.code == "MICROFINANCE_BANK"


def test_resolve_entity_type_refuses_to_guess_on_partial_phrase(db_session):
    """'Takaful Operator' is a different concept from 'Islamic Bank' (a
    separate, non-bank insurer category) -- must not silently match just
    because 'Islamic'/banking-adjacent words overlap with something seeded."""
    resolved = resolve_entity_type(db_session, "Takaful Operator")
    assert resolved is None


def test_resolve_entity_type_matches_islamic_banking_subsidiary(db_session):
    """Added to the taxonomy after real evidence (4 mentions across FCY
    subordinated debt clauses) -- a real seeded entity, not a guess."""
    resolved = resolve_entity_type(db_session, "Islamic banking subsidiary")
    assert resolved is not None
    assert resolved.code == "ISLAMIC_BANKING_SUBSIDIARY"


def test_resolve_entity_type_matches_via_known_alias(db_session):
    """MFB isn't seeded as its own code (only MICROFINANCE_BANK, the
    full name) -- resolves via the explicit alias map instead of
    guessing from string similarity."""
    resolved = resolve_entity_type(db_session, "MFBs")
    assert resolved is not None
    assert resolved.code == "MICROFINANCE_BANK"


def test_resolve_entity_type_matches_member_fi_alias(db_session):
    resolved = resolve_entity_type(db_session, "Member FIs")
    assert resolved is not None
    assert resolved.code == "FI"


def test_resolve_product_type_matches_plain_name(db_session):
    resolved = resolve_product_type(db_session, "Digital Wallet")
    assert resolved is not None
    assert resolved.code == "DIGITAL_WALLET"


def test_resolve_business_activity_matches_plain_name(db_session):
    resolved = resolve_business_activity(db_session, "Deposit Taking")
    assert resolved is not None
    assert resolved.code == "DEPOSIT_TAKING"
