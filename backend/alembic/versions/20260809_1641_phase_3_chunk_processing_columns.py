"""phase 3 chunk processing columns

Revision ID: f802a56c5738
Revises: 4978d06e353d
Create Date: 2026-08-09 16:41:03.471359+00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'f802a56c5738'
down_revision: str | None = '4978d06e353d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Batch mode keeps this portable: table rebuild on SQLite, ALTERs on
    # PostgreSQL (SQLite cannot ADD CONSTRAINT for the foreign key).
    with op.batch_alter_table('document_chunks') as batch:
        batch.add_column(sa.Column('document_id', sa.Uuid(), nullable=True))
        batch.add_column(sa.Column('page_number', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('section', sa.String(length=300), nullable=True))
        batch.create_foreign_key(
            op.f('fk_document_chunks_document_id_documents'),
            'documents', ['document_id'], ['id'], ondelete='CASCADE',
        )
    op.create_index(op.f('ix_document_chunks_document_id'), 'document_chunks', ['document_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_document_chunks_document_id'), table_name='document_chunks')
    with op.batch_alter_table('document_chunks') as batch:
        batch.drop_constraint(op.f('fk_document_chunks_document_id_documents'), type_='foreignkey')
        batch.drop_column('section')
        batch.drop_column('page_number')
        batch.drop_column('document_id')
