"""CLI to ingest one regulatory PDF into the knowledge base.

Creates the Document + DocumentVersion rows, then runs the full
pipeline: PDF -> page images -> OCR -> extraction -> source
verification -> persistence. Everything lands as DRAFT -- nothing here
approves anything (see CLAUDE.md section 4, "no silent publishing").

Usage:
  uv run python -m scripts.ingest \
      --regulator SBP \
      --title "Prudential Regulations for Corporate/Commercial Banking" \
      --reference "BPRD Circular No. 5 of 2023" \
      --issue-date 2023-04-12 \
      --pdf path/to/file.pdf

The --regulator value must already exist (see scripts/seed.py).
"""

import argparse
import hashlib
from datetime import date
from pathlib import Path

from app.db.session import get_session
from app.extraction.pipeline import ingest_pdf
from app.models import Document, DocumentVersion, Regulator
from app.models.enums import DocumentType, OcrStatus
from app.extraction.verification import MIN_ACCEPTABLE_MATCH_SCORE


def sha256_of_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--regulator", required=True, help="Regulator short_code, e.g. SBP")
    parser.add_argument("--title", required=True)
    parser.add_argument(
        "--reference", required=True, help="Official reference number, e.g. 'BPRD Circular No. 5 of 2023'"
    )
    parser.add_argument("--issue-date", required=True, help="YYYY-MM-DD")
    parser.add_argument(
        "--document-type", default="CIRCULAR", choices=[t.value for t in DocumentType]
    )
    parser.add_argument("--pdf", required=True, type=Path)
    args = parser.parse_args()

    if not args.pdf.exists():
        raise SystemExit(f"PDF not found: {args.pdf}")

    session = get_session()
    try:
        regulator = session.query(Regulator).filter_by(short_code=args.regulator).first()
        if regulator is None:
            raise SystemExit(
                f"No regulator with short_code={args.regulator!r}. Seed it first (scripts/seed.py)."
            )

        document = Document(
            regulator_id=regulator.id,
            title=args.title,
            document_type=DocumentType(args.document_type),
            reference_number=args.reference,
            issue_date=date.fromisoformat(args.issue_date),
        )
        session.add(document)
        session.flush()

        document_version = DocumentVersion(
            document_id=document.id,
            version_number=1,
            file_hash=sha256_of_file(args.pdf),
            file_uri=str(args.pdf.resolve()),
            ocr_status=OcrStatus.PROCESSING,
        )
        session.add(document_version)
        session.flush()

        created = ingest_pdf(session, document_version, str(args.pdf))

        document_version.ocr_status = OcrStatus.DONE
        session.commit()

        print(f"Ingested {args.pdf.name}")
        print(f"  document_id: {document.id}")
        print(f"  document_version_id: {document_version.id}")
        print(f"  requirements created (all DRAFT, none active): {len(created)}")

        low_confidence = [
            r for r in created if (r.confidence_source_match or 0) < MIN_ACCEPTABLE_MATCH_SCORE
        ]
        if low_confidence:
            print(
                f"  WARNING: {len(low_confidence)} requirement(s) have source-match confidence "
                f"below {MIN_ACCEPTABLE_MATCH_SCORE} -- review these first."
            )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
