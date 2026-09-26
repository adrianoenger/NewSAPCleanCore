"""SPRINT-11 — Application Discovery: durable pipeline stage integration (CAP-004).

`application_discovery` registers as a 6th stage of the existing `source_processing` pipeline,
after `business_rule_discovery` — these tests exercise it end to end through `run_pipeline`,
with a fake `AIProvider` swapped in via monkeypatch so no live Bedrock/Azure credentials are
needed. Mirrors test_business_rule_discovery_pipeline.py's pattern.
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
    ApplicationStatus,
    Assessment,
    AssessmentStatus,
    Client,
    PipelineRun,
    SAPObject,
    StageRun,
    WorkItem,
)
from pipeline.engine import create_pipeline_run, run_pipeline
from settings import get_settings

_OBJECT_UNDERSTANDING_SCHEMA = "object_understanding_result"
_BUSINESS_RULE_SCHEMA = "business_rule_discovery_result"
_APPLICATION_DISCOVERY_SCHEMA = "application_discovery_result"
# This file exercises application_discovery only; clean_core_analysis now runs as the next stage
# in the same pipeline (SPRINT-13) and needs *some* schema-valid response to let the run reach
# "completed" — an INSUFFICIENT_CONTEXT/REVIEW stub is a safe default regardless of which
# Application ids these tests happen to create.
_CLEAN_CORE_ANALYSIS_SCHEMA = "clean_core_analysis_result"
_INSUFFICIENT_CLEAN_CORE_OUTPUT = {
    "status": "INSUFFICIENT_CONTEXT",
    "recommendation": "REVIEW",
    "recommendation_rationale": "Not enough grouped evidence.",
    "confidence": 0.2,
}

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


def _completed_application_output_citing_first_object(request) -> dict:
    """Real `OBJ-<sap_object_id>` ref_ids are only known once the object is actually parsed and
    persisted — extract the first one from the rendered evidence text rather than hardcoding an
    id the test does not control."""
    match = re.search(r"\bOBJ-(\d+)\b", request.user_prompt)
    assert match is not None, "expected at least one OBJ-<id> evidence item in the prompt"
    return {
        "status": "COMPLETED",
        "name": "Order Management",
        "description": "Handles order validation and posting.",
        "domain": "Order Management",
        "confidence": 0.9,
        "rationale": "Grounded in the object identity.",
        "evidence_refs": [f"OBJ-{match.group(1)}"],
    }


def _make_assessment(session) -> int:
    c = Client(name="Sprint11 Test Client")
    session.add(c)
    session.flush()
    a = Assessment(client_id=c.id, name="Sprint11 Test", status=AssessmentStatus.CREATED.value)
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
        self._outputs = {_CLEAN_CORE_ANALYSIS_SCHEMA: _INSUFFICIENT_CLEAN_CORE_OUTPUT, **(outputs or {})}
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


def _application_stage(session, run_id: int) -> StageRun:
    return session.scalars(
        select(StageRun).where(StageRun.pipeline_run_id == run_id, StageRun.stage_key == "application_discovery")
    ).first()


def test_application_discovery_completed_result_persisted(monkeypatch) -> None:
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
                    _APPLICATION_DISCOVERY_SCHEMA: _completed_application_output_citing_first_object,
                }
            )
            run_id = _run_full_pipeline(monkeypatch, asmnt_id, tmp, fake)

            with get_session_factory()() as session:
                run = session.get(PipelineRun, run_id)
                assert run.status == "completed"
                stage = _application_stage(session, run_id)
                assert stage.status == "completed"

                obj = session.scalars(select(SAPObject).where(SAPObject.assessment_id == asmnt_id)).one()
                assert obj.application_id is not None

                app = session.get(Application, obj.application_id)
                assert app.status == ApplicationStatus.AI_NAMED.value
                assert app.name == "Order Management"
                assert app.domain == "Order Management"
                assert app.confidence == 0.9
                assert app.evidence_refs == [{"ref_id": f"OBJ-{obj.id}", "source_type": "SAP_OBJECT", "entity_id": obj.id}]
                assert app.error is None
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_application_discovery_insufficient_context_is_valid_outcome(monkeypatch) -> None:
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
                }
            )
            run_id = _run_full_pipeline(monkeypatch, asmnt_id, tmp, fake)

            with get_session_factory()() as session:
                run = session.get(PipelineRun, run_id)
                assert run.status == "completed"

                obj = session.scalars(select(SAPObject).where(SAPObject.assessment_id == asmnt_id)).one()
                app = session.get(Application, obj.application_id)
                assert app.status == ApplicationStatus.CANDIDATE.value
                assert app.name == ""
                assert app.error is None
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_application_discovery_provider_error_leaves_stage_completed(monkeypatch) -> None:
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
                },
                errors={_APPLICATION_DISCOVERY_SCHEMA: AIProviderError("boom")},
            )
            run_id = _run_full_pipeline(monkeypatch, asmnt_id, tmp, fake)

            with get_session_factory()() as session:
                run = session.get(PipelineRun, run_id)
                assert run.status == "completed"
                stage = _application_stage(session, run_id)
                assert stage.status == "completed"

                obj = session.scalars(select(SAPObject).where(SAPObject.assessment_id == asmnt_id)).one()
                # Deterministic membership assigned in `prepare` survives an AI naming failure.
                assert obj.application_id is not None
                app = session.get(Application, obj.application_id)
                assert app.status == ApplicationStatus.CANDIDATE.value
                assert "boom" in app.error
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_application_discovery_reprocessing_preserves_user_renamed(monkeypatch) -> None:
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
                    _APPLICATION_DISCOVERY_SCHEMA: _completed_application_output_citing_first_object,
                }
            )
            _run_full_pipeline(monkeypatch, asmnt_id, tmp, fake)

            with get_session_factory()() as session:
                obj = session.scalars(select(SAPObject).where(SAPObject.assessment_id == asmnt_id)).one()
                app_id = obj.application_id
                app = session.get(Application, app_id)
                app.status = ApplicationStatus.USER_RENAMED.value
                app.name = "Custom Name Chosen By The User"
                session.commit()

            # A second full reprocessing run must never overwrite the user's rename, nor move the
            # object out of it via automatic reconciliation.
            run_id_2 = _run_full_pipeline(monkeypatch, asmnt_id, tmp, fake)

            with get_session_factory()() as session:
                run = session.get(PipelineRun, run_id_2)
                assert run.status == "completed"

                obj = session.scalars(select(SAPObject).where(SAPObject.assessment_id == asmnt_id)).one()
                assert obj.application_id == app_id

                app = session.get(Application, app_id)
                assert app.status == ApplicationStatus.USER_RENAMED.value
                assert app.name == "Custom Name Chosen By The User"
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


# ---------------------------------------------------------------------------
# API contract tests (CAP-005)
# ---------------------------------------------------------------------------


def test_get_application_api_returns_members_rules_and_findings(client, monkeypatch) -> None:
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            (Path(tmp) / "a.abap").write_text("REPORT za.\nCALL FUNCTION 'Z_DO_THING'.")
            (Path(tmp) / "b.abap").write_text("FUNCTION z_do_thing.\nENDFUNCTION.")

            fake = _SequencedFakeProvider(
                outputs={
                    _OBJECT_UNDERSTANDING_SCHEMA: _COMPLETED_UNDERSTANDING_OUTPUT,
                    _BUSINESS_RULE_SCHEMA: _ZERO_RULES_OUTPUT,
                    _APPLICATION_DISCOVERY_SCHEMA: _completed_application_output_citing_first_object,
                }
            )
            _run_full_pipeline(monkeypatch, asmnt_id, tmp, fake)

            with get_session_factory()() as session:
                app_id = session.scalars(select(Application).where(Application.assessment_id == asmnt_id)).one().id

            resp = client.get(f"/assessments/{asmnt_id}/applications/{app_id}")
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == ApplicationStatus.AI_NAMED.value
            assert body["member_count"] == 2
            assert {m["object_name"] for m in body["members"]} == {"ZA", "Z_DO_THING"}
            assert body["business_rules"] == []
            assert body["findings"] == []
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_rename_application_api_sets_user_renamed(client, monkeypatch) -> None:
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
                }
            )
            _run_full_pipeline(monkeypatch, asmnt_id, tmp, fake)

            with get_session_factory()() as session:
                app_id = session.scalars(select(Application).where(Application.assessment_id == asmnt_id)).one().id

            resp = client.patch(
                f"/assessments/{asmnt_id}/applications/{app_id}",
                json={"name": "My Custom App", "description": "Curated by the analyst."},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == ApplicationStatus.USER_RENAMED.value
            assert body["name"] == "My Custom App"
            assert body["description"] == "Curated by the analyst."
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_move_object_api_reassigns_membership_and_updates_list(client, monkeypatch) -> None:
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            (Path(tmp) / "a.abap").write_text("REPORT za.")
            (Path(tmp) / "b.abap").write_text("REPORT zb.")

            fake = _SequencedFakeProvider(
                outputs={
                    _OBJECT_UNDERSTANDING_SCHEMA: _COMPLETED_UNDERSTANDING_OUTPUT,
                    _BUSINESS_RULE_SCHEMA: _ZERO_RULES_OUTPUT,
                    _APPLICATION_DISCOVERY_SCHEMA: _INSUFFICIENT_APPLICATION_OUTPUT,
                }
            )
            _run_full_pipeline(monkeypatch, asmnt_id, tmp, fake)

            with get_session_factory()() as session:
                objs = list(session.scalars(select(SAPObject).where(SAPObject.assessment_id == asmnt_id)))
                assert len(objs) == 2
                app_a_id, app_b_id = objs[0].application_id, objs[1].application_id
                assert app_a_id != app_b_id

            resp = client.post(
                f"/assessments/{asmnt_id}/applications/move-object",
                json={"object_id": objs[0].id, "target_application_id": app_b_id},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["object_id"] == objs[0].id
            assert body["application"]["id"] == app_b_id
            assert body["application"]["member_count"] == 2

            list_resp = client.get(f"/assessments/{asmnt_id}/applications")
            assert list_resp.json()["total"] == 1
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_merge_applications_api_marks_source_merged(client, monkeypatch) -> None:
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            (Path(tmp) / "a.abap").write_text("REPORT za.")
            (Path(tmp) / "b.abap").write_text("REPORT zb.")

            fake = _SequencedFakeProvider(
                outputs={
                    _OBJECT_UNDERSTANDING_SCHEMA: _COMPLETED_UNDERSTANDING_OUTPUT,
                    _BUSINESS_RULE_SCHEMA: _ZERO_RULES_OUTPUT,
                    _APPLICATION_DISCOVERY_SCHEMA: _INSUFFICIENT_APPLICATION_OUTPUT,
                }
            )
            _run_full_pipeline(monkeypatch, asmnt_id, tmp, fake)

            with get_session_factory()() as session:
                objs = list(session.scalars(select(SAPObject).where(SAPObject.assessment_id == asmnt_id)))
                source_id, target_id = objs[0].application_id, objs[1].application_id

            resp = client.post(
                f"/assessments/{asmnt_id}/applications/merge",
                json={"source_application_id": source_id, "target_application_id": target_id},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["id"] == target_id
            assert body["member_count"] == 2

            with get_session_factory()() as session:
                source = session.get(Application, source_id)
                assert source.status == ApplicationStatus.MERGED.value
                assert source.consolidated_into_id == target_id

            list_resp = client.get(f"/assessments/{asmnt_id}/applications")
            assert list_resp.json()["total"] == 1

            list_all_resp = client.get(f"/assessments/{asmnt_id}/applications?include_merged=true")
            assert list_all_resp.json()["total"] == 2
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)
