"""business_rule_discovery

Add `business_rule` — zero, one or several discovered candidate business rules per SAPObject,
derived from its persisted `ObjectUnderstanding` plus the same evidence package (ADR-008/ADR-012).
`consolidated_into_id` implements basic merge handling (a duplicate points at its survivor rather
than being deleted); `user_validated`/`user_validated_at`/`user_notes` are the Functional View's
validation hook.

Pre-existing autogenerate drift on `sap_object`/`technical_finding` indexes (BL-013) is left
untouched — out of this sprint's scope, same as SPRINT-09's migration.

Revision ID: 0012_business_rule_discovery
Revises: 0011_object_understanding
Create Date: 2026-09-26
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0012_business_rule_discovery'
down_revision: str | None = '0011_object_understanding'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'business_rule',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('assessment_id', sa.Integer(), nullable=False),
        sa.Column('sap_object_id', sa.Integer(), nullable=False),
        sa.Column('rule_type', sa.String(length=30), nullable=False),
        sa.Column('condition', sa.Text(), nullable=False),
        sa.Column('action', sa.Text(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('rationale', sa.Text(), nullable=False),
        sa.Column('evidence_refs', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('consolidated_into_id', sa.Integer(), nullable=True),
        sa.Column('user_validated', sa.Boolean(), nullable=False),
        sa.Column('user_validated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('user_notes', sa.Text(), nullable=True),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('model_id', sa.String(length=200), nullable=False),
        sa.Column('prompt_capability', sa.String(length=100), nullable=False),
        sa.Column('prompt_version', sa.String(length=20), nullable=False),
        sa.Column('stage_run_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['assessment_id'], ['assessment.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['consolidated_into_id'], ['business_rule.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['sap_object_id'], ['sap_object.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['stage_run_id'], ['stage_run.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_business_rule_assessment_id'), 'business_rule', ['assessment_id'], unique=False)
    op.create_index(op.f('ix_business_rule_consolidated_into_id'), 'business_rule', ['consolidated_into_id'], unique=False)
    op.create_index(op.f('ix_business_rule_sap_object_id'), 'business_rule', ['sap_object_id'], unique=False)
    op.create_index(op.f('ix_business_rule_stage_run_id'), 'business_rule', ['stage_run_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_business_rule_stage_run_id'), table_name='business_rule')
    op.drop_index(op.f('ix_business_rule_sap_object_id'), table_name='business_rule')
    op.drop_index(op.f('ix_business_rule_consolidated_into_id'), table_name='business_rule')
    op.drop_index(op.f('ix_business_rule_assessment_id'), table_name='business_rule')
    op.drop_table('business_rule')
