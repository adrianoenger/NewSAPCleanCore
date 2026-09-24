"""sap_object_parsing

Revision ID: 0004_sap_object_parsing
Revises: 0003_source_ingestion
Create Date: 2026-09-24
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0004_sap_object_parsing'
down_revision: str | None = '0003_source_ingestion'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'sap_object',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('assessment_id', sa.Integer(), nullable=False),
        sa.Column('source_file_id', sa.Integer(), nullable=False),
        sa.Column('object_type', sa.String(length=50), nullable=False),
        sa.Column('object_name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('line_start', sa.Integer(), nullable=False),
        sa.Column('line_end', sa.Integer(), nullable=True),
        sa.Column('attributes', sa.JSON(), nullable=False),
        sa.Column('parsed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['assessment_id'], ['assessment.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_file_id'], ['source_file.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_sap_object_assessment_id'), 'sap_object', ['assessment_id'], unique=False)
    op.create_index(op.f('ix_sap_object_object_name'), 'sap_object', ['object_name'], unique=False)
    op.create_index(op.f('ix_sap_object_object_type'), 'sap_object', ['object_type'], unique=False)
    op.create_index(op.f('ix_sap_object_source_file_id'), 'sap_object', ['source_file_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_sap_object_source_file_id'), table_name='sap_object')
    op.drop_index(op.f('ix_sap_object_object_type'), table_name='sap_object')
    op.drop_index(op.f('ix_sap_object_object_name'), table_name='sap_object')
    op.drop_index(op.f('ix_sap_object_assessment_id'), table_name='sap_object')
    op.drop_table('sap_object')
