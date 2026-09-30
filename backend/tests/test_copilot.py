"""SPRINT-16 — AI Copilot: registry registration, domain-validator unit tests, and the
`/copilot/ask` route against a real pipeline-produced assessment (mirrors test_dashboard.py's
own fixture pattern) with a mocked AIProvider/EmbeddingProvider.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from sqlalchemy import select, text

from ai.copilot import CAPABILITY
from ai.copilot.context import CopilotContext, CopilotContextItem, CopilotSelection, build_context
from ai.copilot.schema import CopilotAnswerResult, CopilotAnswerStatus, sanitize_result, validate_result
from ai.embedding_provider import EmbeddingProviderError, EmbeddingResult
from ai.provider import StructuredCompletionResult
from ai.registry import get_version
from persistence.database import get_session_factory
from persistence.models import (
    Application,
    ApplicationStatus,
    Assessment,
    AssessmentStatus,
    CleanCoreAssessment,
    Client,
    SAPObject,
    ScanStatus,
    SourceFile,
    SourceScan,
    TechnicalFinding,
    TechnicalFindingSeverity,
    TechnicalFindingSource,
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


# ---------------------------------------------------------------------------
# build_context: critical findings sample (fixes "give me an example of a critical finding"
# refusing with INSUFFICIENT_CONTEXT even though the dashboard shows a nonzero count)
# ---------------------------------------------------------------------------


class _RaisingEmbeddingProvider:
    """No embeddings configured — build_context must still succeed (semantic retrieval is
    enrichment, never a hard dependency, mirrored from ai.knowledge_service's own precedent)."""

    def embed(self, request):
        raise EmbeddingProviderError("no provider configured")


def test_build_context_includes_bounded_sample_of_high_severity_findings(monkeypatch):
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
        scan = SourceScan(
            assessment_id=asmnt_id,
            source_path="/tmp/unused",
            status=ScanStatus.COMPLETED.value,
            total_files=1,
            scanned_files=1,
        )
        session.add(scan)
        session.flush()
        source_file = SourceFile(
            scan_id=scan.id,
            assessment_id=asmnt_id,
            rel_path="ZTEST_REPORT.abap",
            size_bytes=0,
            mtime=0.0,
            sha256="0" * 64,
            category="abap_source",
        )
        session.add(source_file)
        session.flush()
        obj = SAPObject(
            assessment_id=asmnt_id,
            source_file_id=source_file.id,
            object_type="report",
            object_name="ZTEST_REPORT",
            canonical_key="report:ztest_report",
            description="",
            line_start=1,
            line_end=1,
            attributes={},
        )
        session.add(obj)
        session.flush()
        session.add(
            TechnicalFinding(
                assessment_id=asmnt_id,
                sap_object_id=obj.id,
                source=TechnicalFindingSource.ATC.value,
                finding_type="CL_BADI_IMPLEMENTATION",
                severity=TechnicalFindingSeverity.HIGH.value,
                title="Implicit BAdI enhancement detected: ZTEST_REPORT",
                details={},
            )
        )
        session.add(
            TechnicalFinding(
                assessment_id=asmnt_id,
                sap_object_id=None,
                source=TechnicalFindingSource.ATC.value,
                finding_type="MINOR_STYLE_WARNING",
                severity=TechnicalFindingSeverity.LOW.value,
                title="Minor style warning — never surfaced as critical",
                details={},
            )
        )
        session.commit()

        context = build_context(
            session, asmnt_id, "dashboard", None, "Me de um exemplo de finding critico", _RaisingEmbeddingProvider()
        )
        try:
            finding_items = [i for i in context.items if i.source_type == "TECHNICAL_FINDING"]
            assert len(finding_items) == 1
            item = finding_items[0]
            assert "BAdI" in item.summary
            assert item.navigation == CopilotSelection(kind="sap_object", id=obj.id)
            assert not any("style warning" in i.summary.lower() for i in context.items)
        finally:
            _cleanup(session, asmnt_id)


def test_copilot_registers_v2_pt_br_as_latest():
    version = get_version(CAPABILITY)
    assert version.capability == "copilot"
    assert version.version == "v2"
    assert version.schema_name == "copilot_answer_result"
    assert "pt-BR" in version.system_prompt
    assert "CATALOG-OBJECTS" in version.system_prompt
    assert get_version(CAPABILITY, "v1").version == "v1"


# ---------------------------------------------------------------------------
# build_context: assessment catalog + intent routing (SPRINT-18 CAP-004 — "Quais objetos o clean
# core categorizou como Remediar?" used to fail with no citable object/classification data)
# ---------------------------------------------------------------------------


def _seed_catalog(session, asmnt_id: int) -> dict:
    scan = SourceScan(
        assessment_id=asmnt_id,
        source_path="/tmp/unused",
        status=ScanStatus.COMPLETED.value,
        total_files=1,
        scanned_files=1,
    )
    session.add(scan)
    session.flush()
    source_file = SourceFile(
        scan_id=scan.id,
        assessment_id=asmnt_id,
        rel_path="catalog.abap",
        size_bytes=0,
        mtime=0.0,
        sha256="0" * 64,
        category="abap_source",
    )
    session.add(source_file)
    session.flush()
    remediar = Application(assessment_id=asmnt_id, name="Faturamento Z", status=ApplicationStatus.AI_NAMED.value)
    manter = Application(assessment_id=asmnt_id, name="Relatórios Z", status=ApplicationStatus.AI_NAMED.value)
    session.add_all([remediar, manter])
    session.flush()
    for app, rec, rationale in (
        (remediar, "REMEDIAR", "Usa APIs não liberadas apontadas pelo ATC."),
        (manter, "MANTER_AS_IS", "Sem violações relevantes."),
    ):
        session.add(
            CleanCoreAssessment(
                assessment_id=asmnt_id,
                application_id=app.id,
                status="COMPLETED",
                recommendation=rec,
                recommendation_rationale=rationale,
                provider="fake",
                model_id="fake",
                prompt_capability="clean_core_analysis",
                prompt_version="v2",
            )
        )
    for name, app in (("ZFAT_POST", remediar), ("ZFAT_CHECK", remediar), ("ZREP_LIST", manter), ("ZLOOSE", None)):
        session.add(
            SAPObject(
                assessment_id=asmnt_id,
                source_file_id=source_file.id,
                object_type="report",
                object_name=name,
                canonical_key=f"report:{name.lower()}",
                description="",
                line_start=1,
                line_end=1,
                attributes={},
                application_id=app.id if app is not None else None,
            )
        )
    session.commit()
    return {"remediar": remediar.id, "manter": manter.id}


def test_build_context_lists_objects_when_asked():
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
        try:
            _seed_catalog(session, asmnt_id)
            context = build_context(
                session, asmnt_id, "dashboard", None, "Liste os objetos analisados", _RaisingEmbeddingProvider()
            )
            by_ref = {i.ref_id: i for i in context.items}
            assert "CATALOG-CC-DIST" in by_ref
            catalog = by_ref["CATALOG-OBJECTS"].summary
            for name in ("ZFAT_POST", "ZFAT_CHECK", "ZREP_LIST", "ZLOOSE"):
                assert name in catalog
            assert "Remediar" in catalog and "Não classificado" in catalog
            assert len(by_ref) == len(context.items)  # ref_ids are unique
        finally:
            _cleanup(session, asmnt_id)


def test_build_context_routes_category_question_to_that_category():
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
        try:
            ids = _seed_catalog(session, asmnt_id)
            context = build_context(
                session,
                asmnt_id,
                "dashboard",
                None,
                "Quais objetos o clean core categorizou como Remediar, me explique o porquê",
                _RaisingEmbeddingProvider(),
            )
            by_ref = {i.ref_id: i for i in context.items}
            app_item = by_ref[f"CATALOG-CC-{ids['remediar']}"]
            assert "APIs não liberadas" in app_item.summary
            assert "ZFAT_POST" in app_item.summary
            assert app_item.navigation == CopilotSelection(kind="application", id=ids["remediar"])
            assert f"CATALOG-CC-{ids['manter']}" not in by_ref  # filtered to the asked category
            catalog = by_ref["CATALOG-OBJECTS"].summary
            assert "ZFAT_POST" in catalog and "ZFAT_CHECK" in catalog
            assert "ZREP_LIST" not in catalog and "ZLOOSE" not in catalog
        finally:
            _cleanup(session, asmnt_id)


def test_build_context_omits_object_catalog_for_unrelated_question():
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
        try:
            ids = _seed_catalog(session, asmnt_id)
            context = build_context(
                session, asmnt_id, "dashboard", None, "Resuma o assessment", _RaisingEmbeddingProvider()
            )
            refs = {i.ref_id for i in context.items}
            assert "CATALOG-OBJECTS" not in refs
            assert {f"CATALOG-CC-{ids['remediar']}", f"CATALOG-CC-{ids['manter']}"} <= refs
        finally:
            _cleanup(session, asmnt_id)


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


def test_sanitize_result_drops_unknown_refs_and_keeps_known():
    result = CopilotAnswerResult(
        status=CopilotAnswerStatus.ANSWERED,
        answer="x",
        evidence_refs=["SEL-1", "SEL-999", "SEL-1"],
        navigation_ref="SEL-999",
    )
    sanitized = sanitize_result(result, _context())
    assert sanitized.evidence_refs == ["SEL-1"]
    assert sanitized.navigation_ref is None
    assert validate_result(sanitized, _context()) == []


def test_sanitize_result_insufficient_context_with_refs_does_not_fail():
    result = CopilotAnswerResult(
        status=CopilotAnswerStatus.INSUFFICIENT_CONTEXT, answer="não sei", evidence_refs=["SEL-1"]
    )
    sanitized = sanitize_result(result, _context())
    assert sanitized.evidence_refs == []
    assert validate_result(sanitized, _context()) == []


def test_sanitize_result_answered_with_only_unknown_refs_still_fails():
    result = CopilotAnswerResult(status=CopilotAnswerStatus.ANSWERED, answer="x", evidence_refs=["SEL-999"])
    errors = validate_result(sanitize_result(result, _context()), _context())
    assert any("requires at least one evidence_refs entry" in e for e in errors)


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
                        "recommendation": None,
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


def test_ask_insufficient_context_with_refs_is_not_failed(client, monkeypatch):
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
    try:
        copilot_fake = _SequencedFakeProvider(
            outputs={
                "copilot_answer_result": {
                    "status": "INSUFFICIENT_CONTEXT",
                    "answer": "Não há dados suficientes.",
                    "evidence_refs": ["SUMMARY-1"],
                    "navigation_ref": None,
                }
            }
        )
        monkeypatch.setattr("api.routes.copilot.get_provider", lambda settings: copilot_fake)
        monkeypatch.setattr("api.routes.copilot.get_embedding_provider", lambda settings: _FakeEmbeddingProvider())

        resp = client.post(
            f"/assessments/{asmnt_id}/copilot/ask",
            json={"question": "qualquer coisa?", "view": "dashboard", "history": []},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "INSUFFICIENT_CONTEXT"
        assert body["references"] == []
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)
