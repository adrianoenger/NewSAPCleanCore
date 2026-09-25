"""dependencies_atc_findings

Add sap_object_dependency, atc_check, atc_run, atc_finding, and technical_finding tables.

Revision ID: 0006_dependencies_atc_findings
Revises: 0005_assessment_alignment
Create Date: 2026-09-24
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op


revision: str = '0006_dependencies_atc_findings'
down_revision: str | None = '0005_assessment_alignment'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # sap_object_dependency
    op.create_table(
        'sap_object_dependency',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('assessment_id', sa.Integer(), nullable=False),
        sa.Column('source_object_id', sa.Integer(), nullable=False),
        sa.Column('target_name', sa.String(length=200), nullable=False),
        sa.Column('target_type', sa.String(length=50), nullable=True),
        sa.Column('dep_type', sa.String(length=50), nullable=False),
        sa.Column('source_line', sa.Integer(), nullable=True),
        sa.Column('confidence', sa.String(length=20), nullable=False),
        sa.Column('detected_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['assessment_id'], ['assessment.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_object_id'], ['sap_object.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_sap_object_dependency_assessment_id'), 'sap_object_dependency', ['assessment_id'])
    op.create_index(op.f('ix_sap_object_dependency_source_object_id'), 'sap_object_dependency', ['source_object_id'])
    op.create_index(op.f('ix_sap_object_dependency_target_name'), 'sap_object_dependency', ['target_name'])
    op.create_index(op.f('ix_sap_object_dependency_dep_type'), 'sap_object_dependency', ['dep_type'])

    # atc_check
    op.create_table(
        'atc_check',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('check_title', sa.String(length=500), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('check_title'),
    )

    # atc_run
    op.create_table(
        'atc_run',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('assessment_id', sa.Integer(), nullable=False),
        sa.Column('source_filename', sa.String(length=500), nullable=False),
        sa.Column('file_fingerprint', sa.String(length=64), nullable=True),
        sa.Column('selected_worksheet', sa.String(length=200), nullable=True),
        sa.Column('original_headers', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('canonical_mapping', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('unknown_headers', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('missing_known_headers', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('importer_version', sa.String(length=20), nullable=False),
        sa.Column('imported_row_count', sa.Integer(), nullable=False),
        sa.Column('warning_count', sa.Integer(), nullable=False),
        sa.Column('validation_status', sa.String(length=20), nullable=False),
        sa.Column('warnings_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('imported_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['assessment_id'], ['assessment.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_atc_run_assessment_id'), 'atc_run', ['assessment_id'])

    # atc_finding
    op.create_table(
        'atc_finding',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('atc_run_id', sa.Integer(), nullable=False),
        sa.Column('assessment_id', sa.Integer(), nullable=False),
        sa.Column('source_row_number', sa.Integer(), nullable=False),
        sa.Column('row_fingerprint', sa.String(length=64), nullable=True),
        sa.Column('raw_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('normalized_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('mapping_warnings', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=True),
        sa.Column('check_title', sa.String(length=500), nullable=True),
        sa.Column('check_message', sa.Text(), nullable=True),
        sa.Column('object_name_raw', sa.String(length=200), nullable=True),
        sa.Column('object_type_raw', sa.String(length=100), nullable=True),
        sa.Column('exemption_state', sa.String(length=200), nullable=True),
        sa.Column('contact_person', sa.String(length=200), nullable=True),
        sa.Column('package_name_raw', sa.String(length=200), nullable=True),
        sa.Column('first_found_on', sa.Date(), nullable=True),
        sa.Column('object_responsible', sa.String(length=200), nullable=True),
        sa.Column('last_changed_by', sa.String(length=200), nullable=True),
        sa.Column('sap_note_number', sa.String(length=100), nullable=True),
        sa.Column('sap_note_short_text', sa.Text(), nullable=True),
        sa.Column('referenced_application_component', sa.String(length=200), nullable=True),
        sa.Column('referenced_object_type', sa.String(length=100), nullable=True),
        sa.Column('referenced_object_name', sa.String(length=200), nullable=True),
        sa.Column('additional_info', sa.Text(), nullable=True),
        sa.Column('simplification_item_category', sa.String(length=200), nullable=True),
        sa.Column('change_category', sa.String(length=200), nullable=True),
        sa.Column('change_category_description', sa.Text(), nullable=True),
        sa.Column('remarks', sa.Text(), nullable=True),
        sa.Column('correlation_status', sa.String(length=30), nullable=True),
        sa.Column('correlated_object_id', sa.Integer(), nullable=True),
        sa.Column('atc_check_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['atc_run_id'], ['atc_run.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assessment_id'], ['assessment.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['correlated_object_id'], ['sap_object.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['atc_check_id'], ['atc_check.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_atc_finding_atc_run_id'), 'atc_finding', ['atc_run_id'])
    op.create_index(op.f('ix_atc_finding_assessment_id'), 'atc_finding', ['assessment_id'])
    op.create_index(op.f('ix_atc_finding_object_name_raw'), 'atc_finding', ['object_name_raw'])
    op.create_index(op.f('ix_atc_finding_correlation_status'), 'atc_finding', ['correlation_status'])
    op.create_index(op.f('ix_atc_finding_correlated_object_id'), 'atc_finding', ['correlated_object_id'])
    op.create_index(op.f('ix_atc_finding_atc_check_id'), 'atc_finding', ['atc_check_id'])

    # technical_finding
    op.create_table(
        'technical_finding',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('assessment_id', sa.Integer(), nullable=False),
        sa.Column('sap_object_id', sa.Integer(), nullable=True),
        sa.Column('atc_finding_id', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(length=20), nullable=False),
        sa.Column('finding_type', sa.String(length=100), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['assessment_id'], ['assessment.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sap_object_id'], ['sap_object.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['atc_finding_id'], ['atc_finding.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_technical_finding_assessment_id'), 'technical_finding', ['assessment_id'])
    op.create_index(op.f('ix_technical_finding_sap_object_id'), 'technical_finding', ['sap_object_id'])
    op.create_index(op.f('ix_technical_finding_finding_type'), 'technical_finding', ['finding_type'])
    op.create_index(op.f('ix_technical_finding_severity'), 'technical_finding', ['severity'])


def downgrade() -> None:
    op.drop_table('technical_finding')
    op.drop_table('atc_finding')
    op.drop_table('atc_run')
    op.drop_table('atc_check')
    op.drop_table('sap_object_dependency')
