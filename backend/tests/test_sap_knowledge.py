"""SPRINT-12 — SAP Knowledge via MCP: provider adapter, guidance service (cache/reuse,
query-only-when-relevant) and API route tests (ADR-007/ADR-008).

No real `mcp-sap-docs`/`mcp-abap` Docker container is available this sprint — the generic MCP
adapter is unit-tested against a mocked transport, and the service/route tests swap in a fake
`SAPKnowledgeProvider` via monkeypatch, mirroring how Azure AI Foundry was unit-tested without
live credentials (test_ai_providers.py). Live validation against a real MCP server is deferred
(see SESSION_HANDOFF.md).
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from ai.knowledge_provider import (
    KnowledgeQuery,
    KnowledgeQueryResult,
    KnowledgeReference,
    SAPKnowledgeProviderError,
)
from ai.knowledge_providers import get_knowledge_providers
from ai.knowledge_providers.mcp_client import MCPKnowledgeProvider
from ai.knowledge_service import SapKnowledgeTargetNotFound, build_query_text, fetch_guidance, list_guidance
from persistence.database import get_session_factory
from persistence.models import (
    Application,
    ApplicationStatus,
    Assessment,
    AssessmentStatus,
    BusinessRule,
    BusinessRuleStatus,
    Client,
    SapKnowledgeTargetType,
    SourceFile,
    SourceScan,
    SAPObject,
)
from settings import Settings

# ---------------------------------------------------------------------------
# Fixtures / helpers (mirrors test_application_discovery_pipeline.py's own pattern)
# ---------------------------------------------------------------------------


def _make_assessment(session) -> int:
    c = Client(name="Sprint12 Test Client")
    session.add(c)
    session.flush()
    a = Assessment(client_id=c.id, name="Sprint12 Test", status=AssessmentStatus.CREATED.value)
    session.add(a)
    session.commit()
    return a.id


def _cleanup(session, assessment_id: int) -> None:
    session.execute(
        text("DELETE FROM client WHERE id = (SELECT client_id FROM assessment WHERE id = :aid)"),
        {"aid": assessment_id},
    )
    session.commit()


def _make_application(session, assessment_id: int, name: str, description: str) -> int:
    app = Application(
        assessment_id=assessment_id,
        name=name,
        description=description,
        domain="Sales",
        rationale="",
        evidence_refs=[],
        clustering_signals=[],
        status=ApplicationStatus.AI_NAMED.value,
    )
    session.add(app)
    session.commit()
    return app.id


def _make_business_rule(session, assessment_id: int, condition: str, action: str) -> int:
    scan = SourceScan(assessment_id=assessment_id, source_path="/tmp/fixture", status="completed")
    session.add(scan)
    session.flush()
    source_file = SourceFile(
        scan_id=scan.id, assessment_id=assessment_id, rel_path="ZA.abap", size_bytes=10, mtime=0.0,
        sha256="0" * 64, category="abap",
    )
    session.add(source_file)
    session.flush()
    obj = SAPObject(
        assessment_id=assessment_id, source_file_id=source_file.id, object_type="report",
        object_name="ZA", canonical_key="REPORT::ZA",
    )
    session.add(obj)
    session.flush()
    rule = BusinessRule(
        assessment_id=assessment_id, sap_object_id=obj.id, rule_type="VALIDATION", condition=condition,
        action=action, confidence=0.8, rationale="", evidence_refs=[], status=BusinessRuleStatus.CANDIDATE.value,
        provider="fake", model_id="fake-1", prompt_capability="business_rule_discovery", prompt_version="v1",
    )
    session.add(rule)
    session.commit()
    return rule.id


class _FakeKnowledgeProvider:
    def __init__(self, name: str, references: list[KnowledgeReference] | None = None, error: Exception | None = None):
        self.name = name
        self._references = references if references is not None else [
            KnowledgeReference(title="Custom Code Guideline", reference="mcp://fake/doc-1", summary="Avoid modifying standard tables.")
        ]
        self._error = error
        self.call_count = 0

    def query(self, query: KnowledgeQuery) -> KnowledgeQueryResult:
        self.call_count += 1
        if self._error is not None:
            raise self._error
        return KnowledgeQueryResult(provider=self.name, references=self._references)


# ---------------------------------------------------------------------------
# ai.knowledge_service.build_query_text
# ---------------------------------------------------------------------------


def test_build_query_text_application():
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
    try:
        with get_session_factory()() as session:
            app_id = _make_application(session, asmnt_id, "Order Management", "Handles order validation.")
            text_ = build_query_text(session, asmnt_id, SapKnowledgeTargetType.APPLICATION.value, app_id)
            assert text_ == "Order Management. Handles order validation"
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_build_query_text_business_rule():
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
    try:
        with get_session_factory()() as session:
            rule_id = _make_business_rule(session, asmnt_id, "if order value > 10000", "require manager approval")
            text_ = build_query_text(session, asmnt_id, SapKnowledgeTargetType.BUSINESS_RULE.value, rule_id)
            assert text_ == "if order value > 10000 require manager approval"
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_build_query_text_missing_target_raises():
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
    try:
        with get_session_factory()() as session:
            with pytest.raises(SapKnowledgeTargetNotFound):
                build_query_text(session, asmnt_id, SapKnowledgeTargetType.APPLICATION.value, 999999)
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


# ---------------------------------------------------------------------------
# ai.knowledge_service.fetch_guidance — query-only-when-relevant + cache/reuse
# ---------------------------------------------------------------------------


def test_fetch_guidance_persists_and_is_idempotent_per_target():
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
    try:
        with get_session_factory()() as session:
            app_id = _make_application(session, asmnt_id, "Order Management", "Handles order validation.")
            provider = _FakeKnowledgeProvider("sap_docs_mcp")

            first = fetch_guidance(session, asmnt_id, SapKnowledgeTargetType.APPLICATION.value, app_id, [provider])
            assert len(first) == 1
            assert first[0].title == "Custom Code Guideline"
            assert first[0].reused_from_id is None
            assert provider.call_count == 1

            second = fetch_guidance(session, asmnt_id, SapKnowledgeTargetType.APPLICATION.value, app_id, [provider])
            assert len(second) == 1
            assert provider.call_count == 1  # already relevant guidance present — not re-queried
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_fetch_guidance_reuses_cache_across_semantically_equivalent_targets():
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
    try:
        with get_session_factory()() as session:
            app1_id = _make_application(session, asmnt_id, "Order Management", "Handles order validation.")
            app2_id = _make_application(session, asmnt_id, "Order Management", "Handles order validation.")
            provider = _FakeKnowledgeProvider("sap_docs_mcp")

            fetch_guidance(session, asmnt_id, SapKnowledgeTargetType.APPLICATION.value, app1_id, [provider])
            assert provider.call_count == 1

            second = fetch_guidance(session, asmnt_id, SapKnowledgeTargetType.APPLICATION.value, app2_id, [provider])
            assert provider.call_count == 1  # same fingerprint — reused, not re-queried
            assert len(second) == 1
            assert second[0].reused_from_id is not None
            assert second[0].title == "Custom Code Guideline"
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_fetch_guidance_skips_failing_provider():
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
    try:
        with get_session_factory()() as session:
            app_id = _make_application(session, asmnt_id, "Order Management", "Handles order validation.")
            provider = _FakeKnowledgeProvider("sap_docs_mcp", error=SAPKnowledgeProviderError("mcp-sap-docs unreachable"))

            result = fetch_guidance(session, asmnt_id, SapKnowledgeTargetType.APPLICATION.value, app_id, [provider])
            assert result == []
            assert list_guidance(session, asmnt_id, SapKnowledgeTargetType.APPLICATION.value, app_id) == []
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_fetch_guidance_target_not_found_raises():
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
    try:
        with get_session_factory()() as session:
            with pytest.raises(SapKnowledgeTargetNotFound):
                fetch_guidance(session, asmnt_id, SapKnowledgeTargetType.APPLICATION.value, 999999, [])
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


# ---------------------------------------------------------------------------
# ai.knowledge_providers.get_knowledge_providers — configurable, optional endpoints
# ---------------------------------------------------------------------------


def test_get_knowledge_providers_empty_when_unset():
    settings = Settings()
    assert get_knowledge_providers(settings) == []


def test_get_knowledge_providers_configured():
    settings = Settings(sap_docs_mcp_endpoint="http://sap-docs:39301/mcp", abap_mcp_endpoint="http://abap:39302/mcp")
    providers = get_knowledge_providers(settings)
    assert [p.name for p in providers] == ["sap_docs_mcp", "abap_mcp"]


# ---------------------------------------------------------------------------
# ai.knowledge_providers.mcp_client.MCPKnowledgeProvider — mocked MCP transport
# ---------------------------------------------------------------------------


class _FakeContentBlock:
    def __init__(self, text: str, type_: str = "text"):
        self.text = text
        self.type = type_


class _FakeCallToolResult:
    def __init__(self, content: list, is_error: bool = False):
        self.content = content
        self.is_error = is_error


class _FakeSession:
    def __init__(self, result: _FakeCallToolResult):
        self._result = result
        self.last_call: tuple[str, dict] | None = None

    async def initialize(self) -> None:
        return None

    async def call_tool(self, name: str, arguments: dict):
        self.last_call = (name, arguments)
        return self._result

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False


class _FakeStreamContext:
    async def __aenter__(self):
        return (object(), object())

    async def __aexit__(self, *exc_info):
        return False


def test_mcp_provider_query_returns_references(monkeypatch):
    fake_session = _FakeSession(_FakeCallToolResult(content=[_FakeContentBlock("Title line\nSummary body")]))
    monkeypatch.setattr("ai.knowledge_providers.mcp_client.streamable_http_client", lambda endpoint: _FakeStreamContext())
    monkeypatch.setattr("ai.knowledge_providers.mcp_client.ClientSession", lambda read, write: fake_session)

    provider = MCPKnowledgeProvider(name="sap_docs_mcp", endpoint="http://x/mcp", tool_name="search")
    result = provider.query(KnowledgeQuery(text="pricing procedure"))

    assert result.provider == "sap_docs_mcp"
    assert len(result.references) == 1
    assert result.references[0].title == "Title line"
    assert result.references[0].summary == "Summary body"
    assert fake_session.last_call == ("search", {"query": "pricing procedure"})


def test_mcp_provider_query_wraps_transport_errors(monkeypatch):
    def _raise(endpoint):
        raise RuntimeError("connection refused")

    monkeypatch.setattr("ai.knowledge_providers.mcp_client.streamable_http_client", _raise)
    provider = MCPKnowledgeProvider(name="sap_docs_mcp", endpoint="http://x/mcp", tool_name="search")
    with pytest.raises(SAPKnowledgeProviderError, match="MCP call failed"):
        provider.query(KnowledgeQuery(text="q"))


def test_mcp_provider_query_error_result_raises(monkeypatch):
    fake_session = _FakeSession(_FakeCallToolResult(content=[], is_error=True))
    monkeypatch.setattr("ai.knowledge_providers.mcp_client.streamable_http_client", lambda endpoint: _FakeStreamContext())
    monkeypatch.setattr("ai.knowledge_providers.mcp_client.ClientSession", lambda read, write: fake_session)

    provider = MCPKnowledgeProvider(name="sap_docs_mcp", endpoint="http://x/mcp", tool_name="search")
    with pytest.raises(SAPKnowledgeProviderError, match="returned an error result"):
        provider.query(KnowledgeQuery(text="q"))


# ---------------------------------------------------------------------------
# API routes — GET is read-only, POST is the explicit user-triggered enrichment call
# ---------------------------------------------------------------------------


def test_get_guidance_empty_before_any_fetch(client):
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
    try:
        with get_session_factory()() as session:
            app_id = _make_application(session, asmnt_id, "Order Management", "Handles order validation.")

        resp = client.get(f"/assessments/{asmnt_id}/sap-knowledge/applications/{app_id}")
        assert resp.status_code == 200
        assert resp.json()["references"] == []
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_post_guidance_persists_and_get_reflects(client, monkeypatch):
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
    try:
        with get_session_factory()() as session:
            app_id = _make_application(session, asmnt_id, "Order Management", "Handles order validation.")

        fake_provider = _FakeKnowledgeProvider("sap_docs_mcp")
        monkeypatch.setattr("api.routes.sap_knowledge.get_knowledge_providers", lambda settings: [fake_provider])

        post_resp = client.post(f"/assessments/{asmnt_id}/sap-knowledge/applications/{app_id}")
        assert post_resp.status_code == 200
        body = post_resp.json()
        assert body["target_type"] == "APPLICATION"
        assert len(body["references"]) == 1
        assert body["references"][0]["provider"] == "sap_docs_mcp"
        assert body["references"][0]["reused"] is False

        get_resp = client.get(f"/assessments/{asmnt_id}/sap-knowledge/applications/{app_id}")
        assert get_resp.json()["references"] == body["references"]
        assert fake_provider.call_count == 1
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_post_guidance_unknown_target_kind_returns_404(client):
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
    try:
        resp = client.post(f"/assessments/{asmnt_id}/sap-knowledge/atc-findings/1")
        assert resp.status_code == 404
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_post_guidance_missing_target_returns_404(client, monkeypatch):
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
    try:
        monkeypatch.setattr("api.routes.sap_knowledge.get_knowledge_providers", lambda settings: [])
        resp = client.post(f"/assessments/{asmnt_id}/sap-knowledge/applications/999999")
        assert resp.status_code == 404
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)
