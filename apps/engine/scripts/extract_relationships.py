"""Extract document relationships (AMENDS/REPLACES/SUPERSEDES/etc.) from
already-reviewed ACTIVE AMENDMENT_TEXT requirements, and link them to
real Document rows in our corpus where possible.

Nothing here re-ingests documents or touches RegulatoryRequirement -- it
only reads already-approved clauses (and their citations, for the exact
source wording) and writes new RegulatoryRelationship rows. Everything
lands as DRAFT, same as the rest of the pipeline: AI-derived, needs
human review before anything treats it as confirmed.

Idempotent: skips any requirement that already has relationship rows
extracted from it, so it's safe to re-run after ingesting more clauses.

Usage:
  uv run python -m scripts.extract_relationships
"""

import argparse
from collections import defaultdict
from datetime import datetime, timezone

from app.core.ai_client import DEFAULT_MODEL
from app.db.session import get_session
from app.extraction.relationship_resolver import resolve_document_reference
from app.extraction.relationships import extract_relationships
from app.models import (
    DocumentVersion,
    ExtractionRun,
    RegulatoryRelationship,
    RegulatoryRequirement,
)
from app.models.enums import ExtractionRunStatus


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    session = get_session()
    try:
        already_processed_ids = {
            row[0]
            for row in session.query(RegulatoryRelationship.source_requirement_id)
            .filter(RegulatoryRelationship.source_requirement_id.isnot(None))
            .all()
        }

        requirements = (
            session.query(RegulatoryRequirement)
            .filter(RegulatoryRequirement.clause_type == "AMENDMENT_TEXT")
            .filter(RegulatoryRequirement.status == "ACTIVE")
            .filter(RegulatoryRequirement.id.notin_(already_processed_ids))
            .all()
        )
        print(f"scanning {len(requirements)} ACTIVE AMENDMENT_TEXT clauses (skipping {len(already_processed_ids)} already processed)")

        by_document_version = defaultdict(list)
        for requirement in requirements:
            by_document_version[requirement.document_version_id].append(requirement)

        total_extracted = 0
        total_resolved = 0
        total_external = 0

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
                # requirement_text, not the raw citation quote: the
                # original extraction already resolved pronouns/context
                # ("the above referred circular" -> the actual circular
                # named earlier on the page) -- re-deriving from the
                # narrower citation text throws that context away and
                # produces vaguer, unresolved references.
                result = extract_relationships(requirement.requirement_text, model=args.model)

                for extracted in result.relationships:
                    total_extracted += 1
                    target_document = resolve_document_reference(
                        session, extracted.target_document_reference
                    )
                    if target_document is not None:
                        total_resolved += 1
                        print(
                            f"  RESOLVED: {extracted.relationship_type.value} -> "
                            f"{target_document.reference_number!r} (from {extracted.target_document_reference!r})"
                        )
                    else:
                        total_external += 1
                        print(
                            f"  EXTERNAL: {extracted.relationship_type.value} -> "
                            f"{extracted.target_document_reference!r} (not in our corpus)"
                        )

                    session.add(
                        RegulatoryRelationship(
                            from_document_id=document_version.document_id,
                            to_document_id=target_document.id if target_document else None,
                            external_reference_text=(
                                None if target_document else extracted.target_document_reference
                            ),
                            relationship_type=extracted.relationship_type,
                            confidence_extraction=extracted.confidence_extraction,
                            source_requirement_id=requirement.id,
                            extraction_run_id=extraction_run.id,
                        )
                    )

            extraction_run.status = ExtractionRunStatus.SUCCEEDED
            extraction_run.completed_at = datetime.now(timezone.utc)

        session.commit()
        print(
            f"\nextracted {total_extracted} relationship(s): "
            f"{total_resolved} resolved to a document in our corpus, "
            f"{total_external} external (not yet ingested). All DRAFT, pending review."
        )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
