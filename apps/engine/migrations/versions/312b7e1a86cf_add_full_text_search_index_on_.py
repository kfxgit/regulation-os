"""add full-text search index on requirement_text

A functional GIN index on to_tsvector('english', requirement_text) --
not a stored column -- since requirement_text never changes after insert
(the immutability trigger forbids it) there's no upkeep cost to computing
the tsvector at index-build/query time instead of maintaining a separate
generated column. Autogenerate doesn't detect functional indexes, so this
migration is hand-written.

Revision ID: 312b7e1a86cf
Revises: 2d192ed187eb
Create Date: 2026-10-06 14:03:37.705312

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '312b7e1a86cf'
down_revision: Union[str, Sequence[str], None] = '2d192ed187eb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        CREATE INDEX ix_regulatory_requirement_text_fts
        ON regulatory_requirement
        USING GIN (to_tsvector('english', requirement_text));
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS ix_regulatory_requirement_text_fts;")
