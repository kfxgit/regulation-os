"""Seed reference/taxonomy data for the SBP pack.

This only seeds lookup tables (Regulator, EntityType, ProductType,
BusinessActivity) -- not regulation content. Requirements, obligations,
and citations come from real documents in Phase 1 (the extraction engine),
not from a seed script.

Idempotent: safe to run more than once, matches existing rows by code.

Run with: uv run python -m scripts.seed
"""

from app.db.session import get_session
from app.models import BusinessActivity, EntityType, ProductType, Regulator

REGULATORS = [
    {
        "name": "State Bank of Pakistan",
        "short_code": "SBP",
        "country": "Pakistan",
        "website": "https://www.sbp.org.pk",
    },
]

ENTITY_TYPES = [
    {"code": "BANK", "name": "Bank"},
    {"code": "DFI", "name": "Development Finance Institution"},
    {"code": "MICROFINANCE_BANK", "name": "Microfinance Bank"},
    {"code": "ISLAMIC_BANK", "name": "Islamic Bank"},
    {"code": "EMI", "name": "Electronic Money Institution"},
    {"code": "PSO", "name": "Payment System Operator"},
    {"code": "PSP", "name": "Payment Service Provider"},
    {"code": "EXCHANGE_COMPANY", "name": "Exchange Company"},
    {"code": "NBFC", "name": "Non-Bank Finance Company"},
    {"code": "MODARABA", "name": "Modaraba"},
    {"code": "FI", "name": "Financial Institution"},
    {"code": "BRANCH", "name": "Branch"},  # 11 mentions ("branches"/"bank branches"/etc.)
    {"code": "RAAST_PARTICIPANT", "name": "Raast Participant"},  # 10 mentions ("Participants"/etc.)
    {"code": "DIGITAL_BANK", "name": "Digital Bank"},  # 2 mentions
    {"code": "EXTERNAL_AUDITOR", "name": "External Auditor"},  # 2 mentions
    {"code": "ISLAMIC_BANKING_SUBSIDIARY", "name": "Islamic Banking Subsidiary"},  # 4 mentions
    {"code": "CURRENCY_CHEST", "name": "Currency Chest"},  # 1 mention, SBP cash mgmt term
    {"code": "SUB_CHEST", "name": "Sub-Chest"},  # 1 mention, SBP cash mgmt term
]

PRODUCT_TYPES = [
    {"code": "DIGITAL_WALLET", "name": "Digital Wallet"},
    {"code": "CURRENT_ACCOUNT", "name": "Current Account"},
    {"code": "SAVINGS_ACCOUNT", "name": "Savings Account"},
    {"code": "BNPL", "name": "Buy Now Pay Later"},
    {"code": "DIGITAL_LENDING", "name": "Digital Lending"},
    {"code": "REMITTANCE", "name": "Remittance"},
    {"code": "RAAST", "name": "Raast"},  # 4 mentions plus "Raast services"/etc. variants
    {"code": "MTS", "name": "MTS"},  # named as extracted -- source text never expands the acronym
    {"code": "TTS", "name": "TTS"},
    {"code": "DDS", "name": "DDS"},
    {"code": "CLAIM_NOTES", "name": "Claim Notes"},
    {"code": "DEFECTIVE_NOTES", "name": "Clearly Payable Defective Notes"},
]

BUSINESS_ACTIVITIES = [
    {"code": "DEPOSIT_TAKING", "name": "Deposit Taking"},
    {"code": "CROSS_BORDER_REMITTANCE", "name": "Cross-Border Remittance"},
    {"code": "DIGITAL_LENDING_OPS", "name": "Digital Lending Operations"},
    {"code": "PAYMENT_PROCESSING", "name": "Payment Processing"},
    {"code": "FX_DEALING", "name": "Foreign Exchange Dealing"},
]


def seed_by_code(session, model, rows, code_field="code"):
    created = 0
    for row in rows:
        code = row[code_field]
        exists = session.query(model).filter_by(**{code_field: code}).first()
        if exists:
            continue
        session.add(model(**row))
        created += 1
    return created


def seed_regulators(session):
    created = 0
    for row in REGULATORS:
        exists = session.query(Regulator).filter_by(short_code=row["short_code"]).first()
        if exists:
            continue
        session.add(Regulator(**row))
        created += 1
    return created


def main():
    session = get_session()
    try:
        r = seed_regulators(session)
        e = seed_by_code(session, EntityType, ENTITY_TYPES)
        p = seed_by_code(session, ProductType, PRODUCT_TYPES)
        b = seed_by_code(session, BusinessActivity, BUSINESS_ACTIVITIES)
        session.commit()
        print(f"seeded: {r} regulator(s), {e} entity type(s), {p} product type(s), {b} business activit(y/ies)")
    finally:
        session.close()


if __name__ == "__main__":
    main()
