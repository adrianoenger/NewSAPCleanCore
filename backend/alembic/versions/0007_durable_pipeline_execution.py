"""durable_pipeline_execution

Add pipeline_run, stage_run, and work_item tables (ADR-005).

Revision ID: 0007_durable_pipeline_execution
Revises: 0006_dependencies_atc_findings
Create Date: 2026-09-24
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0007_durable_pipeline_execution'
down_revision: str | None = '0006_dependencies_atc_findings'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'pipeline_run',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('assessment_id', sa.Integer(), nullable=False),
        sa.Column('source_path', sa.String(length=2000), nullable=False),
        sa.Column('source_scan_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('pause_requested', sa.Boolean(), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['assessment_id'], ['assessment.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_scan_id'], ['source_scan.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_pipeline_run_assessment_id'), 'pipeline_run', ['assessment_id'])

    op.create_table(
        'stage_run',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('pipeline_run_id', sa.Integer(), nullable=False),
        sa.Column('stage_key', sa.String(length=50), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('depends_on', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('total_items', sa.Integer(), nullable=False),
        sa.Column('completed_items', sa.Integer(), nullable=False),
        sa.Column('failed_items', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['pipeline_run_id'], ['pipeline_run.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('pipeline_run_id', 'stage_key'),
    )
    op.create_index(op.f('ix_stage_run_pipeline_run_id'), 'stage_run', ['pipeline_run_id'])
    op.create_index(op.f('ix_stage_run_stage_key'), 'stage_run', ['stage_key'])

    op.create_table(
        'work_item',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('stage_run_id', sa.Integer(), nullable=False),
        sa.Column('item_key', sa.String(length=500), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('max_attempts', sa.Integer(), nullable=False),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['stage_run_id'], ['stage_run.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stage_run_id', 'item_key'),
    )
    op.create_index(op.f('ix_work_item_stage_run_id'), 'work_item', ['stage_run_id'])
    op.create_index(op.f('ix_work_item_status'), 'work_item', ['status'])


def downgrade() -> None:
    op.drop_table('work_item')
    op.drop_table('stage_run')
    op.drop_table('pipeline_run')
