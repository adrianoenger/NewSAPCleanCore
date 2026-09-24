"""SPRINT-00 smoke/contract checks. Require the Compose `postgres` service with migrations applied."""

from sqlalchemy import text

from persistence.database import get_session_factory
from persistence.models import SeedRun
from seed.registry import DATASETS, apply_dataset


def test_health_contract(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == {
        "status": "ok",
        "pgvector": True,
        "migration_revision": "0001_foundation",
        "error": None,
    }
    assert {"service", "version", "environment"} <= body.keys()


def test_cors_allows_renderer_origin(client):
    response = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_demo_seed_is_idempotent():
    with get_session_factory()() as session:
        session.execute(text("DELETE FROM seed_run WHERE name = 'demo'"))
        session.commit()
        assert apply_dataset(session, "demo") is True
        assert apply_dataset(session, "demo") is False
        assert session.get(SeedRun, "demo").version == DATASETS["demo"].version
