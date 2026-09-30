"""executive_summary

Add `executive_summary` — one row per Assessment holding the current AI-generated pt-BR executive
summary (markdown) and the catalog evidence refs it cites (SPRINT-18 CAP-005). Upserted by the
`executive_summary` pipeline stage or the manual regenerate action.

Revision ID: 0018_executive_summary
Revises: 0017_clean_core_taxonomy
Create Date: 2026-09-29
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0018_executive_summary'
down_revision: str | None = '0017_clean_core_taxonomy'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'executive_summary',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('assessment_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('markdown', sa.Text(), nullable=False),
        sa.Column('evidence_refs', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('model_id', sa.String(length=200), nullable=False),
        sa.Column('prompt_capability', sa.String(length=100), nullable=False),
        sa.Column('prompt_version', sa.String(length=20), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('stage_run_id', sa.Integer(), nullable=True),
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['assessment_id'], ['assessment.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['stage_run_id'], ['stage_run.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_executive_summary_assessment_id'), 'executive_summary', ['assessment_id'], unique=True)
    op.create_index(op.f('ix_executive_summary_stage_run_id'), 'executive_summary', ['stage_run_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_executive_summary_stage_run_id'), table_name='executive_summary')
    op.drop_index(op.f('ix_executive_summary_assessment_id'), table_name='executive_summary')
    op.drop_table('executive_summary')
