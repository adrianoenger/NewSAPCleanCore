"""stable_sap_object_identity

Add a stable, Assessment-scoped canonical_key to sap_object so reprocessing
upserts/reconciles instead of deleting and recreating rows (ADR-017,
docs/data/persistence-model.md "Stable SAP object identity"). Existing
duplicate rows produced by the previous delete/recreate behavior are
deduplicated, with ATC/technical-finding correlations repointed to the
surviving row before the duplicates are removed.

`last_seen_stage_run_id` tracks the most recent parse StageRun execution that
reproduced the object, so the parse stage can reconcile (remove) objects no
longer produced by any file in the current scan once that stage run finishes.

Revision ID: 0008_stable_sap_object_identity
Revises: 0007_durable_pipeline_execution
Create Date: 2026-09-25
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0008_stable_sap_object_identity'
down_revision: str | None = '0007_durable_pipeline_execution'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('sap_object', sa.Column('canonical_key', sa.String(length=300), nullable=True))
    op.add_column('sap_object', sa.Column('last_seen_stage_run_id', sa.Integer(), nullable=True))

    # Backfill deterministically from normalized object_type + object_name.
    op.execute(
        "UPDATE sap_object SET canonical_key = upper(object_type) || '::' || upper(object_name) "
        "WHERE canonical_key IS NULL"
    )
    # last_seen_stage_run_id is left NULL for pre-existing rows — there is no historical
    # StageRun to attribute them to; they simply become eligible for the first
    # reconciliation pass the next time their scan's parse stage completes.

    # Deduplicate rows the previous delete/recreate flow left behind for the
    # same logical object: one survivor per (assessment_id, canonical_key),
    # preferring the most recently parsed row.
    op.execute(
        "CREATE TEMP TABLE sap_object_survivor AS "
        "SELECT DISTINCT ON (assessment_id, canonical_key) id AS survivor_id, assessment_id, canonical_key "
        "FROM sap_object ORDER BY assessment_id, canonical_key, parsed_at DESC, id DESC"
    )
    op.execute(
        "CREATE TEMP TABLE sap_object_dup_map AS "
        "SELECT so.id AS dup_id, sv.survivor_id AS survivor_id FROM sap_object so "
        "JOIN sap_object_survivor sv ON sv.assessment_id = so.assessment_id "
        "AND sv.canonical_key = so.canonical_key WHERE so.id <> sv.survivor_id"
    )

    # Re-correlate: repoint existing ATC/technical findings to the survivor
    # before the duplicate sap_object rows are deleted.
    op.execute(
        "UPDATE atc_finding af SET correlated_object_id = dm.survivor_id "
        "FROM sap_object_dup_map dm WHERE af.correlated_object_id = dm.dup_id"
    )
    op.execute(
        "UPDATE technical_finding tf SET sap_object_id = dm.survivor_id "
        "FROM sap_object_dup_map dm WHERE tf.sap_object_id = dm.dup_id"
    )
    op.execute("DELETE FROM sap_object WHERE id IN (SELECT dup_id FROM sap_object_dup_map)")
    op.execute("DROP TABLE sap_object_dup_map")
    op.execute("DROP TABLE sap_object_survivor")

    op.alter_column('sap_object', 'canonical_key', existing_type=sa.String(length=300), nullable=False)
    op.create_index(
        'ux_sap_object_assessment_canonical_key', 'sap_object', ['assessment_id', 'canonical_key'], unique=True
    )
    op.create_index(op.f('ix_sap_object_last_seen_stage_run_id'), 'sap_object', ['last_seen_stage_run_id'])
    op.create_foreign_key(
        'fk_sap_object_last_seen_stage_run_id', 'sap_object', 'stage_run', ['last_seen_stage_run_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_sap_object_last_seen_stage_run_id', 'sap_object', type_='foreignkey')
    op.drop_index(op.f('ix_sap_object_last_seen_stage_run_id'), table_name='sap_object')
    op.drop_index('ux_sap_object_assessment_canonical_key', table_name='sap_object')
    op.drop_column('sap_object', 'last_seen_stage_run_id')
    op.drop_column('sap_object', 'canonical_key')
