"""SPRINT-18 CAP-006/CAP-007 — `POST .../pipeline-runs/reprocess-ai`: an ai_reprocessing run
re-runs only the AI stages over the scan of the last completed full run (no scan/parse),
regenerates the AI output, and does not make the assessment look unprocessed. Mocked
AIProvider/EmbeddingProvider. `from_stage=application_discovery` starts at application
clustering, reusing the already-persisted object_understanding/business_rule_discovery.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from sqlalchemy import select, text

from ai.embedding_provider import EmbeddingResult
from ai.provider import StructuredCompletionResult
from persistence.database import get_session_factory
from persistence.models import Assessment, AssessmentStatus, Client, ObjectUnderstanding, SourceScan, StageRun
from pipeline.engine import create_pipeline_run, run_pipeline
from pipeline.status import compute_processing_status
from settings import get_settings

from fake_outputs import EXECUTIVE_SUMMARY_SCHEMA, INSUFFICIENT_EXECUTIVE_SUMMARY_OUTPUT

_AI_STAGES = [
    "object_understanding",
    "business_rule_discovery",
    "application_discovery",
    "clean_core_analysis",
    "executive_summary",
    "embeddings",
]


def _outputs(functional_purpose: str) -> dict:
    return {
        "object_understanding_result": {
            "status": "COMPLETED",
            "functional_purpose": functional_purpose,
            "technical_purpose": "Um report ABAP.",
            "concepts": ["validação"],
            "confidence": 0.8,
            "rationale": "Baseado no código-fonte.",
            "evidence_refs": ["SRC-1"],
        },
        "business_rule_discovery_result": {"status": "COMPLETED", "rules": []},
        "application_discovery_result": {
            "status": "INSUFFICIENT_CONTEXT", "name": "", "description": "", "domain": "",
            "confidence": 0.2, "rationale": "Evidência insuficiente.", "evidence_refs": [],
        },
        "clean_core_analysis_result": {
            "status": "INSUFFICIENT_CONTEXT", "recommendation": None,
            "recommendation_rationale": "Sem aplicação agrupada.", "confidence": 0.1,
        },
        EXECUTIVE_SUMMARY_SCHEMA: INSUFFICIENT_EXECUTIVE_SUMMARY_OUTPUT,
    }


class _FakeProvider:
    name = "fake"
    model_id = "fake-model-1"

    def __init__(self, outputs: dict, forbidden_schemas: tuple[str, ...] = ()) -> None:
        self._outputs = outputs
        self._forbidden_schemas = forbidden_schemas

    def complete_structured(self, request):
        assert request.schema_name not in self._forbidden_schemas, (
            f"{request.schema_name} should have been reused, not regenerated"
        )
        return StructuredCompletionResult(
            output=self._outputs[request.schema_name], provider=self.name, model_id=self.model_id,
            raw_response={}, stop_reason="tool_use",
        )


class _FakeEmbeddingProvider:
    name = "fake"
    model_id = "fake-embed-1"
    dimensions = 1024

    def embed(self, request):
        return EmbeddingResult(
            vectors=[[0.0] * self.dimensions for _ in request.texts],
            provider=self.name, model_id=self.model_id, dimensions=self.dimensions,
        )


def _make_assessment(session) -> int:
    c = Client(name="Sprint18 ReprocessAI Client")
    session.add(c)
    session.flush()
    a = Assessment(client_id=c.id, name="Sprint18 ReprocessAI", status=AssessmentStatus.CREATED.value)
    session.add(a)
    session.commit()
    return a.id


def _cleanup(session, assessment_id: int) -> None:
    session.execute(
        text("DELETE FROM client WHERE id = (SELECT client_id FROM assessment WHERE id = :aid)"),
        {"aid": assessment_id},
    )
    session.commit()


def test_reprocess_ai_without_completed_run_is_409(client):
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
    try:
        resp = client.post(f"/assessments/{asmnt_id}/pipeline-runs/reprocess-ai")
        assert resp.status_code == 409
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_reprocess_ai_reruns_only_ai_stages_on_same_scan(client, monkeypatch):
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
    try:
        with tempfile.TemporaryDirectory(dir=Path(settings.scan_root)) as tmp:
            (Path(tmp) / "a.abap").write_text("REPORT za.")
            monkeypatch.setattr("pipeline.stages.get_embedding_provider", lambda settings: _FakeEmbeddingProvider())
            monkeypatch.setattr("pipeline.stages.get_provider", lambda settings: _FakeProvider(_outputs("Original.")))
            with get_session_factory()() as session:
                full_id = create_pipeline_run(session, asmnt_id, tmp).id
            run_pipeline(full_id, settings.database_url)

            monkeypatch.setattr(
                "pipeline.stages.get_provider", lambda settings: _FakeProvider(_outputs("Valida valores do pedido."))
            )
            resp = client.post(f"/assessments/{asmnt_id}/pipeline-runs/reprocess-ai")
            assert resp.status_code == 201
            body = resp.json()
            assert body["kind"] == "ai_reprocessing"
            assert [s["stage_key"] for s in body["stages"]] == _AI_STAGES

            with get_session_factory()() as session:
                scans = session.scalars(select(SourceScan).where(SourceScan.assessment_id == asmnt_id)).all()
                assert len(scans) == 1  # no rescan
                assert body["source_scan_id"] == scans[0].id
                stages = session.scalars(select(StageRun).where(StageRun.pipeline_run_id == body["id"])).all()
                assert {s.status for s in stages} == {"completed"}  # background task ran in TestClient
                understanding = session.scalars(
                    select(ObjectUnderstanding).where(ObjectUnderstanding.assessment_id == asmnt_id)
                ).one()
                assert understanding.functional_purpose == "Valida valores do pedido."
                status = compute_processing_status(session, asmnt_id)
                assert status.is_processed and not status.is_stale
                assert status.latest_run_id == full_id
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_reprocess_ai_from_stage_applications_is_409_without_completed_run(client):
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
    try:
        resp = client.post(
            f"/assessments/{asmnt_id}/pipeline-runs/reprocess-ai?from_stage=application_discovery"
        )
        assert resp.status_code == 409
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_reprocess_ai_from_stage_applications_reuses_understanding_and_rules(client, monkeypatch):
    """SPRINT-18 CAP-007 follow-up: starting at application_discovery must not call the provider
    for object_understanding_result/business_rule_discovery_result — those are reused as
    persisted by the base run — and must run only the 4 downstream stages."""
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
    try:
        with tempfile.TemporaryDirectory(dir=Path(settings.scan_root)) as tmp:
            (Path(tmp) / "a.abap").write_text("REPORT za.")
            monkeypatch.setattr("pipeline.stages.get_embedding_provider", lambda settings: _FakeEmbeddingProvider())
            monkeypatch.setattr("pipeline.stages.get_provider", lambda settings: _FakeProvider(_outputs("Original.")))
            with get_session_factory()() as session:
                full_id = create_pipeline_run(session, asmnt_id, tmp).id
            run_pipeline(full_id, settings.database_url)

            with get_session_factory()() as session:
                original_understanding_id = session.scalars(
                    select(ObjectUnderstanding).where(ObjectUnderstanding.assessment_id == asmnt_id)
                ).one().id

            forbidden = ("object_understanding_result", "business_rule_discovery_result")
            monkeypatch.setattr(
                "pipeline.stages.get_provider",
                lambda settings: _FakeProvider(_outputs("Não deveria ser usado."), forbidden_schemas=forbidden),
            )
            resp = client.post(
                f"/assessments/{asmnt_id}/pipeline-runs/reprocess-ai?from_stage=application_discovery"
            )
            assert resp.status_code == 201
            body = resp.json()
            assert body["kind"] == "ai_reprocessing_applications"
            assert [s["stage_key"] for s in body["stages"]] == _AI_STAGES[2:]

            with get_session_factory()() as session:
                stages = session.scalars(select(StageRun).where(StageRun.pipeline_run_id == body["id"])).all()
                assert {s.status for s in stages} == {"completed"}
                understanding = session.scalars(
                    select(ObjectUnderstanding).where(ObjectUnderstanding.assessment_id == asmnt_id)
                ).one()
                assert understanding.id == original_understanding_id
                assert understanding.functional_purpose == "Original."  # untouched, reused
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)
