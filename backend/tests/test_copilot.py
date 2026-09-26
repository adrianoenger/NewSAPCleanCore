"""SPRINT-16 — AI Copilot: registry registration, domain-validator unit tests, and the
`/copilot/ask` route against a real pipeline-produced assessment (mirrors test_dashboard.py's
own fixture pattern) with a mocked AIProvider/EmbeddingProvider.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from sqlalchemy import select, text

from ai.copilot import CAPABILITY
from ai.copilot.context import CopilotContext, CopilotContextItem, CopilotSelection
from ai.copilot.schema import CopilotAnswerResult, CopilotAnswerStatus, validate_result
from ai.embedding_provider import EmbeddingResult
from ai.provider import StructuredCompletionResult
from ai.registry import get_version
from persistence.database import get_session_factory
from persistence.models import Assessment, AssessmentStatus, Client, SAPObject
from pipeline.engine import create_pipeline_run, run_pipeline
from settings import get_settings

_OBJECT_UNDERSTANDING_SCHEMA = "object_understanding_result"
_BUSINESS_RULE_SCHEMA = "business_rule_discovery_result"
_APPLICATION_DISCOVERY_SCHEMA = "application_discovery_result"
_CLEAN_CORE_ANALYSIS_SCHEMA = "clean_core_analysis_result"

_COMPLETED_UNDERSTANDING_OUTPUT = {
    "status": "COMPLETED",
    "functional_purpose": "Validates order amounts before posting.",
    "technical_purpose": "An ABAP report.",
    "concepts": ["validation"],
    "confidence": 0.8,
    "rationale": "Based on source code.",
    "evidence_refs": ["SRC-1"],
}
_NO_RULES_OUTPUT = {"status": "COMPLETED", "rules": []}
_INSUFFICIENT_APPLICATION_OUTPUT = {
    "status": "INSUFFICIENT_CONTEXT",
    "name": "",
    "description": "",
    "domain": "",
    "confidence": 0.2,
    "rationale": "Not enough grouped evidence.",
    "evidence_refs": [],
}


class _SequencedFakeProvider:
    name = "fake"
    model_id = "fake-model-1"

    def __init__(self, outputs: dict) -> None:
        self._outputs = outputs

    def complete_structured(self, request):
        output = self._outputs[request.schema_name]
        if callable(output):
            output = output(request)
        return StructuredCompletionResult(
            output=output, provider=self.name, model_id=self.model_id, raw_response={}, stop_reason="tool_use"
        )


class _FakeEmbeddingProvider:
    name = "fake"
    model_id = "fake-embed-1"
    dimensions = 1024

    def embed(self, request):
        return EmbeddingResult(
            vectors=[[0.0] * self.dimensions for _ in request.texts],
            provider=self.name,
            model_id=self.model_id,
            dimensions=self.dimensions,
        )


def _make_assessment(session) -> int:
    c = Client(name="Sprint16 Test Client")
    session.add(c)
    session.flush()
    a = Assessment(client_id=c.id, name="Sprint16 Test", status=AssessmentStatus.CREATED.value)
    session.add(a)
    session.commit()
    return a.id


def _cleanup(session, assessment_id: int) -> None:
    session.execute(
        text("DELETE FROM client WHERE id = (SELECT client_id FROM assessment WHERE id = :aid)"),
        {"aid": assessment_id},
    )
    session.commit()


# ---------------------------------------------------------------------------
# ai.registry registration
# ---------------------------------------------------------------------------


def test_copilot_registers_v1():
    version = get_version(CAPABILITY)
    assert version.capability == "copilot"
    assert version.version == "v1"
    assert version.schema_name == "copilot_answer_result"


# ---------------------------------------------------------------------------
# CopilotAnswerResult domain validators (ai.copilot.schema)
# ---------------------------------------------------------------------------


def _context() -> CopilotContext:
    return CopilotContext(
        assessment_id=1,
        view="technical",
        selection=CopilotSelection(kind="sap_object", id=42),
        items=[
            CopilotContextItem(ref_id="SEL-1", source_type="SAP_OBJECT", entity_id=42, summary="report ZA"),
            CopilotContextItem(
                ref_id="SEL-1-UNDERSTANDING", source_type="OBJECT_UNDERSTANDING", entity_id=42, summary="purpose"
            ),
        ],
    )


def test_validate_result_valid_answered_has_no_errors():
    result = CopilotAnswerResult(
        status=CopilotAnswerStatus.ANSWERED, answer="It validates order amounts.", evidence_refs=["SEL-1"]
    )
    assert validate_result(result, _context()) == []


def test_validate_result_rejects_unknown_evidence_ref():
    result = CopilotAnswerResult(status=CopilotAnswerStatus.ANSWERED, answer="x", evidence_refs=["SEL-999"])
    errors = validate_result(result, _context())
    assert any("not present in the context package" in e for e in errors)


def test_validate_result_rejects_answered_without_evidence():
    result = CopilotAnswerResult(status=CopilotAnswerStatus.ANSWERED, answer="x", evidence_refs=[])
    errors = validate_result(result, _context())
    assert any("requires at least one evidence_refs entry" in e for e in errors)


def test_validate_result_rejects_insufficient_context_with_evidence():
    result = CopilotAnswerResult(
        status=CopilotAnswerStatus.INSUFFICIENT_CONTEXT, answer="not sure", evidence_refs=["SEL-1"]
    )
    errors = validate_result(result, _context())
    assert any("must not cite evidence_refs" in e for e in errors)


def test_validate_result_rejects_unknown_navigation_ref():
    result = CopilotAnswerResult(
        status=CopilotAnswerStatus.ANSWERED, answer="x", evidence_refs=["SEL-1"], navigation_ref="SEL-999"
    )
    errors = validate_result(result, _context())
    assert any("navigation_ref" in e for e in errors)


# ---------------------------------------------------------------------------
# POST /assessments/{id}/copilot/ask
# ---------------------------------------------------------------------------


def test_ask_returns_404_for_unknown_assessment(client):
    resp = client.post(
        "/assessments/999999/copilot/ask", json={"question": "what is this?", "view": "technical"}
    )
    assert resp.status_code == 404


def test_ask_answers_grounded_in_selected_object(client, monkeypatch):
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
                    _BUSINESS_RULE_SCHEMA: _NO_RULES_OUTPUT,
                    _APPLICATION_DISCOVERY_SCHEMA: _INSUFFICIENT_APPLICATION_OUTPUT,
                    _CLEAN_CORE_ANALYSIS_SCHEMA: {
                        "status": "INSUFFICIENT_CONTEXT",
                        "recommendation": "REVIEW",
                        "recommendation_rationale": "No grouped application yet.",
                        "confidence": 0.1,
                    },
                }
            )
            monkeypatch.setattr("pipeline.stages.get_provider", lambda settings: fake)
            monkeypatch.setattr("pipeline.stages.get_embedding_provider", lambda settings: _FakeEmbeddingProvider())
            with get_session_factory()() as session:
                run = create_pipeline_run(session, asmnt_id, tmp)
                run_id = run.id
            run_pipeline(run_id, settings.database_url)

            with get_session_factory()() as session:
                obj = session.scalars(select(SAPObject).where(SAPObject.assessment_id == asmnt_id)).one()
                object_id = obj.id

            def _copilot_answer(request):
                assert "SEL-1" in request.user_prompt
                assert "SEL-1-UNDERSTANDING" in request.user_prompt
                return {
                    "status": "ANSWERED",
                    "answer": "This object validates order amounts before posting.",
                    "evidence_refs": ["SEL-1", "SEL-1-UNDERSTANDING"],
                    "navigation_ref": None,
                }

            copilot_fake = _SequencedFakeProvider(outputs={"copilot_answer_result": _copilot_answer})
            monkeypatch.setattr("api.routes.copilot.get_provider", lambda settings: copilot_fake)
            monkeypatch.setattr(
                "api.routes.copilot.get_embedding_provider", lambda settings: _FakeEmbeddingProvider()
            )

            resp = client.post(
                f"/assessments/{asmnt_id}/copilot/ask",
                json={
                    "question": "What does this object do?",
                    "view": "technical",
                    "selection": {"kind": "sap_object", "id": object_id},
                    "history": [],
                },
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "ANSWERED"
            assert "order amounts" in body["answer"]
            ref_ids = {r["ref_id"] for r in body["references"]}
            assert ref_ids == {"SEL-1", "SEL-1-UNDERSTANDING"}
            assert body["navigation"] is None
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_ask_returns_failed_status_on_domain_validation_failure(client, monkeypatch):
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
    try:
        copilot_fake = _SequencedFakeProvider(
            outputs={
                "copilot_answer_result": {
                    "status": "ANSWERED",
                    "answer": "x",
                    "evidence_refs": ["NOT-A-REAL-REF"],
                    "navigation_ref": None,
                }
            }
        )
        monkeypatch.setattr("api.routes.copilot.get_provider", lambda settings: copilot_fake)
        monkeypatch.setattr("api.routes.copilot.get_embedding_provider", lambda settings: _FakeEmbeddingProvider())

        resp = client.post(
            f"/assessments/{asmnt_id}/copilot/ask",
            json={"question": "anything?", "view": "technical", "history": []},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "FAILED"
        assert body["error"] is not None
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)
