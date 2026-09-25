"""SPRINT-01 / SPRINT-04 contract checks: Client and Assessment CRUD-light APIs."""

from sqlalchemy import text

from persistence.database import get_session_factory


def _clean(session, client_id: int) -> None:
    """Remove only the client (and cascaded assessment) this test created —
    never a blanket table wipe against the shared dev database."""
    session.execute(text("DELETE FROM client WHERE id = :id"), {"id": client_id})
    session.commit()


def test_client_create_and_list(client):
    resp = client.post("/clients", json={"name": "Test Corp", "description": "Unit test client"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Test Corp"
    assert "id" in body

    cid = body["id"]
    try:
        resp = client.get("/clients")
        assert resp.status_code == 200
        ids = [c["id"] for c in resp.json()]
        assert cid in ids
    finally:
        with get_session_factory()() as session:
            _clean(session, cid)


def test_assessment_create_and_list(client):
    c = client.post("/clients", json={"name": "TestCo2"}).json()
    cid = c["id"]
    try:
        resp = client.post(
            "/assessments",
            json={"client_id": cid, "name": "Sprint04 Assessment", "sap_source_system": "S4D"},
        )
        assert resp.status_code == 201
        asmnt = resp.json()
        assert asmnt["status"] == "created"
        assert asmnt["client_id"] == cid
        assert asmnt["sap_source_system"] == "S4D"

        resp = client.get("/assessments")
        assert resp.status_code == 200
        assert any(a["id"] == asmnt["id"] for a in resp.json())

        resp = client.get("/assessments", params={"client_id": cid})
        assert resp.status_code == 200
        assert all(a["client_id"] == cid for a in resp.json())
    finally:
        with get_session_factory()() as session:
            _clean(session, cid)


def test_client_not_found(client):
    resp = client.get("/clients/99999")
    assert resp.status_code == 404


def test_assessment_unknown_client(client):
    resp = client.post("/assessments", json={"client_id": 99999, "name": "Orphan"})
    assert resp.status_code == 404


def test_assessment_not_found(client):
    resp = client.get("/assessments/99999")
    assert resp.status_code == 404
