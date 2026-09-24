"""Health endpoint: reports backend liveness and database/pgvector/migration state."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from persistence.database import get_engine
from settings import get_settings

router = APIRouter(tags=["health"])


class DatabaseHealth(BaseModel):
    status: Literal["ok", "unavailable"]
    pgvector: bool = False
    migration_revision: str | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str
    version: str
    environment: str
    database: DatabaseHealth


def check_database() -> DatabaseHealth:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
            pgvector = conn.execute(
                text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
            ).scalar_one()
            revision = None
            if conn.execute(text("SELECT to_regclass('alembic_version')")).scalar_one():
                revision = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        return DatabaseHealth(status="ok", pgvector=bool(pgvector), migration_revision=revision)
    except SQLAlchemyError as exc:
        return DatabaseHealth(status="unavailable", error=exc.__class__.__name__)


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    database = check_database()
    return HealthResponse(
        status="ok" if database.status == "ok" else "degraded",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        database=database,
    )
