"""pipeline_run_kind

Generalize the durable pipeline engine (ADR-005) to run more than one registered
stage set: add `pipeline_run.kind` (default 'source_processing', preserving all
existing runs) and `pipeline_run.evidence_dataset_id` so a 'evidence_import' run
can durably import/correlate one EvidenceDataset without a parallel job system
(ADR-017).

Revision ID: 0010_pipeline_run_kind
Revises: 0009_evidence_foundation
Create Date: 2026-09-25
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0010_pipeline_run_kind'
down_revision: str | None = '0009_evidence_foundation'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'pipeline_run',
        sa.Column('kind', sa.String(length=30), nullable=False, server_default='source_processing'),
    )
    op.alter_column('pipeline_run', 'kind', server_default=None)
    op.create_index(op.f('ix_pipeline_run_kind'), 'pipeline_run', ['kind'])

    op.add_column('pipeline_run', sa.Column('evidence_dataset_id', sa.Integer(), nullable=True))
    op.create_index(
        op.f('ix_pipeline_run_evidence_dataset_id'), 'pipeline_run', ['evidence_dataset_id']
    )
    op.create_foreign_key(
        'fk_pipeline_run_evidence_dataset_id', 'pipeline_run', 'evidence_dataset',
        ['evidence_dataset_id'], ['id'], ondelete='CASCADE',
    )


def downgrade() -> None:
    op.drop_constraint('fk_pipeline_run_evidence_dataset_id', 'pipeline_run', type_='foreignkey')
    op.drop_index(op.f('ix_pipeline_run_evidence_dataset_id'), table_name='pipeline_run')
    op.drop_column('pipeline_run', 'evidence_dataset_id')
    op.drop_index(op.f('ix_pipeline_run_kind'), table_name='pipeline_run')
    op.drop_column('pipeline_run', 'kind')
