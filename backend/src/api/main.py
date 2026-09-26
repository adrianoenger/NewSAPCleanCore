"""FastAPI application entry point: `uvicorn api.main:app`."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import health
from api.routes.applications import router as applications_router
from api.routes.atc import router as atc_router
from api.routes.business_rules import router as business_rules_router
from api.routes.clients import router as clients_router
from api.routes.dashboard import router as dashboard_router
from api.routes.dependencies import router as dependencies_router
from api.routes.evidence import router as evidence_router
from api.routes.ingestion import assessments_router as ingestion_router
from api.routes.ingestion import config_router as ingestion_config_router
from api.routes.parsing import router as parsing_router
from api.routes.pipeline import router as pipeline_router
from api.routes.sap_knowledge import router as sap_knowledge_router
from api.routes.semantic_search import router as semantic_search_router
from persistence.database import get_session_factory
from pipeline.engine import recover_orphans
from settings import get_settings


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """ADR-005: on startup, requeue pipeline work left RUNNING by an unclean shutdown."""
    with get_session_factory()() as session:
        recover_orphans(session)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=_lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(clients_router)
    app.include_router(ingestion_router)
    app.include_router(ingestion_config_router)
    app.include_router(parsing_router)
    app.include_router(dependencies_router)
    app.include_router(atc_router)
    app.include_router(pipeline_router)
    app.include_router(evidence_router)
    app.include_router(business_rules_router)
    app.include_router(applications_router)
    app.include_router(sap_knowledge_router)
    app.include_router(semantic_search_router)
    app.include_router(dashboard_router)
    return app


app = create_app()
