"""SPRINT-01 contract checks: Client, SAPSystem and Assessment CRUD-light APIs."""

from sqlalchemy import text

from persistence.database import get_session_factory


def _clean(session) -> None:
    """Remove demo rows created during a test run."""
    session.execute(text("DELETE FROM assessment"))
    session.execute(text("DELETE FROM sap_system"))
    session.execute(text("DELETE FROM client"))
    session.commit()


def test_client_create_and_list(client):
    with get_session_factory()() as session:
        _clean(session)

    resp = client.post("/clients", json={"name": "Test Corp", "description": "Unit test client"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Test Corp"
    assert "id" in body

    cid = body["id"]
    resp = client.get("/clients")
    assert resp.status_code == 200
    ids = [c["id"] for c in resp.json()]
    assert cid in ids

    with get_session_factory()() as session:
        _clean(session)


def test_system_create_and_list(client):
    with get_session_factory()() as session:
        _clean(session)

    c = client.post("/clients", json={"name": "TestCo"}).json()
    cid = c["id"]

    resp = client.post(
        f"/clients/{cid}/systems",
        json={"name": "PRD System", "sid": "PRD", "description": "Production"},
    )
    assert resp.status_code == 201
    sys_body = resp.json()
    assert sys_body["client_id"] == cid
    assert sys_body["sid"] == "PRD"

    resp = client.get(f"/clients/{cid}/systems")
    assert resp.status_code == 200
    assert any(s["id"] == sys_body["id"] for s in resp.json())

    with get_session_factory()() as session:
        _clean(session)


def test_assessment_create_and_list(client):
    with get_session_factory()() as session:
        _clean(session)

    c = client.post("/clients", json={"name": "TestCo2"}).json()
    cid = c["id"]
    s = client.post(f"/clients/{cid}/systems", json={"name": "Dev", "sid": "DEV"}).json()
    sid = s["id"]

    resp = client.post(
        f"/clients/{cid}/systems/{sid}/assessments",
        json={"name": "Sprint01 Assessment"},
    )
    assert resp.status_code == 201
    asmnt = resp.json()
    assert asmnt["status"] == "created"
    assert asmnt["sap_system_id"] == sid

    resp = client.get(f"/clients/{cid}/systems/{sid}/assessments")
    assert resp.status_code == 200
    assert any(a["id"] == asmnt["id"] for a in resp.json())

    with get_session_factory()() as session:
        _clean(session)


def test_client_not_found(client):
    resp = client.get("/clients/99999")
    assert resp.status_code == 404


def test_system_wrong_client(client):
    """System belonging to another client should return 404."""
    with get_session_factory()() as session:
        _clean(session)

    c1 = client.post("/clients", json={"name": "C1"}).json()
    c2 = client.post("/clients", json={"name": "C2"}).json()
    s = client.post(
        f"/clients/{c1['id']}/systems", json={"name": "S1"}
    ).json()

    # Access system via wrong client
    resp = client.get(f"/clients/{c2['id']}/systems/{s['id']}/assessments")
    assert resp.status_code == 404

    with get_session_factory()() as session:
        _clean(session)
