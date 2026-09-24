"""ORM models. Import every model module here so Alembic autogenerate sees the full metadata."""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from persistence.database import Base


class SeedRun(Base):
    """Records which synthetic seed datasets were applied, keeping seeding idempotent."""

    __tablename__ = "seed_run"

    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    version: Mapped[int] = mapped_column(nullable=False)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
