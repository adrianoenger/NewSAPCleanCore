"""clean core 7-category taxonomy

ADR-018: `clean_core_assessment.recommendation` moves from the 5-value taxonomy
(RETAIN/REMEDIATE/REPLATFORM/RETIRE/REVIEW) to the 7 Clean Core categories and becomes nullable —
there is no fallback category, a failed/insufficient-context analysis persists NULL ("Não
classificado"). Existing rows are mapped; the reprocessing (SPRINT-18 CAP-007) regenerates them.

Revision ID: 0017_clean_core_taxonomy
Revises: 0016_embeddings
Create Date: 2026-09-29
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0017_clean_core_taxonomy'
down_revision: str | None = '0016_embeddings'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FORWARD = {
    'RETAIN': 'MANTER_AS_IS',
    'REMEDIATE': 'REMEDIAR',
    'REPLATFORM': 'REIMPLEMENTAR_EXTENSAO',
    'RETIRE': 'DESCONTINUAR',
}

_BACKWARD = {
    'MANTER_AS_IS': 'RETAIN',
    'REMEDIAR': 'REMEDIATE',
    'MODERNIZAR': 'REMEDIATE',
    'ATUALIZAR_OSS': 'REMEDIATE',
    'REIMPLEMENTAR_EXTENSAO': 'REPLATFORM',
    'SUBSTITUIR_STANDARD': 'REPLATFORM',
    'DESCONTINUAR': 'RETIRE',
}


def upgrade() -> None:
    op.alter_column(
        'clean_core_assessment',
        'recommendation',
        existing_type=sa.String(length=20),
        type_=sa.String(length=30),
        nullable=True,
    )
    for old, new in _FORWARD.items():
        op.execute(
            sa.text("UPDATE clean_core_assessment SET recommendation = :new WHERE recommendation = :old").bindparams(
                new=new, old=old
            )
        )
    op.execute("UPDATE clean_core_assessment SET recommendation = NULL WHERE recommendation = 'REVIEW'")


def downgrade() -> None:
    for new, old in _BACKWARD.items():
        op.execute(
            sa.text("UPDATE clean_core_assessment SET recommendation = :old WHERE recommendation = :new").bindparams(
                old=old, new=new
            )
        )
    op.execute("UPDATE clean_core_assessment SET recommendation = 'REVIEW' WHERE recommendation IS NULL")
    op.alter_column(
        'clean_core_assessment',
        'recommendation',
        existing_type=sa.String(length=30),
        type_=sa.String(length=20),
        nullable=False,
    )
