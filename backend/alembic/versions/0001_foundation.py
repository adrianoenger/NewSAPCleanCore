"""foundation: pgvector extension and seed_run bookkeeping

Revision ID: 0001_foundation
Revises:
Create Date: 2026-09-24
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_foundation"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "seed_run",
        sa.Column("name", sa.String(100), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "applied_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("seed_run")
    op.execute("DROP EXTENSION IF EXISTS vector")
