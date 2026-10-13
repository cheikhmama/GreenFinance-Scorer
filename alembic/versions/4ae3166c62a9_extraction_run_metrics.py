"""extraction runs: pages, OCR pages, durations and memory peak

Long reports (200+ pages) are converted in page batches on a memory-bounded VM: each successful run
now records how many pages were converted, how many went through OCR, how long the Docling
conversion and the LLM calls took, and the memory peak in MB. All nullable: runs recorded before
this revision have none of these measures, and a failed run keeps them empty.

Downgrade: the five columns are dropped.

Revision ID: 4ae3166c62a9
Revises: c3e8a1f6d2b9
Create Date: 2026-10-13 21:29:38.803090

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '4ae3166c62a9'
down_revision: str | Sequence[str] | None = 'c3e8a1f6d2b9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('extraction_runs', sa.Column('pages', sa.Integer(), nullable=True))
    op.add_column('extraction_runs', sa.Column('pages_ocr', sa.Integer(), nullable=True))
    op.add_column('extraction_runs', sa.Column('duree_conversion_s', sa.Float(), nullable=True))
    op.add_column('extraction_runs', sa.Column('duree_llm_s', sa.Float(), nullable=True))
    op.add_column('extraction_runs', sa.Column('pic_memoire_mo', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('extraction_runs', 'pic_memoire_mo')
    op.drop_column('extraction_runs', 'duree_llm_s')
    op.drop_column('extraction_runs', 'duree_conversion_s')
    op.drop_column('extraction_runs', 'pages_ocr')
    op.drop_column('extraction_runs', 'pages')
