"""source_ingestion

Revision ID: 0003_source_ingestion
Revises: 0002_client_system_assessment
Create Date: 2026-09-24
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0003_source_ingestion'
down_revision: str | None = '0002_client_system_assessment'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('source_scan',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('assessment_id', sa.Integer(), nullable=False),
    sa.Column('source_path', sa.String(length=2000), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('total_files', sa.Integer(), nullable=False),
    sa.Column('scanned_files', sa.Integer(), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['assessment_id'], ['assessment.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_source_scan_assessment_id'), 'source_scan', ['assessment_id'], unique=False)
    op.create_table('source_file',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('scan_id', sa.Integer(), nullable=False),
    sa.Column('assessment_id', sa.Integer(), nullable=False),
    sa.Column('rel_path', sa.String(length=2000), nullable=False),
    sa.Column('size_bytes', sa.BigInteger(), nullable=False),
    sa.Column('mtime', sa.Float(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('category', sa.String(length=30), nullable=False),
    sa.ForeignKeyConstraint(['assessment_id'], ['assessment.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['scan_id'], ['source_scan.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_source_file_assessment_id'), 'source_file', ['assessment_id'], unique=False)
    op.create_index(op.f('ix_source_file_scan_id'), 'source_file', ['scan_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_source_file_scan_id'), table_name='source_file')
    op.drop_index(op.f('ix_source_file_assessment_id'), table_name='source_file')
    op.drop_table('source_file')
    op.drop_index(op.f('ix_source_scan_assessment_id'), table_name='source_scan')
    op.drop_table('source_scan')
