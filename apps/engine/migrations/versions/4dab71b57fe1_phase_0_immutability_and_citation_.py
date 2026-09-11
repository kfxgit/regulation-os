"""phase 0: immutability and citation-required triggers

Two non-negotiable principles that a column definition alone can't enforce,
so they are real Postgres triggers, not just application-level discipline:

1. REQUIREMENTS ARE IMMUTABLE. A regulatory_requirement row's content
   (text, classification, confidence scores, source document link) can
   never change after insert. The only allowed change is the lifecycle
   pair (status, superseded_by_id) -- e.g. flipping DRAFT -> ACTIVE on
   review approval, or ACTIVE -> SUPERSEDED when a new revision replaces
   it. Amendments always insert a new row; they never edit an old one.

2. NO CITATION = UNPUBLISHABLE. A requirement cannot be marked ACTIVE
   unless it has at least one source_citation row proving where in the
   source document it comes from.

Revision ID: 4dab71b57fe1
Revises: 03250b77ed3b
Create Date: 2026-09-11 21:34:56.623698

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4dab71b57fe1'
down_revision: Union[str, Sequence[str], None] = '03250b77ed3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION regulatory_requirement_block_content_update()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.id IS DISTINCT FROM OLD.id
               OR NEW.stable_key IS DISTINCT FROM OLD.stable_key
               OR NEW.revision_number IS DISTINCT FROM OLD.revision_number
               OR NEW.document_version_id IS DISTINCT FROM OLD.document_version_id
               OR NEW.section_id IS DISTINCT FROM OLD.section_id
               OR NEW.clause_type IS DISTINCT FROM OLD.clause_type
               OR NEW.requirement_text IS DISTINCT FROM OLD.requirement_text
               OR NEW.effective_date IS DISTINCT FROM OLD.effective_date
               OR NEW.confidence_extraction IS DISTINCT FROM OLD.confidence_extraction
               OR NEW.confidence_source_match IS DISTINCT FROM OLD.confidence_source_match
               OR NEW.confidence_classification IS DISTINCT FROM OLD.confidence_classification
               OR NEW.confidence_applicability IS DISTINCT FROM OLD.confidence_applicability
               OR NEW.confidence_interpretation IS DISTINCT FROM OLD.confidence_interpretation
               OR NEW.extraction_run_id IS DISTINCT FROM OLD.extraction_run_id
               OR NEW.created_at IS DISTINCT FROM OLD.created_at
            THEN
                RAISE EXCEPTION
                    'regulatory_requirement rows are immutable: only status and superseded_by_id may change (id=%)',
                    OLD.id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_regulatory_requirement_immutable
        BEFORE UPDATE ON regulatory_requirement
        FOR EACH ROW EXECUTE FUNCTION regulatory_requirement_block_content_update();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION regulatory_requirement_require_citation()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.status = 'ACTIVE' THEN
                IF NOT EXISTS (
                    SELECT 1 FROM source_citation WHERE requirement_id = NEW.id
                ) THEN
                    RAISE EXCEPTION
                        'requirement % cannot become ACTIVE without at least one source citation',
                        NEW.id;
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_regulatory_requirement_require_citation
        BEFORE INSERT OR UPDATE ON regulatory_requirement
        FOR EACH ROW EXECUTE FUNCTION regulatory_requirement_require_citation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_regulatory_requirement_require_citation ON regulatory_requirement;")
    op.execute("DROP FUNCTION IF EXISTS regulatory_requirement_require_citation();")
    op.execute("DROP TRIGGER IF EXISTS trg_regulatory_requirement_immutable ON regulatory_requirement;")
    op.execute("DROP FUNCTION IF EXISTS regulatory_requirement_block_content_update();")
