"""object_understanding

Add `object_understanding` — one row per SAPObject holding the current AI-produced
interpretation plus full provider/prompt/schema provenance (ADR-006/ADR-012). Reprocessing
upserts the row rather than appending history, mirroring `SAPObject.canonical_key`'s own
upsert-not-recreate pattern (ADR-017).

Revision ID: 0011_object_understanding
Revises: 0010_pipeline_run_kind
Create Date: 2026-09-26
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0011_object_understanding'
down_revision: str | None = '0010_pipeline_run_kind'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'object_understanding',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('assessment_id', sa.Integer(), nullable=False),
        sa.Column('sap_object_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('functional_purpose', sa.Text(), nullable=False),
        sa.Column('technical_purpose', sa.Text(), nullable=False),
        sa.Column('concepts', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('rationale', sa.Text(), nullable=False),
        sa.Column('evidence_refs', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('model_id', sa.String(length=200), nullable=False),
        sa.Column('prompt_capability', sa.String(length=100), nullable=False),
        sa.Column('prompt_version', sa.String(length=20), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('stage_run_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['assessment_id'], ['assessment.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sap_object_id'], ['sap_object.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['stage_run_id'], ['stage_run.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_object_understanding_assessment_id'), 'object_understanding', ['assessment_id'], unique=False)
    op.create_index(op.f('ix_object_understanding_sap_object_id'), 'object_understanding', ['sap_object_id'], unique=True)
    op.create_index(op.f('ix_object_understanding_stage_run_id'), 'object_understanding', ['stage_run_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_object_understanding_stage_run_id'), table_name='object_understanding')
    op.drop_index(op.f('ix_object_understanding_sap_object_id'), table_name='object_understanding')
    op.drop_index(op.f('ix_object_understanding_assessment_id'), table_name='object_understanding')
    op.drop_table('object_understanding')
