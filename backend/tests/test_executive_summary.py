"""SPRINT-18 CAP-005 — Executive Summary: registry, domain validator, generator persistence and the
GET/regenerate routes, with a mocked AIProvider (tests scoped to their own client/assessment).
"""
from __future__ import annotations

from sqlalchemy import select, text

from ai.executive_summary import CAPABILITY
from ai.executive_summary.generator import generate_executive_summary
from ai.executive_summary.schema import ExecutiveSummaryResult, ExecutiveSummaryResultStatus, validate_result
from ai.provider import StructuredCompletionResult
from ai.registry import get_version
from persistence.database import get_session_factory
from persistence.models import Assessment, AssessmentStatus, Client, ExecutiveSummary

_COMPLETED_OUTPUT = {
    "status": "COMPLETED",
    "markdown": "## Visão geral\n\nAssessment sem objetos analisados ainda.",
    "evidence_refs": ["SUMMARY-1"],
}


class _FakeProvider:
    name = "fake"
    model_id = "fake-model-1"

    def __init__(self, output: dict) -> None:
        self._output = output

    def complete_structured(self, request):
        assert request.schema_name == "executive_summary_result"
        return StructuredCompletionResult(
            output=self._output, provider=self.name, model_id=self.model_id, raw_response={}, stop_reason="tool_use"
        )


def _make_assessment(session) -> int:
    c = Client(name="Sprint18 ExecSummary Client")
    session.add(c)
    session.flush()
    a = Assessment(client_id=c.id, name="Sprint18 ExecSummary", status=AssessmentStatus.CREATED.value)
    session.add(a)
    session.commit()
    return a.id


def _cleanup(session, assessment_id: int) -> None:
    session.execute(
        text("DELETE FROM client WHERE id = (SELECT client_id FROM assessment WHERE id = :aid)"),
        {"aid": assessment_id},
    )
    session.commit()


def test_executive_summary_v1_registered_pt_br():
    version = get_version(CAPABILITY)
    assert version.schema_name == "executive_summary_result"
    assert "## Visão geral" in version.system_prompt
    assert "pt-BR" in version.system_prompt


def test_validate_result_rules():
    known = {"SUMMARY-1"}
    ok = ExecutiveSummaryResult(status=ExecutiveSummaryResultStatus.COMPLETED, markdown="# x", evidence_refs=["SUMMARY-1"])
    assert validate_result(ok, known) == []
    unknown = ok.model_copy(update={"evidence_refs": ["APP-999"]})
    assert any("not present" in e for e in validate_result(unknown, known))
    empty = ok.model_copy(update={"markdown": "  "})
    assert any("non-empty markdown" in e for e in validate_result(empty, known))
    insufficient = ExecutiveSummaryResult(status=ExecutiveSummaryResultStatus.INSUFFICIENT_CONTEXT)
    assert validate_result(insufficient, known) == []


def test_generator_persists_completed_then_failed_keeps_previous_markdown():
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
    try:
        with get_session_factory()() as session:
            row = generate_executive_summary(session, asmnt_id, "Sprint18", _FakeProvider(_COMPLETED_OUTPUT))
            session.commit()
            assert row.status == "COMPLETED"
            assert row.evidence_refs == [{"ref_id": "SUMMARY-1", "source_type": "STRUCTURED_SUMMARY", "entity_id": None}]
            assert row.model_id == "fake-model-1"

        bad = {**_COMPLETED_OUTPUT, "markdown": "Outro texto", "evidence_refs": ["INVENTED-1"]}
        with get_session_factory()() as session:
            row = generate_executive_summary(session, asmnt_id, "Sprint18", _FakeProvider(bad))
            session.commit()
            assert row.status == "FAILED"
            assert "INVENTED-1" in row.error
            assert row.markdown == _COMPLETED_OUTPUT["markdown"]  # the last good summary stays visible
            count = session.scalars(select(ExecutiveSummary).where(ExecutiveSummary.assessment_id == asmnt_id)).all()
            assert len(count) == 1
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_routes_get_404_then_regenerate(client, monkeypatch):
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
    try:
        assert client.get(f"/assessments/{asmnt_id}/executive-summary").status_code == 404

        monkeypatch.setattr(
            "api.routes.executive_summary.get_provider", lambda settings: _FakeProvider(_COMPLETED_OUTPUT)
        )
        resp = client.post(f"/assessments/{asmnt_id}/executive-summary/regenerate")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "COMPLETED"
        assert body["markdown"].startswith("## Visão geral")
        assert body["generated_at"]

        got = client.get(f"/assessments/{asmnt_id}/executive-summary").json()
        assert got["markdown"] == body["markdown"]
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)
