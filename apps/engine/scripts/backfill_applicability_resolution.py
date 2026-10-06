"""Re-resolve ApplicabilityRule rows whose entity/product/activity text
didn't match our taxonomy at extraction time, but would now (e.g. after
a taxonomy addition or a new resolver alias). Pure re-application of
resolution logic against already-extracted data -- no new AI calls.

Only touches DRAFT rows (nothing reviewed is ever silently changed) and
only moves a dimension from unresolved-text to resolved-id, never the
reverse.

Usage:
  uv run python -m scripts.backfill_applicability_resolution
"""

from app.db.session import get_session
from app.extraction.applicability_resolver import (
    resolve_business_activity,
    resolve_entity_type,
    resolve_product_type,
)
from app.models import ApplicabilityRule


def main():
    session = get_session()
    try:
        rules = session.query(ApplicabilityRule).filter_by(status="DRAFT").all()
        updated = 0

        for rule in rules:
            changed = False

            if rule.entity_type_text and not rule.entity_type_id:
                resolved = resolve_entity_type(session, rule.entity_type_text)
                if resolved is not None:
                    rule.entity_type_id = resolved.id
                    rule.entity_type_text = None
                    changed = True

            if rule.product_type_text and not rule.product_type_id:
                resolved = resolve_product_type(session, rule.product_type_text)
                if resolved is not None:
                    rule.product_type_id = resolved.id
                    rule.product_type_text = None
                    changed = True

            if rule.business_activity_text and not rule.business_activity_id:
                resolved = resolve_business_activity(session, rule.business_activity_text)
                if resolved is not None:
                    rule.business_activity_id = resolved.id
                    rule.business_activity_text = None
                    changed = True

            if changed:
                updated += 1

        session.commit()
        print(f"re-resolved {updated}/{len(rules)} DRAFT applicability rule(s)")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
