"""SPRINT-09 — AI Object Understanding: provider abstraction, registry, chunking, and
domain-validator unit tests (ADR-006/ADR-012). No live provider credentials required —
Bedrock/Azure AI Foundry adapters are exercised against mocked SDK/HTTP layers only; the
separate live Bedrock smoke test is documented in SESSION_HANDOFF.md.
"""
from __future__ import annotations

import pytest
from botocore.exceptions import ClientError

from ai import chunking, registry
from ai.object_understanding.evidence_package import EvidenceItem, ObjectEvidencePackage
from ai.object_understanding.schema import ObjectUnderstandingResult, ObjectUnderstandingStatus, validate_result
from ai.provider import AIProviderError, StructuredCompletionRequest
from ai.providers import get_provider
from ai.providers.azure_foundry import AzureFoundryProvider
from ai.providers.bedrock import BedrockProvider
from settings import Settings

# ---------------------------------------------------------------------------
# Provider registry (ai.providers.get_provider)
# ---------------------------------------------------------------------------


def test_get_provider_bedrock_default(monkeypatch):
    monkeypatch.setattr("ai.providers.bedrock.boto3.client", lambda *a, **k: object())
    settings = Settings(llm_provider="bedrock", bedrock_model_id="m1", aws_region="us-east-1")
    provider = get_provider(settings)
    assert isinstance(provider, BedrockProvider)
    assert provider.model_id == "m1"


def test_get_provider_azure_requires_configuration():
    settings = Settings(llm_provider="azure_foundry")
    with pytest.raises(ValueError, match="not configured"):
        get_provider(settings)


def test_get_provider_azure_configured():
    settings = Settings(
        llm_provider="azure_foundry",
        azure_foundry_endpoint="https://example.com",
        azure_foundry_api_key="key",
        azure_foundry_deployment="dep1",
    )
    provider = get_provider(settings)
    assert isinstance(provider, AzureFoundryProvider)
    assert provider.model_id == "dep1"


def test_get_provider_unknown_name_raises():
    settings = Settings()
    with pytest.raises(ValueError, match="Unknown llm_provider"):
        get_provider(settings, name="something_else")


# ---------------------------------------------------------------------------
# BedrockProvider.complete_structured — mocked boto3 Converse API
# ---------------------------------------------------------------------------


class _FakeBedrockClient:
    def __init__(self, response):
        self._response = response
        self.last_kwargs: dict | None = None

    def converse(self, **kwargs):
        self.last_kwargs = kwargs
        return self._response


def test_bedrock_provider_extracts_forced_tool_use(monkeypatch):
    fake_response = {
        "output": {"message": {"content": [{"toolUse": {"name": "my_schema", "input": {"claim": "x"}}}]}},
        "stopReason": "tool_use",
    }
    fake_client = _FakeBedrockClient(fake_response)
    monkeypatch.setattr("ai.providers.bedrock.boto3.client", lambda *a, **k: fake_client)

    provider = BedrockProvider(model_id="m1", region="us-east-1")
    result = provider.complete_structured(
        StructuredCompletionRequest(
            system_prompt="sys", user_prompt="usr", json_schema={"type": "object"}, schema_name="my_schema"
        )
    )
    assert result.output == {"claim": "x"}
    assert result.provider == "bedrock"
    assert result.model_id == "m1"
    assert fake_client.last_kwargs["toolConfig"]["toolChoice"] == {"tool": {"name": "my_schema"}}


def test_bedrock_provider_missing_tool_use_raises(monkeypatch):
    fake_client = _FakeBedrockClient({"output": {"message": {"content": []}}, "stopReason": "end_turn"})
    monkeypatch.setattr("ai.providers.bedrock.boto3.client", lambda *a, **k: fake_client)

    provider = BedrockProvider(model_id="m1", region="us-east-1")
    with pytest.raises(AIProviderError, match="no 'my_schema'"):
        provider.complete_structured(
            StructuredCompletionRequest(
                system_prompt="sys", user_prompt="usr", json_schema={"type": "object"}, schema_name="my_schema"
            )
        )


def test_bedrock_provider_wraps_boto_errors(monkeypatch):
    class _RaisingClient:
        def converse(self, **kwargs):
            raise ClientError({"Error": {"Code": "X", "Message": "boom"}}, "Converse")

    monkeypatch.setattr("ai.providers.bedrock.boto3.client", lambda *a, **k: _RaisingClient())
    provider = BedrockProvider(model_id="m1", region="us-east-1")
    with pytest.raises(AIProviderError, match="Bedrock invocation failed"):
        provider.complete_structured(
            StructuredCompletionRequest(system_prompt="s", user_prompt="u", json_schema={}, schema_name="s1")
        )


# ---------------------------------------------------------------------------
# AzureFoundryProvider.complete_structured — mocked HTTP layer
# ---------------------------------------------------------------------------


class _FakeHTTPResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


def test_azure_foundry_provider_parses_message_content(monkeypatch):
    payload = {"choices": [{"message": {"content": '{"claim": "y"}'}, "finish_reason": "stop"}]}
    monkeypatch.setattr("ai.providers.azure_foundry.httpx.post", lambda *a, **k: _FakeHTTPResponse(payload))

    provider = AzureFoundryProvider(endpoint="https://ex.com", api_key="k", deployment="dep1")
    result = provider.complete_structured(
        StructuredCompletionRequest(system_prompt="s", user_prompt="u", json_schema={}, schema_name="schema1")
    )
    assert result.output == {"claim": "y"}
    assert result.provider == "azure_foundry"
    assert result.stop_reason == "stop"


def test_azure_foundry_provider_no_choices_raises(monkeypatch):
    monkeypatch.setattr("ai.providers.azure_foundry.httpx.post", lambda *a, **k: _FakeHTTPResponse({"choices": []}))
    provider = AzureFoundryProvider(endpoint="https://ex.com", api_key="k", deployment="dep1")
    with pytest.raises(AIProviderError, match="no parseable"):
        provider.complete_structured(
            StructuredCompletionRequest(system_prompt="s", user_prompt="u", json_schema={}, schema_name="schema1")
        )


# ---------------------------------------------------------------------------
# chunk_source — structural ABAP chunking (ai.chunking, CAP-007)
# ---------------------------------------------------------------------------


def test_chunk_source_returns_single_chunk_when_under_budget():
    content = "REPORT za.\nWRITE 'hi'."
    assert chunking.chunk_source(content) == [content]


def test_chunk_source_splits_on_method_boundaries_when_over_budget():
    method = "METHOD do_something.\n" + ("  x = x + 1.\n" * 200) + "ENDMETHOD.\n"
    content = method * 3

    chunks = chunking.chunk_source(content, max_chunk_chars=1000)

    assert len(chunks) > 1
    assert "".join(chunks) == content
    for chunk in chunks[:-1]:
        assert chunk.rstrip().upper().endswith("ENDMETHOD.")


def test_chunk_source_falls_back_to_one_chunk_without_boundaries():
    content = "X" * 10
    assert chunking.chunk_source(content, max_chunk_chars=5) == [content]


# ---------------------------------------------------------------------------
# Versioned prompt/schema registry (ai.registry, CAP-004)
# ---------------------------------------------------------------------------


def test_registry_register_and_resolve_latest():
    registry.register(
        registry.PromptSchemaVersion(capability="test_capability", version="v1", system_prompt="p1", json_schema={}, schema_name="s1")
    )
    registry.register(
        registry.PromptSchemaVersion(capability="test_capability", version="v2", system_prompt="p2", json_schema={}, schema_name="s2")
    )

    assert registry.latest_version("test_capability") == "v2"
    assert registry.get_version("test_capability").version == "v2"
    assert registry.get_version("test_capability", "v1").version == "v1"


def test_registry_unknown_capability_raises():
    with pytest.raises(KeyError):
        registry.get_version("no_such_capability")


def test_registry_unknown_version_raises():
    registry.register(
        registry.PromptSchemaVersion(capability="test_capability_2", version="v1", system_prompt="p", json_schema={}, schema_name="s")
    )
    with pytest.raises(KeyError):
        registry.get_version("test_capability_2", "v99")


# ---------------------------------------------------------------------------
# ObjectUnderstandingResult domain validators (ai.object_understanding.schema, CAP-005)
# ---------------------------------------------------------------------------


def _package() -> ObjectEvidencePackage:
    return ObjectEvidencePackage(
        object_id=1,
        object_type="report",
        object_name="ZA",
        description="",
        code_excerpt_chunks=["code"],
        code_truncated=False,
        code_item=EvidenceItem(ref_id="SRC-1", source_type="SOURCE_CODE", entity_id=1, summary="s"),
        atc_items=[],
        supplemental_items=[],
    )


def test_validate_result_completed_requires_evidence_refs():
    result = ObjectUnderstandingResult(
        status=ObjectUnderstandingStatus.COMPLETED, functional_purpose="does x", technical_purpose="",
        concepts=[], confidence=0.9, rationale="r", evidence_refs=[],
    )
    errors = validate_result(result, _package())
    assert any("requires at least one evidence_refs" in e for e in errors)


def test_validate_result_completed_requires_purpose_text():
    result = ObjectUnderstandingResult(
        status=ObjectUnderstandingStatus.COMPLETED, functional_purpose="", technical_purpose="",
        concepts=[], confidence=0.9, rationale="r", evidence_refs=["SRC-1"],
    )
    errors = validate_result(result, _package())
    assert any("requires at least one of functional_purpose" in e for e in errors)


def test_validate_result_insufficient_context_must_not_assert_purpose():
    result = ObjectUnderstandingResult(
        status=ObjectUnderstandingStatus.INSUFFICIENT_CONTEXT, functional_purpose="guessed anyway",
        technical_purpose="", concepts=[], confidence=0.1, rationale="r", evidence_refs=[],
    )
    errors = validate_result(result, _package())
    assert any("must not assert" in e for e in errors)


def test_validate_result_rejects_unknown_evidence_refs():
    result = ObjectUnderstandingResult(
        status=ObjectUnderstandingStatus.COMPLETED, functional_purpose="p", technical_purpose="",
        concepts=[], confidence=0.9, rationale="r", evidence_refs=["SRC-999"],
    )
    errors = validate_result(result, _package())
    assert any("not present in the evidence package" in e for e in errors)


def test_validate_result_valid_completed_has_no_errors():
    result = ObjectUnderstandingResult(
        status=ObjectUnderstandingStatus.COMPLETED, functional_purpose="p", technical_purpose="",
        concepts=[], confidence=0.9, rationale="r", evidence_refs=["SRC-1"],
    )
    assert validate_result(result, _package()) == []
