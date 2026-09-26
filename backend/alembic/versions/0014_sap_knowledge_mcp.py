"""sap_knowledge_mcp

Add `sap_knowledge_reference` — SAP/ABAP guidance retrieved through `mcp-sap-docs`/`mcp-abap`
providers for a specific finding/application (ADR-007/ADR-008). Kept separate from
`evidence_dataset`/`evidence_record` (ADR-017): provenance here is a live MCP retrieval
(provider/query/timestamp), never a dataset imported by the user. `query_fingerprint` lets a
later semantically-equivalent query reuse a prior retrieval (`reused_from_id`) instead of
calling MCP again.

Revision ID: 0014_sap_knowledge_mcp
Revises: 0013_application_discovery
Create Date: 2026-09-26
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0014_sap_knowledge_mcp'
down_revision: str | None = '0013_application_discovery'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'sap_knowledge_reference',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('assessment_id', sa.Integer(), nullable=False),
        sa.Column('target_type', sa.String(length=30), nullable=False),
        sa.Column('target_id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('query', sa.Text(), nullable=False),
        sa.Column('query_fingerprint', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('reference', sa.String(length=500), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('retrieved_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reused_from_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['assessment_id'], ['assessment.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reused_from_id'], ['sap_knowledge_reference.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_sap_knowledge_reference_assessment_id'), 'sap_knowledge_reference', ['assessment_id'], unique=False
    )
    op.create_index(
        op.f('ix_sap_knowledge_reference_query_fingerprint'),
        'sap_knowledge_reference',
        ['query_fingerprint'],
        unique=False,
    )
    op.create_index(
        'ix_sap_knowledge_reference_target', 'sap_knowledge_reference', ['target_type', 'target_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_sap_knowledge_reference_target', table_name='sap_knowledge_reference')
    op.drop_index(op.f('ix_sap_knowledge_reference_query_fingerprint'), table_name='sap_knowledge_reference')
    op.drop_index(op.f('ix_sap_knowledge_reference_assessment_id'), table_name='sap_knowledge_reference')
    op.drop_table('sap_knowledge_reference')
