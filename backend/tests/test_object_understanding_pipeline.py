"""SPRINT-09 — AI Object Understanding: durable pipeline stage integration (CAP-008/CAP-009).

`object_understanding` registers as a 4th stage of the existing `source_processing`
PipelineRun (BL-003) — these tests exercise it end to end through `run_pipeline`, with a
fake `AIProvider` swapped in via monkeypatch so no live Bedrock/Azure credentials are needed.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from sqlalchemy import select, text

from ai.provider import AIProviderError, StructuredCompletionResult
from persistence.database import get_session_factory
from persistence.models import (
    Assessment,
    AssessmentStatus,
    Client,
    ObjectUnderstanding,
    PipelineRun,
    SAPObject,
    StageRun,
)
from pipeline.engine import create_pipeline_run, run_pipeline
from settings import get_settings


def _make_assessment(session) -> int:
    c = Client(name="Sprint09 Test Client")
    session.add(c)
    session.flush()
    a = Assessment(client_id=c.id, name="Sprint09 Test", status=AssessmentStatus.CREATED.value)
    session.add(a)
    session.commit()
    return a.id


def _cleanup(session, assessment_id: int) -> None:
    """Remove only the client owning this assessment — cascades to everything under it."""
    session.execute(
        text("DELETE FROM client WHERE id = (SELECT client_id FROM assessment WHERE id = :aid)"),
        {"aid": assessment_id},
    )
    session.commit()


class _FakeProvider:
    name = "fake"
    model_id = "fake-model-1"

    def __init__(self, output: dict | None = None, error: Exception | None = None):
        self._output = output
        self._error = error

    def complete_structured(self, request):
        if self._error is not None:
            raise self._error
        return StructuredCompletionResult(
            output=self._output, provider=self.name, model_id=self.model_id, raw_response={}, stop_reason="tool_use"
        )


def _run_full_pipeline(monkeypatch, asmnt_id: int, tmp: str, fake_provider: _FakeProvider) -> int:
    settings = get_settings()
    monkeypatch.setattr("pipeline.stages.get_provider", lambda settings: fake_provider)
    with get_session_factory()() as session:
        run = create_pipeline_run(session, asmnt_id, tmp)
        run_id = run.id
    run_pipeline(run_id, settings.database_url)
    return run_id


def test_object_understanding_completed_result_persisted(monkeypatch) -> None:
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            (Path(tmp) / "a.abap").write_text("REPORT za.")

            fake = _FakeProvider(
                output={
                    "status": "COMPLETED",
                    "functional_purpose": "Reports on something.",
                    "technical_purpose": "A simple ABAP report.",
                    "concepts": ["reporting"],
                    "confidence": 0.8,
                    "rationale": "Based on source code.",
                    "evidence_refs": ["SRC-1"],
                }
            )
            run_id = _run_full_pipeline(monkeypatch, asmnt_id, tmp, fake)

            with get_session_factory()() as session:
                run = session.get(PipelineRun, run_id)
                assert run.status == "completed"
                stage = session.scalars(
                    select(StageRun).where(
                        StageRun.pipeline_run_id == run_id, StageRun.stage_key == "object_understanding"
                    )
                ).first()
                assert stage.status == "completed"

                obj = session.scalars(select(SAPObject).where(SAPObject.assessment_id == asmnt_id)).first()
                understanding = session.scalars(
                    select(ObjectUnderstanding).where(ObjectUnderstanding.sap_object_id == obj.id)
                ).first()
                assert understanding is not None
                assert understanding.status == "COMPLETED"
                assert understanding.functional_purpose == "Reports on something."
                assert understanding.provider == "fake"
                assert understanding.model_id == "fake-model-1"
                assert understanding.prompt_capability == "object_understanding"
                assert understanding.evidence_refs == [
                    {"ref_id": "SRC-1", "source_type": "SOURCE_CODE", "entity_id": obj.source_file_id}
                ]
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_object_understanding_insufficient_context_persisted(monkeypatch) -> None:
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            (Path(tmp) / "a.abap").write_text("REPORT za.")

            fake = _FakeProvider(
                output={
                    "status": "INSUFFICIENT_CONTEXT",
                    "functional_purpose": "",
                    "technical_purpose": "",
                    "concepts": [],
                    "confidence": 0.1,
                    "rationale": "Not enough evidence.",
                    "evidence_refs": [],
                }
            )
            run_id = _run_full_pipeline(monkeypatch, asmnt_id, tmp, fake)

            with get_session_factory()() as session:
                run = session.get(PipelineRun, run_id)
                assert run.status == "completed"
                obj = session.scalars(select(SAPObject).where(SAPObject.assessment_id == asmnt_id)).first()
                understanding = session.scalars(
                    select(ObjectUnderstanding).where(ObjectUnderstanding.sap_object_id == obj.id)
                ).first()
                assert understanding.status == "INSUFFICIENT_CONTEXT"
                assert understanding.functional_purpose == ""
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_object_understanding_provider_error_marks_failed_without_failing_work_item(monkeypatch) -> None:
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            (Path(tmp) / "a.abap").write_text("REPORT za.")

            fake = _FakeProvider(error=AIProviderError("provider unavailable"))
            run_id = _run_full_pipeline(monkeypatch, asmnt_id, tmp, fake)

            with get_session_factory()() as session:
                run = session.get(PipelineRun, run_id)
                assert run.status == "completed"  # a per-object AI failure is not a pipeline failure
                stage = session.scalars(
                    select(StageRun).where(
                        StageRun.pipeline_run_id == run_id, StageRun.stage_key == "object_understanding"
                    )
                ).first()
                assert stage.status == "completed"
                assert stage.failed_items == 0

                obj = session.scalars(select(SAPObject).where(SAPObject.assessment_id == asmnt_id)).first()
                understanding = session.scalars(
                    select(ObjectUnderstanding).where(ObjectUnderstanding.sap_object_id == obj.id)
                ).first()
                assert understanding.status == "FAILED"
                assert "provider unavailable" in understanding.error
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_object_understanding_domain_validation_failure_persisted_as_failed(monkeypatch) -> None:
    """A schema-valid but domain-invalid response (unknown evidence_refs) must never be
    persisted as COMPLETED — ADR-012 validates evidence references before persistence."""
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            (Path(tmp) / "a.abap").write_text("REPORT za.")

            fake = _FakeProvider(
                output={
                    "status": "COMPLETED",
                    "functional_purpose": "Invented purpose.",
                    "technical_purpose": "",
                    "concepts": [],
                    "confidence": 0.9,
                    "rationale": "Made up.",
                    "evidence_refs": ["SRC-999"],
                }
            )
            run_id = _run_full_pipeline(monkeypatch, asmnt_id, tmp, fake)

            with get_session_factory()() as session:
                run = session.get(PipelineRun, run_id)
                assert run.status == "completed"
                obj = session.scalars(select(SAPObject).where(SAPObject.assessment_id == asmnt_id)).first()
                understanding = session.scalars(
                    select(ObjectUnderstanding).where(ObjectUnderstanding.sap_object_id == obj.id)
                ).first()
                assert understanding.status == "FAILED"
                assert "Domain validation failed" in understanding.error
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_object_understanding_reprocessing_upserts_in_place(monkeypatch) -> None:
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            (Path(tmp) / "a.abap").write_text("REPORT za.")

            fake1 = _FakeProvider(
                output={
                    "status": "COMPLETED", "functional_purpose": "First.", "technical_purpose": "",
                    "concepts": [], "confidence": 0.5, "rationale": "r1", "evidence_refs": ["SRC-1"],
                }
            )
            _run_full_pipeline(monkeypatch, asmnt_id, tmp, fake1)

            fake2 = _FakeProvider(
                output={
                    "status": "COMPLETED", "functional_purpose": "Second.", "technical_purpose": "",
                    "concepts": [], "confidence": 0.9, "rationale": "r2", "evidence_refs": ["SRC-1"],
                }
            )
            _run_full_pipeline(monkeypatch, asmnt_id, tmp, fake2)

            with get_session_factory()() as session:
                obj = session.scalars(select(SAPObject).where(SAPObject.assessment_id == asmnt_id)).first()
                rows = list(
                    session.scalars(select(ObjectUnderstanding).where(ObjectUnderstanding.sap_object_id == obj.id))
                )
                assert len(rows) == 1
                assert rows[0].functional_purpose == "Second."
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_get_object_api_includes_understanding(client, monkeypatch) -> None:
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            (Path(tmp) / "a.abap").write_text("REPORT za.")

            fake = _FakeProvider(
                output={
                    "status": "COMPLETED", "functional_purpose": "Does something.", "technical_purpose": "",
                    "concepts": ["batch"], "confidence": 0.7, "rationale": "r", "evidence_refs": ["SRC-1"],
                }
            )
            _run_full_pipeline(monkeypatch, asmnt_id, tmp, fake)

            with get_session_factory()() as session:
                obj = session.scalars(select(SAPObject).where(SAPObject.assessment_id == asmnt_id)).first()
                obj_id = obj.id

            resp = client.get(f"/assessments/{asmnt_id}/objects/{obj_id}")
            assert resp.status_code == 200
            body = resp.json()
            assert body["understanding"]["status"] == "COMPLETED"
            assert body["understanding"]["functional_purpose"] == "Does something."
            assert body["understanding"]["provider"] == "fake"
            assert body["understanding"]["evidence_refs"] == [
                {"ref_id": "SRC-1", "source_type": "SOURCE_CODE", "entity_id": obj.source_file_id}
            ]
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)
