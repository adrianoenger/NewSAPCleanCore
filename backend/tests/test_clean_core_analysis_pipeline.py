"""SPRINT-13 — Clean Core Analysis: durable pipeline stage integration (CAP-004) and API (CAP-005).

`clean_core_analysis` registers as a 7th stage of the existing `source_processing` pipeline,
after `application_discovery` — these tests exercise it end to end through `run_pipeline`, with a
fake `AIProvider` swapped in via monkeypatch so no live Bedrock/Azure credentials are needed.
Mirrors test_application_discovery_pipeline.py's pattern.
"""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

from sqlalchemy import select, text

from ai.provider import AIProviderError, StructuredCompletionResult
from persistence.database import get_session_factory
from persistence.models import (
    Application,
    Assessment,
    AssessmentStatus,
    CleanCoreAssessment,
    CleanCoreStatus,
    Client,
    PipelineRun,
    SAPObject,
    StageRun,
)
from pipeline.engine import create_pipeline_run, run_pipeline
from settings import get_settings

_OBJECT_UNDERSTANDING_SCHEMA = "object_understanding_result"
_BUSINESS_RULE_SCHEMA = "business_rule_discovery_result"
_APPLICATION_DISCOVERY_SCHEMA = "application_discovery_result"
_CLEAN_CORE_ANALYSIS_SCHEMA = "clean_core_analysis_result"

_COMPLETED_UNDERSTANDING_OUTPUT = {
    "status": "COMPLETED",
    "functional_purpose": "Validates a business condition.",
    "technical_purpose": "An ABAP report.",
    "concepts": ["validation"],
    "confidence": 0.8,
    "rationale": "Based on source code.",
    "evidence_refs": ["SRC-1"],
}
_ZERO_RULES_OUTPUT = {"status": "COMPLETED", "rules": []}
_INSUFFICIENT_APPLICATION_OUTPUT = {
    "status": "INSUFFICIENT_CONTEXT",
    "name": "",
    "description": "",
    "domain": "",
    "confidence": 0.2,
    "rationale": "Not enough grouped evidence.",
    "evidence_refs": [],
}


def _completed_clean_core_output_citing_first_object(request) -> dict:
    """Real `OBJ-<sap_object_id>` ref_ids are only known once the object is actually parsed and
    persisted — extract the first one from the rendered evidence text rather than hardcoding an
    id the test does not control."""
    match = re.search(r"\bOBJ-(\d+)\b", request.user_prompt)
    assert match is not None, "expected at least one OBJ-<id> evidence item in the prompt"
    ref = f"OBJ-{match.group(1)}"
    return {
        "status": "COMPLETED",
        "technical_risk": "LOW",
        "technical_risk_rationale": "No open findings and no risky dependencies.",
        "technical_risk_evidence_refs": [ref],
        "business_importance": "LOW",
        "business_importance_rationale": "No process/usage evidence available; based on object identity only.",
        "business_importance_evidence_refs": [ref],
        "recommendation": "RETAIN",
        "recommendation_rationale": "Low risk, low importance — keep as-is.",
        "recommendation_evidence_refs": [ref],
        "confidence": 0.7,
    }


_INSUFFICIENT_CLEAN_CORE_OUTPUT = {
    "status": "INSUFFICIENT_CONTEXT",
    "recommendation": "REVIEW",
    "recommendation_rationale": "Not enough evidence to determine risk or importance.",
    "confidence": 0.1,
}


def _make_assessment(session) -> int:
    c = Client(name="Sprint13 Test Client")
    session.add(c)
    session.flush()
    a = Assessment(client_id=c.id, name="Sprint13 Test", status=AssessmentStatus.CREATED.value)
    session.add(a)
    session.commit()
    return a.id


def _cleanup(session, assessment_id: int) -> None:
    session.execute(
        text("DELETE FROM client WHERE id = (SELECT client_id FROM assessment WHERE id = :aid)"),
        {"aid": assessment_id},
    )
    session.commit()


class _SequencedFakeProvider:
    """Returns a canned (or dynamically computed) output/error per `schema_name`."""

    name = "fake"
    model_id = "fake-model-1"

    def __init__(self, outputs: dict | None = None, errors: dict | None = None):
        self._outputs = outputs or {}
        self._errors = errors or {}

    def complete_structured(self, request):
        if request.schema_name in self._errors:
            raise self._errors[request.schema_name]
        output = self._outputs[request.schema_name]
        if callable(output):
            output = output(request)
        return StructuredCompletionResult(
            output=output, provider=self.name, model_id=self.model_id, raw_response={}, stop_reason="tool_use"
        )


def _run_full_pipeline(monkeypatch, asmnt_id: int, tmp: str, fake_provider: _SequencedFakeProvider) -> int:
    settings = get_settings()
    monkeypatch.setattr("pipeline.stages.get_provider", lambda settings: fake_provider)
    with get_session_factory()() as session:
        run = create_pipeline_run(session, asmnt_id, tmp)
        run_id = run.id
    run_pipeline(run_id, settings.database_url)
    return run_id


def _clean_core_stage(session, run_id: int) -> StageRun:
    return session.scalars(
        select(StageRun).where(StageRun.pipeline_run_id == run_id, StageRun.stage_key == "clean_core_analysis")
    ).first()


def test_clean_core_analysis_completed_result_persisted(monkeypatch) -> None:
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            (Path(tmp) / "a.abap").write_text("REPORT za.")

            fake = _SequencedFakeProvider(
                outputs={
                    _OBJECT_UNDERSTANDING_SCHEMA: _COMPLETED_UNDERSTANDING_OUTPUT,
                    _BUSINESS_RULE_SCHEMA: _ZERO_RULES_OUTPUT,
                    _APPLICATION_DISCOVERY_SCHEMA: _INSUFFICIENT_APPLICATION_OUTPUT,
                    _CLEAN_CORE_ANALYSIS_SCHEMA: _completed_clean_core_output_citing_first_object,
                }
            )
            run_id = _run_full_pipeline(monkeypatch, asmnt_id, tmp, fake)

            with get_session_factory()() as session:
                run = session.get(PipelineRun, run_id)
                assert run.status == "completed"
                stage = _clean_core_stage(session, run_id)
                assert stage.status == "completed"

                obj = session.scalars(select(SAPObject).where(SAPObject.assessment_id == asmnt_id)).one()
                app = session.get(Application, obj.application_id)

                cca = session.scalars(
                    select(CleanCoreAssessment).where(CleanCoreAssessment.application_id == app.id)
                ).one()
                assert cca.status == CleanCoreStatus.COMPLETED.value
                assert cca.technical_risk == "LOW"
                assert cca.business_importance == "LOW"
                assert cca.recommendation == "RETAIN"
                assert cca.business_importance_uses_process_usage_evidence is False
                assert cca.technical_risk_evidence_refs == [
                    {"ref_id": f"OBJ-{obj.id}", "source_type": "SAP_OBJECT", "entity_id": obj.id}
                ]
                assert cca.error is None
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_clean_core_analysis_insufficient_context_is_valid_outcome(monkeypatch) -> None:
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            (Path(tmp) / "a.abap").write_text("REPORT za.")

            fake = _SequencedFakeProvider(
                outputs={
                    _OBJECT_UNDERSTANDING_SCHEMA: _COMPLETED_UNDERSTANDING_OUTPUT,
                    _BUSINESS_RULE_SCHEMA: _ZERO_RULES_OUTPUT,
                    _APPLICATION_DISCOVERY_SCHEMA: _INSUFFICIENT_APPLICATION_OUTPUT,
                    _CLEAN_CORE_ANALYSIS_SCHEMA: _INSUFFICIENT_CLEAN_CORE_OUTPUT,
                }
            )
            run_id = _run_full_pipeline(monkeypatch, asmnt_id, tmp, fake)

            with get_session_factory()() as session:
                run = session.get(PipelineRun, run_id)
                assert run.status == "completed"

                obj = session.scalars(select(SAPObject).where(SAPObject.assessment_id == asmnt_id)).one()
                cca = session.scalars(
                    select(CleanCoreAssessment).where(CleanCoreAssessment.application_id == obj.application_id)
                ).one()
                assert cca.status == CleanCoreStatus.INSUFFICIENT_CONTEXT.value
                assert cca.recommendation == "REVIEW"
                assert cca.technical_risk is None
                assert cca.error is None
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_clean_core_analysis_provider_error_persists_failed_status(monkeypatch) -> None:
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            (Path(tmp) / "a.abap").write_text("REPORT za.")

            fake = _SequencedFakeProvider(
                outputs={
                    _OBJECT_UNDERSTANDING_SCHEMA: _COMPLETED_UNDERSTANDING_OUTPUT,
                    _BUSINESS_RULE_SCHEMA: _ZERO_RULES_OUTPUT,
                    _APPLICATION_DISCOVERY_SCHEMA: _INSUFFICIENT_APPLICATION_OUTPUT,
                },
                errors={_CLEAN_CORE_ANALYSIS_SCHEMA: AIProviderError("boom")},
            )
            run_id = _run_full_pipeline(monkeypatch, asmnt_id, tmp, fake)

            with get_session_factory()() as session:
                run = session.get(PipelineRun, run_id)
                assert run.status == "completed"
                stage = _clean_core_stage(session, run_id)
                assert stage.status == "completed"

                obj = session.scalars(select(SAPObject).where(SAPObject.assessment_id == asmnt_id)).one()
                cca = session.scalars(
                    select(CleanCoreAssessment).where(CleanCoreAssessment.application_id == obj.application_id)
                ).one()
                assert cca.status == CleanCoreStatus.FAILED.value
                assert "boom" in cca.error
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


# ---------------------------------------------------------------------------
# API contract test (CAP-005)
# ---------------------------------------------------------------------------


def test_get_application_api_embeds_clean_core_assessment(client, monkeypatch) -> None:
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            (Path(tmp) / "a.abap").write_text("REPORT za.")

            fake = _SequencedFakeProvider(
                outputs={
                    _OBJECT_UNDERSTANDING_SCHEMA: _COMPLETED_UNDERSTANDING_OUTPUT,
                    _BUSINESS_RULE_SCHEMA: _ZERO_RULES_OUTPUT,
                    _APPLICATION_DISCOVERY_SCHEMA: _INSUFFICIENT_APPLICATION_OUTPUT,
                    _CLEAN_CORE_ANALYSIS_SCHEMA: _completed_clean_core_output_citing_first_object,
                }
            )
            _run_full_pipeline(monkeypatch, asmnt_id, tmp, fake)

            with get_session_factory()() as session:
                app_id = session.scalars(select(Application).where(Application.assessment_id == asmnt_id)).one().id

            resp = client.get(f"/assessments/{asmnt_id}/applications/{app_id}")
            assert resp.status_code == 200
            body = resp.json()
            assert body["clean_core"] is not None
            assert body["clean_core"]["status"] == "COMPLETED"
            assert body["clean_core"]["technical_risk"] == "LOW"
            assert body["clean_core"]["recommendation"] == "RETAIN"

            list_resp = client.get(f"/assessments/{asmnt_id}/applications")
            assert list_resp.json()["applications"][0]["clean_core"]["recommendation"] == "RETAIN"
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)
