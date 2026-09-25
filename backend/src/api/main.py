"""FastAPI application entry point: `uvicorn api.main:app`."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import health
from api.routes.atc import router as atc_router
from api.routes.clients import router as clients_router
from api.routes.dependencies import router as dependencies_router
from api.routes.ingestion import assessments_router as ingestion_router
from api.routes.ingestion import config_router as ingestion_config_router
from api.routes.parsing import router as parsing_router
from settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version)
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
    return app


app = create_app()
