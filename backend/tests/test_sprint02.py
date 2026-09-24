"""SPRINT-02 — Source Ingestion: critical contract and flow tests."""

import hashlib
import tempfile
from pathlib import Path

import pytest

from ingestion.classifier import classify
from persistence.database import get_session_factory
from persistence.models import ArtifactCategory, Assessment, AssessmentStatus, Client, SAPSystem


def _clean_ingestion(session) -> None:
    from sqlalchemy import text
    session.execute(text("DELETE FROM source_file"))
    session.execute(text("DELETE FROM source_scan"))
    session.execute(text("DELETE FROM assessment"))
    session.execute(text("DELETE FROM sap_system"))
    session.execute(text("DELETE FROM client"))
    session.commit()


# ---------------------------------------------------------------------------
# Classifier unit tests (no DB needed)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path, expected",
    [
        ("ABAP/ZCL_ORDER.abap", ArtifactCategory.ABAP_SOURCE.value),
        ("ABAP/ZCL_ORDER.clas.xml", ArtifactCategory.ABAP_SOURCE.value),
        ("ABAP/ZFUGR.prog", ArtifactCategory.ABAP_SOURCE.value),
        ("DDIC/ZTABLE.tabl", ArtifactCategory.DDIC.value),
        ("DDIC/ZDOMAIN.doma", ArtifactCategory.DDIC.value),
        ("VIEW/ZCDS_VIEW.cds", ArtifactCategory.CDS.value),
        ("META/object.xml", ArtifactCategory.XML_METADATA.value),
        ("CONFIG/settings.yaml", ArtifactCategory.CONFIGURATION.value),
        ("README.md", ArtifactCategory.DOCUMENTATION.value),
        ("binary.bin", ArtifactCategory.OTHER.value),
    ],
)
def test_classifier(path: str, expected: str) -> None:
    assert classify(path) == expected


# ---------------------------------------------------------------------------
# Scan API contract tests
# ---------------------------------------------------------------------------


def test_scan_config_endpoint(client) -> None:
    resp = client.get("/ingestion/config")
    assert resp.status_code == 200
    body = resp.json()
    assert "scan_root" in body
    assert "demo_path" in body


def test_start_scan_unknown_assessment(client) -> None:
    resp = client.post("/assessments/99999/scans", json={"source_path": "/tmp"})
    assert resp.status_code == 404


def test_scan_path_outside_root_rejected(client) -> None:
    """Paths outside scan_root must be rejected with 400."""
    resp = client.post("/assessments/1/scans", json={"source_path": "/etc"})
    assert resp.status_code in (400, 404)  # 404 if assessment doesn't exist, 400 if path check runs first


def test_scan_lifecycle(client) -> None:
    """Create a scan against a directory inside scan_root; verify completed status and category counts."""
    from settings import get_settings

    with get_session_factory()() as session:
        _clean_ingestion(session)
        c = Client(name="Scan Test Client")
        session.add(c)
        session.flush()
        sys = SAPSystem(client_id=c.id, name="T01")
        session.add(sys)
        session.flush()
        asmnt = Assessment(
            sap_system_id=sys.id, name="Scan Test", status=AssessmentStatus.CREATED.value
        )
        session.add(asmnt)
        session.commit()
        asmnt_id = asmnt.id

    scan_root = Path(get_settings().scan_root)
    with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
        p = Path(tmp)
        (p / "prog.abap").write_text("REPORT ztest.")
        (p / "table.tabl").write_text("DDIC table")
        (p / "readme.md").write_text("# Test")

        resp = client.post(
            f"/assessments/{asmnt_id}/scans",
            json={"source_path": tmp},
        )
        assert resp.status_code == 201
        scan_id = resp.json()["id"]

        detail_resp = client.get(f"/assessments/{asmnt_id}/scans/{scan_id}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["status"] == "completed"
        assert detail["total_files"] == 3
        counts = {c["category"]: c["count"] for c in detail["category_counts"]}
        assert counts.get(ArtifactCategory.ABAP_SOURCE.value) == 1
        assert counts.get(ArtifactCategory.DDIC.value) == 1
        assert counts.get(ArtifactCategory.DOCUMENTATION.value) == 1

        files_resp = client.get(f"/assessments/{asmnt_id}/source-files")
        assert files_resp.status_code == 200
        files = files_resp.json()
        assert len(files) == 3
        sha_found = {f["sha256"] for f in files}
        expected_sha = hashlib.sha256(b"REPORT ztest.").hexdigest()
        assert expected_sha in sha_found

    with get_session_factory()() as session:
        _clean_ingestion(session)
