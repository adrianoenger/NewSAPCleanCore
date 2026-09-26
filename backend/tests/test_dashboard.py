"""SPRINT-15 — Results Navigation Perspectives: dashboard-summary aggregation endpoint (CAP-002).

Runs the full `source_processing` pipeline with a fake AIProvider (mirrors
test_clean_core_analysis_pipeline.py's pattern) so `/dashboard-summary` has real objects,
applications, a CANDIDATE business rule and a HIGH technical_risk Clean Core assessment to
aggregate over.
"""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

from sqlalchemy import select, text

from ai.embedding_provider import EmbeddingResult
from ai.provider import StructuredCompletionResult
from persistence.database import get_session_factory
from persistence.models import (
    Assessment,
    AssessmentStatus,
    Client,
    SAPObject,
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
_ONE_RULE_OUTPUT = {
    "status": "COMPLETED",
    "rules": [
        {
            "rule_type": "VALIDATION",
            "condition": "Amount > 0",
            "action": "Reject",
            "confidence": 0.9,
            "rationale": "Guard clause.",
            "evidence_refs": ["SRC-1"],
        }
    ],
}
_INSUFFICIENT_APPLICATION_OUTPUT = {
    "status": "INSUFFICIENT_CONTEXT",
    "name": "",
    "description": "",
    "domain": "",
    "confidence": 0.2,
    "rationale": "Not enough grouped evidence.",
    "evidence_refs": [],
}


def _high_risk_clean_core_output(request) -> dict:
    match = re.search(r"\bOBJ-(\d+)\b", request.user_prompt)
    assert match is not None, "expected at least one OBJ-<id> evidence item in the prompt"
    ref = f"OBJ-{match.group(1)}"
    return {
        "status": "COMPLETED",
        "technical_risk": "HIGH",
        "technical_risk_rationale": "Uses a deprecated dependency.",
        "technical_risk_evidence_refs": [ref],
        "business_importance": "LOW",
        "business_importance_rationale": "No process/usage evidence available.",
        "business_importance_evidence_refs": [ref],
        "recommendation": "REMEDIATE",
        "recommendation_rationale": "High technical risk should be addressed.",
        "recommendation_evidence_refs": [ref],
        "confidence": 0.7,
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
    c = Client(name="Sprint15 Test Client")
    session.add(c)
    session.flush()
    a = Assessment(client_id=c.id, name="Sprint15 Test", status=AssessmentStatus.CREATED.value)
    session.add(a)
    session.commit()
    return a.id


def _cleanup(session, assessment_id: int) -> None:
    session.execute(
        text("DELETE FROM client WHERE id = (SELECT client_id FROM assessment WHERE id = :aid)"),
        {"aid": assessment_id},
    )
    session.commit()


def test_dashboard_summary_aggregates_across_entities(client, monkeypatch) -> None:
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
                    _BUSINESS_RULE_SCHEMA: _ONE_RULE_OUTPUT,
                    _APPLICATION_DISCOVERY_SCHEMA: _INSUFFICIENT_APPLICATION_OUTPUT,
                    _CLEAN_CORE_ANALYSIS_SCHEMA: _high_risk_clean_core_output,
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
                assert obj.application_id is not None

            resp = client.get(f"/assessments/{asmnt_id}/dashboard-summary")
            assert resp.status_code == 200
            body = resp.json()
            assert body["assessment_id"] == asmnt_id
            assert body["objects_analyzed"] == 1
            assert body["customizations_identified"] == 1
            assert body["business_rules_identified"] == 1
            assert body["high_impact_objects"] == 1
            assert body["critical_findings"] == 0
            assert body["is_stale"] is False
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_dashboard_summary_empty_assessment_returns_zeros(client) -> None:
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
    try:
        resp = client.get(f"/assessments/{asmnt_id}/dashboard-summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["objects_analyzed"] == 0
        assert body["customizations_identified"] == 0
        assert body["critical_findings"] == 0
        assert body["high_impact_objects"] == 0
        assert body["business_rules_identified"] == 0
        assert body["is_stale"] is False
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)
