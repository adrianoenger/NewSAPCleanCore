"""supplemental_evidence_foundation

Add evidence_dataset, evidence_artifact, evidence_record and evidence_correlation
tables (ADR-017, docs/data/supplemental-evidence-import-contract.md). These persist
imported Panaya/Signavio/FUE packages as canonical, capability-oriented evidence —
never as SAPObject subtypes.

Revision ID: 0009_evidence_foundation
Revises: 0008_stable_sap_object_identity
Create Date: 2026-09-25
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0009_evidence_foundation'
down_revision: str | None = '0008_stable_sap_object_identity'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'evidence_dataset',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('assessment_id', sa.Integer(), nullable=False),
        sa.Column('dataset_type', sa.String(length=50), nullable=False),
        sa.Column('display_name', sa.String(length=200), nullable=False),
        sa.Column('source_filename', sa.String(length=500), nullable=False),
        sa.Column('source_sha256', sa.String(length=64), nullable=False),
        sa.Column('source_size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('importer_name', sa.String(length=100), nullable=False),
        sa.Column('importer_version', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('source_system_hint', sa.String(length=200), nullable=True),
        sa.Column('source_client_hint', sa.String(length=200), nullable=True),
        sa.Column('extracted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('capabilities', postgresql.JSONB(), nullable=False),
        sa.Column('manifest', postgresql.JSONB(), nullable=False),
        sa.Column('warning_summary', postgresql.JSONB(), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['assessment_id'], ['assessment.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_evidence_dataset_assessment_id'), 'evidence_dataset', ['assessment_id'])
    op.create_index(op.f('ix_evidence_dataset_dataset_type'), 'evidence_dataset', ['dataset_type'])
    op.create_index(op.f('ix_evidence_dataset_status'), 'evidence_dataset', ['status'])

    op.create_table(
        'evidence_artifact',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('dataset_id', sa.Integer(), nullable=False),
        sa.Column('member_name', sa.String(length=500), nullable=False),
        sa.Column('artifact_role', sa.String(length=20), nullable=False),
        sa.Column('media_hint', sa.String(length=100), nullable=True),
        sa.Column('size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('sha256', sa.String(length=64), nullable=True),
        sa.Column('storage_path', sa.String(length=2000), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['dataset_id'], ['evidence_dataset.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_evidence_artifact_dataset_id'), 'evidence_artifact', ['dataset_id'])

    op.create_table(
        'evidence_record',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('dataset_id', sa.Integer(), nullable=False),
        sa.Column('artifact_id', sa.Integer(), nullable=True),
        sa.Column('record_type', sa.String(length=100), nullable=False),
        sa.Column('capability', sa.String(length=50), nullable=False),
        sa.Column('source_key', sa.String(length=500), nullable=False),
        sa.Column('record_fingerprint', sa.String(length=64), nullable=False),
        sa.Column('object_name', sa.String(length=200), nullable=True),
        sa.Column('object_type', sa.String(length=100), nullable=True),
        sa.Column('package_name', sa.String(length=200), nullable=True),
        sa.Column('normalized_payload', postgresql.JSONB(), nullable=False),
        sa.Column('raw_payload', postgresql.JSONB(), nullable=True),
        sa.Column('source_locator', postgresql.JSONB(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['dataset_id'], ['evidence_dataset.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['artifact_id'], ['evidence_artifact.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('dataset_id', 'record_fingerprint', name='ux_evidence_record_dataset_fingerprint'),
    )
    op.create_index(op.f('ix_evidence_record_dataset_id'), 'evidence_record', ['dataset_id'])
    op.create_index(op.f('ix_evidence_record_artifact_id'), 'evidence_record', ['artifact_id'])
    op.create_index(op.f('ix_evidence_record_record_type'), 'evidence_record', ['record_type'])
    op.create_index(op.f('ix_evidence_record_capability'), 'evidence_record', ['capability'])
    op.create_index(op.f('ix_evidence_record_object_name'), 'evidence_record', ['object_name'])
    op.create_index(op.f('ix_evidence_record_object_type'), 'evidence_record', ['object_type'])

    op.create_table(
        'evidence_correlation',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('evidence_record_id', sa.Integer(), nullable=False),
        sa.Column('target_type', sa.String(length=50), nullable=False),
        sa.Column('target_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('method', sa.String(length=50), nullable=False),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('rationale', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['evidence_record_id'], ['evidence_record.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_evidence_correlation_evidence_record_id'), 'evidence_correlation', ['evidence_record_id'])
    op.create_index(op.f('ix_evidence_correlation_target_type'), 'evidence_correlation', ['target_type'])
    op.create_index(op.f('ix_evidence_correlation_target_id'), 'evidence_correlation', ['target_id'])
    op.create_index(op.f('ix_evidence_correlation_status'), 'evidence_correlation', ['status'])


def downgrade() -> None:
    op.drop_table('evidence_correlation')
    op.drop_table('evidence_record')
    op.drop_table('evidence_artifact')
    op.drop_table('evidence_dataset')
