"""Extract applicability scoping (who/what a clause applies to) from
already-reviewed ACTIVE requirements, and link entity/product/activity
mentions to our taxonomy where possible.

Scoped to clause types that actually impose or scope a requirement --
RULE, PROCEDURE, EXCEPTION, AMENDMENT_TEXT. DEFINITION and TABLE_DATA
clauses describe what something is, not who must do something, so
they're skipped.

Idempotent: skips any requirement that already has applicability rules
extracted from it.

Usage:
  uv run python -m scripts.extract_applicability [--limit N]
"""

import argparse
from collections import defaultdict
from datetime import datetime, timezone

from app.core.ai_client import DEFAULT_MODEL
from app.db.session import get_session
from app.extraction.applicability import extract_applicability
from app.extraction.applicability_resolver import (
    resolve_business_activity,
    resolve_entity_type,
    resolve_product_type,
)
from app.models import ApplicabilityRule, DocumentVersion, ExtractionRun, RegulatoryRequirement
from app.models.enums import ExtractionRunStatus

SCOPED_CLAUSE_TYPES = ["RULE", "PROCEDURE", "EXCEPTION", "AMENDMENT_TEXT"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--limit", type=int, default=None, help="Process at most N requirements (for a validation sample before a full run)")
    args = parser.parse_args()

    session = get_session()
    try:
        already_processed_ids = {
            row[0] for row in session.query(ApplicabilityRule.requirement_id).all()
        }

        query = (
            session.query(RegulatoryRequirement)
            .filter(RegulatoryRequirement.clause_type.in_(SCOPED_CLAUSE_TYPES))
            .filter(RegulatoryRequirement.status == "ACTIVE")
            .filter(RegulatoryRequirement.id.notin_(already_processed_ids))
        )
        requirements = query.limit(args.limit).all() if args.limit else query.all()
        print(f"scanning {len(requirements)} ACTIVE requirements (skipping {len(already_processed_ids)} already processed)")

        by_document_version = defaultdict(list)
        for requirement in requirements:
            by_document_version[requirement.document_version_id].append(requirement)

        total_extracted = 0
        total_resolved_dims = 0
        total_unresolved_dims = 0

        for document_version_id, reqs in by_document_version.items():
            document_version = session.get(DocumentVersion, document_version_id)
            extraction_run = ExtractionRun(
                document_version_id=document_version_id,
                model_name=args.model,
                model_version=args.model,
                prompt_version="v1",
                status=ExtractionRunStatus.RUNNING,
                started_at=datetime.now(timezone.utc),
            )
            session.add(extraction_run)
            session.flush()

            for requirement in reqs:
                result = extract_applicability(requirement.requirement_text, model=args.model)

                for extracted in result.rules:
                    total_extracted += 1

                    entity = resolve_entity_type(session, extracted.entity_type) if extracted.entity_type else None
                    product = resolve_product_type(session, extracted.product_type) if extracted.product_type else None
                    activity = (
                        resolve_business_activity(session, extracted.business_activity)
                        if extracted.business_activity
                        else None
                    )

                    for label, raw, resolved in [
                        ("entity", extracted.entity_type, entity),
                        ("product", extracted.product_type, product),
                        ("activity", extracted.business_activity, activity),
                    ]:
                        if raw is None:
                            continue
                        if resolved is not None:
                            total_resolved_dims += 1
                        else:
                            total_unresolved_dims += 1

                    print(
                        f"  [{requirement.clause_type}] {extracted.scope_type.value}: "
                        f"entity={extracted.entity_type!r}({'resolved' if entity else 'unresolved' if extracted.entity_type else '-'}) "
                        f"product={extracted.product_type!r}({'resolved' if product else 'unresolved' if extracted.product_type else '-'}) "
                        f"activity={extracted.business_activity!r}({'resolved' if activity else 'unresolved' if extracted.business_activity else '-'}) "
                        f"condition={extracted.condition_text!r}"
                    )

                    session.add(
                        ApplicabilityRule(
                            requirement_id=requirement.id,
                            scope_type=extracted.scope_type,
                            entity_type_id=entity.id if entity else None,
                            entity_type_text=None if entity else extracted.entity_type,
                            product_type_id=product.id if product else None,
                            product_type_text=None if product else extracted.product_type,
                            business_activity_id=activity.id if activity else None,
                            business_activity_text=None if activity else extracted.business_activity,
                            condition_text=extracted.condition_text,
                            confidence_extraction=extracted.confidence_extraction,
                            extraction_run_id=extraction_run.id,
                        )
                    )

            extraction_run.status = ExtractionRunStatus.SUCCEEDED
            extraction_run.completed_at = datetime.now(timezone.utc)

        session.commit()
        print(
            f"\nextracted {total_extracted} applicability rule(s) across {len(requirements)} requirement(s): "
            f"{total_resolved_dims} dimension(s) resolved to our taxonomy, "
            f"{total_unresolved_dims} unresolved (kept as text). All DRAFT, pending review."
        )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
