"""clean_core_analysis

Add `clean_core_assessment` — one row per `Application` holding the current AI-produced Clean
Core conclusion: Technical Risk, Business Importance and Recommendation kept as separate,
evidence-bound dimensions (Baseline core rule 8), with a `REVIEW` recommendation fallback for
insufficient-context or conflicting-evidence outcomes. Mirrors `object_understanding`'s
upsert-not-recreate + provider provenance pattern.

Revision ID: 0015_clean_core_analysis
Revises: 0014_sap_knowledge_mcp
Create Date: 2026-09-26
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0015_clean_core_analysis'
down_revision: str | None = '0014_sap_knowledge_mcp'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'clean_core_assessment',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('assessment_id', sa.Integer(), nullable=False),
        sa.Column('application_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('technical_risk', sa.String(length=20), nullable=True),
        sa.Column('technical_risk_rationale', sa.Text(), nullable=False),
        sa.Column('technical_risk_evidence_refs', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('business_importance', sa.String(length=20), nullable=True),
        sa.Column('business_importance_rationale', sa.Text(), nullable=False),
        sa.Column('business_importance_evidence_refs', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('business_importance_uses_process_usage_evidence', sa.Boolean(), nullable=False),
        sa.Column('recommendation', sa.String(length=20), nullable=False),
        sa.Column('recommendation_rationale', sa.Text(), nullable=False),
        sa.Column('recommendation_evidence_refs', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('model_id', sa.String(length=200), nullable=False),
        sa.Column('prompt_capability', sa.String(length=100), nullable=False),
        sa.Column('prompt_version', sa.String(length=20), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('stage_run_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['assessment_id'], ['assessment.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['application_id'], ['application.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['stage_run_id'], ['stage_run.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_clean_core_assessment_assessment_id'), 'clean_core_assessment', ['assessment_id'], unique=False)
    op.create_index(op.f('ix_clean_core_assessment_application_id'), 'clean_core_assessment', ['application_id'], unique=True)
    op.create_index(op.f('ix_clean_core_assessment_stage_run_id'), 'clean_core_assessment', ['stage_run_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_clean_core_assessment_stage_run_id'), table_name='clean_core_assessment')
    op.drop_index(op.f('ix_clean_core_assessment_application_id'), table_name='clean_core_assessment')
    op.drop_index(op.f('ix_clean_core_assessment_assessment_id'), table_name='clean_core_assessment')
    op.drop_table('clean_core_assessment')
