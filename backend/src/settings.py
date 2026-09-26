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

    # Source ingestion: root under which scans are permitted (must be accessible from the container).
    scan_root: str = "/workspace"
    demo_source_path: str = "/workspace/demo-source"

    # Supplemental evidence packages (ADR-017): uploaded files are stored here by
    # reference, never duplicated into PostgreSQL. Matches the .gitignore'd uploads/ pattern.
    evidence_storage_path: str = "/workspace/uploads/evidence-datasets"

    # LLM provider abstraction (ADR-006/ADR-012). Credentials are resolved by each provider's
    # own SDK (boto3 for Bedrock via AWS_PROFILE/~/.aws; never a static secret in this Settings
    # object) — these fields only select which provider/model to talk to.
    llm_provider: str = "bedrock"
    bedrock_model_id: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    aws_region: str = "us-east-1"
    azure_foundry_endpoint: str | None = None
    azure_foundry_api_key: str | None = None
    azure_foundry_deployment: str | None = None

    # SAP knowledge via MCP (ADR-007): configurable local/dev endpoints for `mcp-sap-docs` and
    # `mcp-abap`. Left unset, each provider is simply skipped (contextual enrichment is optional,
    # never a hard dependency of the demonstrable flow).
    sap_docs_mcp_endpoint: str | None = None
    sap_docs_mcp_tool_name: str = "search"
    abap_mcp_endpoint: str | None = None
    abap_mcp_tool_name: str = "search"


@lru_cache
def get_settings() -> Settings:
    return Settings()
