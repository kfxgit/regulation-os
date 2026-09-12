"""Batch-ingest every PDF in data/incoming/: auto-extract document
metadata from each file's own first page, then run the full pipeline.

Skips (does not guess) any file where metadata extraction can't find a
reference number or issue date -- those need manual --title/--reference/
--issue-date via scripts/ingest.py instead (see "no silent defaults").

Idempotent: skips files whose content hash already has a DocumentVersion
in the database, so it's safe to re-run after adding more files.

Usage:
  uv run python -m scripts.batch_ingest --regulator SBP

Writes a JSON review export (data/batch_review_<timestamp>.json) with
every requirement/obligation/citation created, for a review page.
"""

import argparse
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

from app.db.session import get_session
from app.extraction.metadata import extract_document_metadata
from app.extraction.pdf_pages import render_pdf_pages
from app.extraction.pipeline import ingest_pdf
from app.extraction.verification import MIN_ACCEPTABLE_MATCH_SCORE
from app.models import Document, DocumentVersion, Obligation, Regulator, SourceCitation
from app.models.enums import OcrStatus

INCOMING_DIR = Path(__file__).parent.parent / "data" / "incoming"


def sha256_of_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_default(value):
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"not JSON serializable: {type(value)}")


def build_review_entry(session, requirement) -> dict:
    citation = session.query(SourceCitation).filter_by(requirement_id=requirement.id).first()
    obligations = session.query(Obligation).filter_by(requirement_id=requirement.id).all()
    return {
        "id": str(requirement.id),
        "clause_type": str(requirement.clause_type.value if hasattr(requirement.clause_type, "value") else requirement.clause_type),
        "requirement_text": requirement.requirement_text,
        "contains_high_risk_language": requirement.contains_high_risk_language,
        "high_risk_notes": requirement.high_risk_notes,
        "confidence_extraction": requirement.confidence_extraction,
        "confidence_source_match": requirement.confidence_source_match,
        "confidence_classification": requirement.confidence_classification,
        "confidence_interpretation": requirement.confidence_interpretation,
        "citation": {
            "quoted_text": citation.quoted_text,
            "match_score": citation.match_score,
        }
        if citation
        else None,
        "obligations": [
            {
                "actor": o.actor,
                "action": o.action,
                "object": o.object,
                "frequency": str(o.frequency.value if hasattr(o.frequency, "value") else o.frequency) if o.frequency else None,
                "deadline_description": o.deadline_description,
            }
            for o in obligations
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--regulator", required=True, help="Regulator short_code, e.g. SBP")
    args = parser.parse_args()

    pdf_files = sorted(INCOMING_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDF files found in {INCOMING_DIR}")
        return

    session = get_session()
    review_export = {"generated_at": datetime.now(timezone.utc).isoformat(), "documents": []}

    try:
        regulator = session.query(Regulator).filter_by(short_code=args.regulator).first()
        if regulator is None:
            raise SystemExit(f"No regulator with short_code={args.regulator!r}. Seed it first.")

        for pdf_path in pdf_files:
            file_hash = sha256_of_file(pdf_path)
            existing = session.query(DocumentVersion).filter_by(file_hash=file_hash).first()
            if existing is not None:
                print(f"SKIP (already ingested): {pdf_path.name}")
                continue

            images = render_pdf_pages(str(pdf_path))
            meta = extract_document_metadata(images[0])

            if meta.reference_number is None or meta.issue_date is None:
                print(
                    f"NEEDS MANUAL METADATA: {pdf_path.name} "
                    f"(title guessed: {meta.title!r}, reference_number={meta.reference_number!r}, "
                    f"issue_date={meta.issue_date!r}) -- use scripts/ingest.py with explicit "
                    f"--reference/--issue-date instead."
                )
                continue

            document = Document(
                regulator_id=regulator.id,
                title=meta.title,
                document_type=meta.document_type,
                reference_number=meta.reference_number,
                issue_date=meta.issue_date,
            )
            session.add(document)
            session.flush()

            document_version = DocumentVersion(
                document_id=document.id,
                version_number=1,
                file_hash=file_hash,
                file_uri=str(pdf_path.resolve()),
                ocr_status=OcrStatus.PROCESSING,
            )
            session.add(document_version)
            session.flush()

            created = ingest_pdf(session, document_version, str(pdf_path))
            document_version.ocr_status = OcrStatus.DONE
            session.commit()

            low_confidence = [
                r for r in created if (r.confidence_source_match or 0) < MIN_ACCEPTABLE_MATCH_SCORE
            ]
            print(
                f"OK: {pdf_path.name} -> {meta.reference_number} ({len(created)} requirements"
                + (f", {len(low_confidence)} low-confidence" if low_confidence else "")
                + ")"
            )

            review_export["documents"].append(
                {
                    "file_name": pdf_path.name,
                    "title": meta.title,
                    "reference_number": meta.reference_number,
                    "issue_date": meta.issue_date.isoformat(),
                    "document_type": str(meta.document_type.value if hasattr(meta.document_type, "value") else meta.document_type),
                    "document_id": str(document.id),
                    "document_version_id": str(document_version.id),
                    "requirements": [build_review_entry(session, r) for r in created],
                }
            )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    if review_export["documents"]:
        out_dir = Path(__file__).parent.parent / "data"
        out_path = out_dir / f"batch_review_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        out_path.write_text(json.dumps(review_export, indent=2, default=_json_default), encoding="utf-8")
        print(f"\nReview export written to {out_path}")


if __name__ == "__main__":
    main()
