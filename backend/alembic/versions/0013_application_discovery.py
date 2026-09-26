"""application_discovery

Add `application` — discovered candidate custom applications (clusters of `SAPObject`s) named/
described by AI from deterministic clustering signals (ADR-008/ADR-012). Membership is
`sap_object.application_id` (at most one application per object) rather than a join table.
`consolidated_into_id` implements manual merge, mirroring `business_rule.consolidated_into_id`.

Revision ID: 0013_application_discovery
Revises: 0012_business_rule_discovery
Create Date: 2026-09-26
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0013_application_discovery'
down_revision: str | None = '0012_business_rule_discovery'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'application',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('assessment_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('domain', sa.String(length=200), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('rationale', sa.Text(), nullable=False),
        sa.Column('evidence_refs', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('clustering_signals', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('consolidated_into_id', sa.Integer(), nullable=True),
        sa.Column('provider', sa.String(length=50), nullable=True),
        sa.Column('model_id', sa.String(length=200), nullable=True),
        sa.Column('prompt_capability', sa.String(length=100), nullable=True),
        sa.Column('prompt_version', sa.String(length=20), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('stage_run_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['assessment_id'], ['assessment.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['consolidated_into_id'], ['application.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['stage_run_id'], ['stage_run.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_application_assessment_id'), 'application', ['assessment_id'], unique=False)
    op.create_index(op.f('ix_application_consolidated_into_id'), 'application', ['consolidated_into_id'], unique=False)
    op.create_index(op.f('ix_application_stage_run_id'), 'application', ['stage_run_id'], unique=False)

    op.add_column('sap_object', sa.Column('application_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_sap_object_application_id', 'sap_object', 'application', ['application_id'], ['id'], ondelete='SET NULL'
    )
    op.create_index(op.f('ix_sap_object_application_id'), 'sap_object', ['application_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_sap_object_application_id'), table_name='sap_object')
    op.drop_constraint('fk_sap_object_application_id', 'sap_object', type_='foreignkey')
    op.drop_column('sap_object', 'application_id')

    op.drop_index(op.f('ix_application_stage_run_id'), table_name='application')
    op.drop_index(op.f('ix_application_consolidated_into_id'), table_name='application')
    op.drop_index(op.f('ix_application_assessment_id'), table_name='application')
    op.drop_table('application')
