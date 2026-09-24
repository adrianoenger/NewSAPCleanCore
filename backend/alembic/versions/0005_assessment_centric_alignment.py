"""assessment_centric_alignment

Remove independent SAPSystem entity. Add Assessment.client_id (direct FK to client)
and Assessment.sap_source_system (string attribute). Backfill from existing sap_system
rows before dropping the table.

Revision ID: 0005_assessment_centric_alignment
Revises: 0004_sap_object_parsing
Create Date: 2026-09-24
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0005_assessment_alignment'
down_revision: str | None = '0004_sap_object_parsing'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add new columns to assessment (nullable initially for backfill)
    op.add_column('assessment', sa.Column('client_id', sa.Integer(), nullable=True))
    op.add_column('assessment', sa.Column('sap_source_system', sa.Text(), nullable=True))

    # 2. Backfill client_id and sap_source_system from sap_system
    op.execute(
        sa.text("""
        UPDATE assessment
        SET
            client_id = ss.client_id,
            sap_source_system = CASE
                WHEN ss.sid IS NOT NULL THEN ss.name || ' (' || ss.sid || ')'
                ELSE ss.name
            END
        FROM sap_system ss
        WHERE assessment.sap_system_id = ss.id
        """)
    )

    # 3. Make client_id NOT NULL now that it is populated
    op.alter_column('assessment', 'client_id', nullable=False)

    # 4. Add FK constraint from assessment.client_id to client.id
    op.create_foreign_key(
        'fk_assessment_client_id',
        'assessment', 'client',
        ['client_id'], ['id'],
        ondelete='CASCADE',
    )

    # 5. Add index for client_id
    op.create_index(op.f('ix_assessment_client_id'), 'assessment', ['client_id'], unique=False)

    # 6. Drop FK from assessment.sap_system_id to sap_system.id
    op.drop_constraint('assessment_sap_system_id_fkey', 'assessment', type_='foreignkey')

    # 7. Drop index on assessment.sap_system_id
    op.drop_index(op.f('ix_assessment_sap_system_id'), table_name='assessment')

    # 8. Drop assessment.sap_system_id column
    op.drop_column('assessment', 'sap_system_id')

    # 9. Drop sap_system table (index first)
    op.drop_index(op.f('ix_sap_system_client_id'), table_name='sap_system')
    op.drop_table('sap_system')


def downgrade() -> None:
    # Recreate sap_system table
    op.create_table(
        'sap_system',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('sid', sa.String(length=10), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['client.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_sap_system_client_id'), 'sap_system', ['client_id'], unique=False)

    # Re-add sap_system_id to assessment
    op.add_column('assessment', sa.Column('sap_system_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_assessment_sap_system_id'), 'assessment', ['sap_system_id'], unique=False)
    op.create_foreign_key(
        'assessment_sap_system_id_fkey',
        'assessment', 'sap_system',
        ['sap_system_id'], ['id'],
        ondelete='CASCADE',
    )

    # Drop new columns
    op.drop_index(op.f('ix_assessment_client_id'), table_name='assessment')
    op.drop_constraint('fk_assessment_client_id', 'assessment', type_='foreignkey')
    op.drop_column('assessment', 'sap_source_system')
    op.drop_column('assessment', 'client_id')
