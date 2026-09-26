"""SPRINT-14 — Embeddings and Semantic Retrieval: durable pipeline stage integration (CAP-003)
and the source-text builder's quality gates (CAP-003) / semantic search service (CAP-004).

`embeddings` registers as an 8th stage of the existing `source_processing` pipeline, after
`clean_core_analysis` — exercised end to end through `run_pipeline`, with a fake `AIProvider` and
a counting fake `EmbeddingProvider` swapped in via monkeypatch so no live Bedrock/Azure
credentials are needed. Mirrors test_clean_core_analysis_pipeline.py's pattern.
"""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

from sqlalchemy import select, text

from ai.embedding_provider import EmbeddingResult
from ai.embeddings.search import semantic_search
from ai.embeddings.source_builder import collect_embeddable_entities
from ai.provider import StructuredCompletionResult
from persistence.database import get_session_factory
from persistence.models import (
    Assessment,
    AssessmentStatus,
    Client,
    Embedding,
    EvidenceCorrelation,
    EvidenceCorrelationStatus,
    EvidenceDataset,
    EvidenceDatasetType,
    EvidenceRecord,
    PipelineRun,
    SAPObject,
    SemanticEntityType,
    SourceFile,
    SourceScan,
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
            "condition": "order value exceeds credit limit",
            "action": "reject the posting",
            "confidence": 0.85,
            "rationale": "Grounded in source.",
            "evidence_refs": ["SRC-1"],
        }
    ],
}
_INSUFFICIENT_CLEAN_CORE_OUTPUT = {
    "status": "INSUFFICIENT_CONTEXT",
    "recommendation": "REVIEW",
    "recommendation_rationale": "Not enough evidence to determine risk or importance.",
    "confidence": 0.1,
}


def _completed_application_output_citing_first_object(request) -> dict:
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
    c = Client(name="Sprint14 Test Client")
    session.add(c)
    session.flush()
    a = Assessment(client_id=c.id, name="Sprint14 Test", status=AssessmentStatus.CREATED.value)
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
    name = "fake"
    model_id = "fake-model-1"

    def __init__(self, outputs: dict | None = None):
        self._outputs = {_CLEAN_CORE_ANALYSIS_SCHEMA: _INSUFFICIENT_CLEAN_CORE_OUTPUT, **(outputs or {})}

    def complete_structured(self, request):
        output = self._outputs[request.schema_name]
        if callable(output):
            output = output(request)
        return StructuredCompletionResult(
            output=output, provider=self.name, model_id=self.model_id, raw_response={}, stop_reason="tool_use"
        )


class _CountingFakeEmbeddingProvider:
    """Distinguishable-per-text vectors (not all-zero) so cosine ranking is meaningful, plus a
    call counter used to assert the `embeddings` stage's incrementality (content_hash) gate."""

    name = "fake"
    model_id = "fake-embed-1"
    dimensions = 1024

    def __init__(self) -> None:
        self.embed_call_count = 0

    def embed(self, request):
        self.embed_call_count += 1
        vectors = []
        for text_ in request.texts:
            seed = sum(text_.encode("utf-8")) % 1000 / 1000.0
            vectors.append([seed] * self.dimensions)
        return EmbeddingResult(vectors=vectors, provider=self.name, model_id=self.model_id, dimensions=self.dimensions)


def _run_full_pipeline(monkeypatch, asmnt_id: int, tmp: str, fake_provider, fake_embedding_provider) -> int:
    settings = get_settings()
    monkeypatch.setattr("pipeline.stages.get_provider", lambda settings: fake_provider)
    monkeypatch.setattr("pipeline.stages.get_embedding_provider", lambda settings: fake_embedding_provider)
    with get_session_factory()() as session:
        run = create_pipeline_run(session, asmnt_id, tmp)
        run_id = run.id
    run_pipeline(run_id, settings.database_url)
    return run_id


def test_embeddings_created_for_object_application_and_rule(monkeypatch) -> None:
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    settings = get_settings()
    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            (Path(tmp) / "a.abap").write_text("REPORT za.")

            fake = _SequencedFakeProvider(
                outputs={
                    _OBJECT_UNDERSTANDING_SCHEMA: _COMPLETED_UNDERSTANDING_OUTPUT,
                    _BUSINESS_RULE_SCHEMA: _ONE_RULE_OUTPUT,
                    _APPLICATION_DISCOVERY_SCHEMA: _completed_application_output_citing_first_object,
                }
            )
            fake_embeddings = _CountingFakeEmbeddingProvider()
            run_id = _run_full_pipeline(monkeypatch, asmnt_id, tmp, fake, fake_embeddings)

            with get_session_factory()() as session:
                run = session.get(PipelineRun, run_id)
                assert run.status == "completed"

                rows = list(session.scalars(select(Embedding).where(Embedding.assessment_id == asmnt_id)))
                by_type = {r.entity_type: r for r in rows}
                assert set(by_type) == {
                    SemanticEntityType.SAP_OBJECT.value,
                    SemanticEntityType.APPLICATION.value,
                    SemanticEntityType.BUSINESS_RULE.value,
                }
                assert "Validates a business condition" in by_type[SemanticEntityType.SAP_OBJECT.value].content_text
                assert "Order Management" in by_type[SemanticEntityType.APPLICATION.value].content_text
                assert "credit limit" in by_type[SemanticEntityType.BUSINESS_RULE.value].content_text
                for row in rows:
                    assert len(row.vector) == 1024
                    assert row.provider == "fake"

            assert fake_embeddings.embed_call_count == 3
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_embeddings_incrementality_skips_unchanged_content(monkeypatch) -> None:
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    settings = get_settings()
    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            (Path(tmp) / "a.abap").write_text("REPORT za.")

            fake = _SequencedFakeProvider(
                outputs={
                    _OBJECT_UNDERSTANDING_SCHEMA: _COMPLETED_UNDERSTANDING_OUTPUT,
                    _BUSINESS_RULE_SCHEMA: _ONE_RULE_OUTPUT,
                    _APPLICATION_DISCOVERY_SCHEMA: _completed_application_output_citing_first_object,
                }
            )
            fake_embeddings = _CountingFakeEmbeddingProvider()
            _run_full_pipeline(monkeypatch, asmnt_id, tmp, fake, fake_embeddings)
            assert fake_embeddings.embed_call_count == 3

            with get_session_factory()() as session:
                rows_after_run_1 = {
                    r.entity_type: r.id
                    for r in session.scalars(select(Embedding).where(Embedding.assessment_id == asmnt_id))
                }

            # A second full reprocessing run over the exact same source/outputs rebuilds identical
            # embeddable text for SAP_OBJECT/APPLICATION (both upserted in place by their own
            # stages) — the `embeddings` stage must never re-call the provider for their unchanged
            # content (pipeline-architecture.md's Incrementality principle). BUSINESS_RULE is the
            # one exception: `business_rule_discovery` deletes and recreates its rows every run
            # (see `_business_rule_discovery_process_item`), so its embedding necessarily gets a
            # new entity_id and is re-embedded — a pre-existing recreate-not-upsert design choice
            # of that stage, not a gap in this stage's own incrementality logic.
            run_id_2 = _run_full_pipeline(monkeypatch, asmnt_id, tmp, fake, fake_embeddings)

            with get_session_factory()() as session:
                run = session.get(PipelineRun, run_id_2)
                assert run.status == "completed"

                rows_after_run_2 = {
                    r.entity_type: r.id
                    for r in session.scalars(select(Embedding).where(Embedding.assessment_id == asmnt_id))
                }
                assert rows_after_run_2[SemanticEntityType.SAP_OBJECT.value] == rows_after_run_1[SemanticEntityType.SAP_OBJECT.value]
                assert rows_after_run_2[SemanticEntityType.APPLICATION.value] == rows_after_run_1[SemanticEntityType.APPLICATION.value]
                assert rows_after_run_2[SemanticEntityType.BUSINESS_RULE.value] != rows_after_run_1[SemanticEntityType.BUSINESS_RULE.value]

            assert fake_embeddings.embed_call_count == 4
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_evidence_record_entities_only_include_quality_gated_business_signals() -> None:
    """Unit-level check of `collect_embeddable_entities`'s EVIDENCE_RECORD pool: only
    `MATCHED_*`-correlated, business-capability-tagged records are embeddable — an UNMATCHED
    correlation or a technical-capability record must never appear (ADR-017 quality gate, mirrors
    `ai.clean_core_analysis.evidence_package`'s own pool split)."""
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

        scan = SourceScan(assessment_id=asmnt_id, source_path="/workspace/demo-source")
        session.add(scan)
        session.flush()
        source_file = SourceFile(
            scan_id=scan.id,
            assessment_id=asmnt_id,
            rel_path="a.abap",
            size_bytes=10,
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
            object_name="ZA",
            canonical_key="REPORT::ZA",
            description="",
            line_start=1,
            line_end=1,
        )
        session.add(obj)
        session.flush()

        dataset = EvidenceDataset(
            assessment_id=asmnt_id,
            dataset_type=EvidenceDatasetType.SIGNAVIO_PROCESS_INSIGHTS.value,
            display_name="Test Signavio Export",
            source_filename="export.json",
            source_sha256="0" * 64,
            importer_name="signavio",
        )
        session.add(dataset)
        session.flush()

        business_record = EvidenceRecord(
            dataset_id=dataset.id,
            record_type="usage_summary",
            capability="USAGE_SIGNAL",
            source_key="usage-1",
            record_fingerprint="fp-usage-1",
            normalized_payload={"executions_per_month": 42},
        )
        technical_record = EvidenceRecord(
            dataset_id=dataset.id,
            record_type="dependency_summary",
            capability="DEPENDENCY_SIGNAL",
            source_key="dep-1",
            record_fingerprint="fp-dep-1",
            normalized_payload={"calls": "ZB"},
        )
        session.add_all([business_record, technical_record])
        session.flush()

        matched_business = EvidenceCorrelation(
            evidence_record_id=business_record.id,
            target_type="SAP_OBJECT",
            target_id=obj.id,
            status=EvidenceCorrelationStatus.MATCHED_EXACT.value,
            method="exact_name",
        )
        unmatched_business = EvidenceRecord(
            dataset_id=dataset.id,
            record_type="usage_summary",
            capability="USAGE_SIGNAL",
            source_key="usage-2",
            record_fingerprint="fp-usage-2",
            normalized_payload={"executions_per_month": 1},
        )
        session.add(unmatched_business)
        session.flush()
        unmatched_corr = EvidenceCorrelation(
            evidence_record_id=unmatched_business.id,
            target_type="SAP_OBJECT",
            target_id=obj.id,
            status=EvidenceCorrelationStatus.UNMATCHED.value,
            method="none",
        )
        matched_technical = EvidenceCorrelation(
            evidence_record_id=technical_record.id,
            target_type="SAP_OBJECT",
            target_id=obj.id,
            status=EvidenceCorrelationStatus.MATCHED_EXACT.value,
            method="exact_name",
        )
        session.add_all([matched_business, unmatched_corr, matched_technical])
        session.commit()

        try:
            entities = collect_embeddable_entities(session, asmnt_id)
            evidence_entities = [e for e in entities if e.entity_type == SemanticEntityType.EVIDENCE_RECORD.value]
            assert {e.entity_id for e in evidence_entities} == {business_record.id}
            assert evidence_entities[0].metadata["capability"] == "USAGE_SIGNAL"
        finally:
            _cleanup(session, asmnt_id)


def test_semantic_search_ranks_by_cosine_similarity_and_scopes_to_assessment() -> None:
    with get_session_factory()() as session:
        asmnt_id_a = _make_assessment(session)
        asmnt_id_b = _make_assessment(session)

        close_vector = [0.9] + [0.0] * 1023
        far_vector = [0.1] + [0.0] * 1023
        other_assessment_vector = [0.95] + [0.0] * 1023

        session.add_all(
            [
                Embedding(
                    assessment_id=asmnt_id_a,
                    entity_type=SemanticEntityType.BUSINESS_RULE.value,
                    entity_id=1,
                    content_text="close match",
                    content_hash="h1",
                    entity_metadata={},
                    vector=close_vector,
                    provider="fake",
                    model_id="fake-embed-1",
                ),
                Embedding(
                    assessment_id=asmnt_id_a,
                    entity_type=SemanticEntityType.BUSINESS_RULE.value,
                    entity_id=2,
                    content_text="far match",
                    content_hash="h2",
                    entity_metadata={},
                    vector=far_vector,
                    provider="fake",
                    model_id="fake-embed-1",
                ),
                Embedding(
                    assessment_id=asmnt_id_b,
                    entity_type=SemanticEntityType.BUSINESS_RULE.value,
                    entity_id=3,
                    content_text="other assessment match",
                    content_hash="h3",
                    entity_metadata={},
                    vector=other_assessment_vector,
                    provider="fake",
                    model_id="fake-embed-1",
                ),
            ]
        )
        session.commit()

        class _QueryEmbeddingProvider:
            name = "fake"
            model_id = "fake-embed-1"
            dimensions = 1024

            def embed(self, request):
                return EmbeddingResult(
                    vectors=[[1.0] + [0.0] * 1023 for _ in request.texts],
                    provider=self.name,
                    model_id=self.model_id,
                    dimensions=self.dimensions,
                )

        try:
            hits = semantic_search(session, asmnt_id_a, "business concept", _QueryEmbeddingProvider())
            assert [h.entity_id for h in hits] == [1, 2]
            assert hits[0].score > hits[1].score
        finally:
            _cleanup(session, asmnt_id_a)
            _cleanup(session, asmnt_id_b)


def test_semantic_search_api_returns_ranked_hits_for_this_assessment_only(client, monkeypatch) -> None:
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
        session.add(
            Embedding(
                assessment_id=asmnt_id,
                entity_type=SemanticEntityType.BUSINESS_RULE.value,
                entity_id=42,
                content_text="reject postings that exceed the customer credit limit",
                content_hash="h1",
                entity_metadata={"rule_type": "VALIDATION"},
                vector=[0.9] + [0.0] * 1023,
                provider="fake",
                model_id="fake-embed-1",
            )
        )
        session.commit()

    class _QueryEmbeddingProvider:
        name = "fake"
        model_id = "fake-embed-1"
        dimensions = 1024

        def embed(self, request):
            return EmbeddingResult(
                vectors=[[1.0] + [0.0] * 1023 for _ in request.texts],
                provider=self.name,
                model_id=self.model_id,
                dimensions=self.dimensions,
            )

    monkeypatch.setattr(
        "api.routes.semantic_search.get_embedding_provider", lambda settings: _QueryEmbeddingProvider()
    )

    try:
        resp = client.get(f"/assessments/{asmnt_id}/semantic-search", params={"q": "credit limit"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["assessment_id"] == asmnt_id
        assert body["query"] == "credit limit"
        assert len(body["results"]) == 1
        assert body["results"][0]["entity_type"] == "BUSINESS_RULE"
        assert body["results"][0]["entity_id"] == 42
        assert body["results"][0]["metadata"] == {"rule_type": "VALIDATION"}

        missing_resp = client.get("/assessments/999999/semantic-search", params={"q": "credit limit"})
        assert missing_resp.status_code == 404
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)
