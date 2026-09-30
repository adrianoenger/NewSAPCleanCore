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
    ATCFinding,
    ATCRun,
    Client,
    SAPObject,
)
from pipeline.engine import create_pipeline_run, run_pipeline
from settings import get_settings

from fake_outputs import EXECUTIVE_SUMMARY_SCHEMA, INSUFFICIENT_EXECUTIVE_SUMMARY_OUTPUT

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
        "recommendation": "REMEDIAR",
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
        output = {EXECUTIVE_SUMMARY_SCHEMA: INSUFFICIENT_EXECUTIVE_SUMMARY_OUTPUT, **self._outputs}[request.schema_name]
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


def test_dashboard_overview_and_drilldown_lists(client, monkeypatch) -> None:
    """SPRINT-18 CAP-003 (ADR-019): reference-dashboard panels + drill-down lists over one
    classified custom object and a current ATC run with a correlated P1 and an uncorrelated P3."""
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
                object_id = obj.id
                atc_run = ATCRun(assessment_id=asmnt_id, source_filename="atc.xlsx", validation_status="COMPLETED")
                session.add(atc_run)
                session.flush()
                session.add_all(
                    [
                        ATCFinding(
                            atc_run_id=atc_run.id, assessment_id=asmnt_id, source_row_number=1, priority=1,
                            check_title="Check A", object_name_raw=obj.object_name, correlated_object_id=object_id,
                        ),
                        ATCFinding(
                            atc_run_id=atc_run.id, assessment_id=asmnt_id, source_row_number=2, priority=3,
                            check_title="Check B", object_name_raw="ZOTHER",
                        ),
                    ]
                )
                session.commit()

            body = client.get(f"/assessments/{asmnt_id}/dashboard-overview").json()
            assert body["objects_total"] == 1
            assert body["objects_custom"] == 1
            assert body["objects_by_type"] == {"report": 1}
            assert body["atc_total"] == 2
            assert body["atc_by_priority"] == {"1": 1, "3": 1}
            assert body["objects_classified"] == 1
            assert body["clean_core_objects"] == {"REMEDIAR": 1}
            assert body["clean_core_applications"] == {"REMEDIAR": 1}

            listed = client.get(f"/assessments/{asmnt_id}/object-list", params={"recommendation": "REMEDIAR"}).json()
            assert listed["total"] == 1
            assert listed["items"][0]["id"] == object_id
            assert listed["items"][0]["atc_findings"] == 1
            assert listed["items"][0]["is_custom"] is True
            assert client.get(
                f"/assessments/{asmnt_id}/object-list", params={"recommendation": "UNCLASSIFIED"}
            ).json()["total"] == 0
            assert client.get(f"/assessments/{asmnt_id}/object-list", params={"high_impact": True}).json()["total"] == 1

            p1 = client.get(f"/assessments/{asmnt_id}/atc-findings", params={"priority": 1}).json()
            assert p1["total"] == 1
            assert p1["items"][0]["correlated_object_id"] == object_id
            by_object = client.get(f"/assessments/{asmnt_id}/atc-findings", params={"object_id": object_id}).json()
            assert by_object["total"] == 1
            detail = client.get(f"/assessments/{asmnt_id}/atc-findings/{p1['items'][0]['id']}")
            assert detail.status_code == 200
            assert detail.json()["check_title"] == "Check A"
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_atc_imported_before_parse_is_recorrelated_by_parse(client, monkeypatch) -> None:
    """SPRINT-18: ATC correlation happens at import time; an ATC file imported before the source
    was parsed must be re-correlated by `parse_objects` finalize (and TechnicalFinding follows)."""
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
        atc_run = ATCRun(assessment_id=asmnt_id, source_filename="atc.xlsx", validation_status="COMPLETED")
        session.add(atc_run)
        session.flush()
        session.add_all(
            [
                ATCFinding(
                    atc_run_id=atc_run.id, assessment_id=asmnt_id, source_row_number=1, priority=1,
                    check_title="Check A", object_name_raw="za", correlation_status="UNMATCHED",
                ),
                ATCFinding(
                    atc_run_id=atc_run.id, assessment_id=asmnt_id, source_row_number=2, priority=2,
                    check_title="Check B", object_name_raw="ZNOT_IN_SOURCE", correlation_status="UNMATCHED",
                ),
            ]
        )
        session.commit()

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
                run_id = create_pipeline_run(session, asmnt_id, tmp).id
            run_pipeline(run_id, settings.database_url)

            with get_session_factory()() as session:
                obj = session.scalars(select(SAPObject).where(SAPObject.assessment_id == asmnt_id)).one()
                findings = {
                    f.check_title: f
                    for f in session.scalars(select(ATCFinding).where(ATCFinding.assessment_id == asmnt_id))
                }
                assert findings["Check A"].correlated_object_id == obj.id
                assert findings["Check A"].correlation_status == "MATCHED_HEURISTIC"
                assert findings["Check B"].correlated_object_id is None
                assert findings["Check B"].correlation_status == "UNMATCHED"
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)
