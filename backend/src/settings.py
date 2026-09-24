"""Application configuration loaded from environment variables (see `.env.example`)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CCA_", extra="ignore")

    app_name: str = "SAP Clean Core Analyzer"
    app_version: str = "0.1.0"
    environment: str = "development"

    database_url: str = "postgresql+psycopg://cleancore:cleancore@postgres:5432/cleancore"

    # Renderer origins allowed to call the API: Vite dev server and packaged Electron (file:// -> "null").
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173", "null"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
