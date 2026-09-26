"""embeddings

Add `embedding` — one pgvector row per meaningful semantic entity (SAP_OBJECT, APPLICATION,
BUSINESS_RULE, EVIDENCE_RECORD), scoped to its Assessment (Baseline core rule 14, ADR-004).
`entity_type`/`entity_id` is a polymorphic reference with no FK, mirroring
`evidence_correlation.target_type`/`target_id`. A cosine-distance HNSW index supports the
assessment-scoped semantic search service.

Revision ID: 0016_embeddings
Revises: 0015_clean_core_analysis
Create Date: 2026-09-26
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = '0016_embeddings'
down_revision: str | None = '0015_clean_core_analysis'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_EMBEDDING_DIMENSIONS = 1024


def upgrade() -> None:
    op.create_table(
        'embedding',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('assessment_id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(length=30), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('content_text', sa.Text(), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('vector', Vector(_EMBEDDING_DIMENSIONS), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('model_id', sa.String(length=200), nullable=False),
        sa.Column('stage_run_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['assessment_id'], ['assessment.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['stage_run_id'], ['stage_run.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('assessment_id', 'entity_type', 'entity_id', name='ux_embedding_assessment_entity'),
    )
    op.create_index(op.f('ix_embedding_assessment_id'), 'embedding', ['assessment_id'], unique=False)
    op.create_index(op.f('ix_embedding_entity_type'), 'embedding', ['entity_type'], unique=False)
    op.create_index(op.f('ix_embedding_entity_id'), 'embedding', ['entity_id'], unique=False)
    op.create_index(op.f('ix_embedding_stage_run_id'), 'embedding', ['stage_run_id'], unique=False)
    op.create_index(
        op.f('ix_embedding_vector_cosine'),
        'embedding',
        ['vector'],
        unique=False,
        postgresql_using='hnsw',
        postgresql_ops={'vector': 'vector_cosine_ops'},
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_embedding_vector_cosine'), table_name='embedding')
    op.drop_index(op.f('ix_embedding_stage_run_id'), table_name='embedding')
    op.drop_index(op.f('ix_embedding_entity_id'), table_name='embedding')
    op.drop_index(op.f('ix_embedding_entity_type'), table_name='embedding')
    op.drop_index(op.f('ix_embedding_assessment_id'), table_name='embedding')
    op.drop_table('embedding')
