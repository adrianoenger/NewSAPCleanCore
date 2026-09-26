"""SPRINT-10 — Business Rule Discovery: durable pipeline stage integration (CAP-003/CAP-004)
and API (CAP-005). `business_rule_discovery` registers as a 5th stage of the existing
`source_processing` PipelineRun, after `object_understanding` — these tests exercise it end to
end through `run_pipeline`, with a fake `AIProvider` swapped in via monkeypatch so no live
Bedrock/Azure credentials are needed. Mirrors test_object_understanding_pipeline.py's pattern.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from sqlalchemy import select, text

from ai.provider import AIProviderError, StructuredCompletionResult
from persistence.database import get_session_factory
from persistence.models import (
    Assessment,
    AssessmentStatus,
    BusinessRule,
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
# This file exercises business_rule_discovery only; application_discovery now runs as the next
# stage in the same pipeline (SPRINT-11) and needs *some* schema-valid response to let the run
# reach "completed" — an INSUFFICIENT_CONTEXT stub (no evidence_refs required) is a safe default
# regardless of which SAPObject ids these tests happen to create.
_APPLICATION_DISCOVERY_SCHEMA = "application_discovery_result"
_INSUFFICIENT_APPLICATION_OUTPUT = {
    "status": "INSUFFICIENT_CONTEXT",
    "name": "",
    "description": "",
    "domain": "",
    "confidence": 0.2,
    "rationale": "Not enough grouped evidence.",
    "evidence_refs": [],
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


def _rule_output(condition: str = "order value exceeds credit limit", action: str = "reject the posting") -> dict:
    return {
        "status": "COMPLETED",
        "rules": [
            {
                "rule_type": "VALIDATION",
                "condition": condition,
                "action": action,
                "confidence": 0.85,
                "rationale": "Grounded in source.",
                "evidence_refs": ["SRC-1"],
            }
        ],
    }


def _make_assessment(session) -> int:
    c = Client(name="Sprint10 Test Client")
    session.add(c)
    session.flush()
    a = Assessment(client_id=c.id, name="Sprint10 Test", status=AssessmentStatus.CREATED.value)
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
    """Returns a canned output/error per `schema_name` — object_understanding must complete
    before business_rule_discovery is even attempted for an object, so a single fixed output
    (as `_FakeProvider` uses in test_object_understanding_pipeline.py) is not enough here."""

    name = "fake"
    model_id = "fake-model-1"

    def __init__(self, outputs: dict[str, dict] | None = None, errors: dict[str, Exception] | None = None):
        self._outputs = {_APPLICATION_DISCOVERY_SCHEMA: _INSUFFICIENT_APPLICATION_OUTPUT, **(outputs or {})}
        self._errors = errors or {}

    def complete_structured(self, request):
        if request.schema_name in self._errors:
            raise self._errors[request.schema_name]
        return StructuredCompletionResult(
            output=self._outputs[request.schema_name],
            provider=self.name,
            model_id=self.model_id,
            raw_response={},
            stop_reason="tool_use",
        )


def _run_full_pipeline(monkeypatch, asmnt_id: int, tmp: str, fake_provider: _SequencedFakeProvider) -> int:
    settings = get_settings()
    monkeypatch.setattr("pipeline.stages.get_provider", lambda settings: fake_provider)
    with get_session_factory()() as session:
        run = create_pipeline_run(session, asmnt_id, tmp)
        run_id = run.id
    run_pipeline(run_id, settings.database_url)
    return run_id


def _business_rule_stage(session, run_id: int) -> StageRun:
    return session.scalars(
        select(StageRun).where(StageRun.pipeline_run_id == run_id, StageRun.stage_key == "business_rule_discovery")
    ).first()


def test_business_rule_discovery_completed_result_persisted(monkeypatch) -> None:
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
                    _BUSINESS_RULE_SCHEMA: _rule_output(),
                }
            )
            run_id = _run_full_pipeline(monkeypatch, asmnt_id, tmp, fake)

            with get_session_factory()() as session:
                run = session.get(PipelineRun, run_id)
                assert run.status == "completed"
                stage = _business_rule_stage(session, run_id)
                assert stage.status == "completed"

                obj = session.scalars(select(SAPObject).where(SAPObject.assessment_id == asmnt_id)).first()
                rules = list(session.scalars(select(BusinessRule).where(BusinessRule.sap_object_id == obj.id)))
                assert len(rules) == 1
                rule = rules[0]
                assert rule.status == "CANDIDATE"
                assert rule.rule_type == "VALIDATION"
                assert rule.condition == "order value exceeds credit limit"
                assert rule.action == "reject the posting"
                assert rule.provider == "fake"
                assert rule.prompt_capability == "business_rule_discovery"
                assert rule.evidence_refs == [
                    {"ref_id": "SRC-1", "source_type": "SOURCE_CODE", "entity_id": obj.source_file_id}
                ]
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_business_rule_discovery_zero_rules_is_a_valid_outcome(monkeypatch) -> None:
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
                    _BUSINESS_RULE_SCHEMA: {"status": "COMPLETED", "rules": []},
                }
            )
            run_id = _run_full_pipeline(monkeypatch, asmnt_id, tmp, fake)

            with get_session_factory()() as session:
                run = session.get(PipelineRun, run_id)
                assert run.status == "completed"
                stage = _business_rule_stage(session, run_id)
                assert stage.status == "completed"
                assert stage.failed_items == 0

                obj = session.scalars(select(SAPObject).where(SAPObject.assessment_id == asmnt_id)).first()
                rules = list(session.scalars(select(BusinessRule).where(BusinessRule.sap_object_id == obj.id)))
                assert rules == []
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_business_rule_discovery_provider_error_leaves_prior_rows_and_stage_completed(monkeypatch) -> None:
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            (Path(tmp) / "a.abap").write_text("REPORT za.")

            fake1 = _SequencedFakeProvider(
                outputs={_OBJECT_UNDERSTANDING_SCHEMA: _COMPLETED_UNDERSTANDING_OUTPUT, _BUSINESS_RULE_SCHEMA: _rule_output()}
            )
            _run_full_pipeline(monkeypatch, asmnt_id, tmp, fake1)

            with get_session_factory()() as session:
                obj = session.scalars(select(SAPObject).where(SAPObject.assessment_id == asmnt_id)).first()
                first_rule_id = session.scalars(
                    select(BusinessRule).where(BusinessRule.sap_object_id == obj.id)
                ).first().id

            fake2 = _SequencedFakeProvider(
                outputs={_OBJECT_UNDERSTANDING_SCHEMA: _COMPLETED_UNDERSTANDING_OUTPUT},
                errors={_BUSINESS_RULE_SCHEMA: AIProviderError("provider unavailable")},
            )
            run_id2 = _run_full_pipeline(monkeypatch, asmnt_id, tmp, fake2)

            with get_session_factory()() as session:
                run = session.get(PipelineRun, run_id2)
                assert run.status == "completed"  # a per-object AI failure is not a pipeline failure
                stage = _business_rule_stage(session, run_id2)
                assert stage.status == "completed"
                assert stage.failed_items == 0

                item = session.scalars(
                    select(WorkItem).where(WorkItem.stage_run_id == stage.id, WorkItem.item_key == str(obj.id))
                ).first()
                assert "provider unavailable" in item.last_error

                rules = list(session.scalars(select(BusinessRule).where(BusinessRule.sap_object_id == obj.id)))
                assert [r.id for r in rules] == [first_rule_id]  # untouched by the failed attempt
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_business_rule_discovery_domain_validation_failure_not_persisted(monkeypatch) -> None:
    """A schema-valid but domain-invalid response (unknown evidence_refs) must never be
    persisted — ADR-012 validates evidence references before persistence."""
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            (Path(tmp) / "a.abap").write_text("REPORT za.")

            bad_output = {
                "status": "COMPLETED",
                "rules": [
                    {
                        "rule_type": "VALIDATION",
                        "condition": "invented condition",
                        "action": "invented action",
                        "confidence": 0.9,
                        "rationale": "made up",
                        "evidence_refs": ["SRC-999"],
                    }
                ],
            }
            fake = _SequencedFakeProvider(
                outputs={_OBJECT_UNDERSTANDING_SCHEMA: _COMPLETED_UNDERSTANDING_OUTPUT, _BUSINESS_RULE_SCHEMA: bad_output}
            )
            run_id = _run_full_pipeline(monkeypatch, asmnt_id, tmp, fake)

            with get_session_factory()() as session:
                run = session.get(PipelineRun, run_id)
                assert run.status == "completed"
                stage = _business_rule_stage(session, run_id)
                assert stage.failed_items == 0

                obj = session.scalars(select(SAPObject).where(SAPObject.assessment_id == asmnt_id)).first()
                item = session.scalars(
                    select(WorkItem).where(WorkItem.stage_run_id == stage.id, WorkItem.item_key == str(obj.id))
                ).first()
                assert "Domain validation failed" in item.last_error

                rules = list(session.scalars(select(BusinessRule).where(BusinessRule.sap_object_id == obj.id)))
                assert rules == []
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_business_rule_discovery_reprocessing_replaces_non_validated_candidates(monkeypatch) -> None:
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            (Path(tmp) / "a.abap").write_text("REPORT za.")

            fake1 = _SequencedFakeProvider(
                outputs={
                    _OBJECT_UNDERSTANDING_SCHEMA: _COMPLETED_UNDERSTANDING_OUTPUT,
                    _BUSINESS_RULE_SCHEMA: _rule_output(condition="first condition", action="first action"),
                }
            )
            _run_full_pipeline(monkeypatch, asmnt_id, tmp, fake1)

            fake2 = _SequencedFakeProvider(
                outputs={
                    _OBJECT_UNDERSTANDING_SCHEMA: _COMPLETED_UNDERSTANDING_OUTPUT,
                    _BUSINESS_RULE_SCHEMA: _rule_output(condition="second condition", action="second action"),
                }
            )
            _run_full_pipeline(monkeypatch, asmnt_id, tmp, fake2)

            with get_session_factory()() as session:
                obj = session.scalars(select(SAPObject).where(SAPObject.assessment_id == asmnt_id)).first()
                rules = list(session.scalars(select(BusinessRule).where(BusinessRule.sap_object_id == obj.id)))
                assert len(rules) == 1
                assert rules[0].condition == "second condition"
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_business_rule_discovery_consolidation_merges_duplicates_across_objects(monkeypatch) -> None:
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            (Path(tmp) / "a.abap").write_text("REPORT za.")
            (Path(tmp) / "b.abap").write_text("REPORT zb.")

            fake = _SequencedFakeProvider(
                outputs={_OBJECT_UNDERSTANDING_SCHEMA: _COMPLETED_UNDERSTANDING_OUTPUT, _BUSINESS_RULE_SCHEMA: _rule_output()}
            )
            run_id = _run_full_pipeline(monkeypatch, asmnt_id, tmp, fake)

            with get_session_factory()() as session:
                run = session.get(PipelineRun, run_id)
                assert run.status == "completed"

                objs = list(session.scalars(select(SAPObject).where(SAPObject.assessment_id == asmnt_id)))
                assert len(objs) == 2

                all_rules = list(session.scalars(select(BusinessRule).where(BusinessRule.assessment_id == asmnt_id)))
                assert len(all_rules) == 2

                candidates = [r for r in all_rules if r.status == "CANDIDATE"]
                merged = [r for r in all_rules if r.status == "MERGED"]
                assert len(candidates) == 1
                assert len(merged) == 1
                assert merged[0].consolidated_into_id == candidates[0].id

                # The survivor's evidence keeps both objects' distinct SRC-1 (ref_id is only
                # unique within one object's own evidence package, not across objects).
                entity_ids = {ref["entity_id"] for ref in candidates[0].evidence_refs}
                assert entity_ids == {o.source_file_id for o in objs}
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_business_rule_discovery_user_validated_row_survives_reprocessing_and_wins_consolidation(monkeypatch) -> None:
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            (Path(tmp) / "a.abap").write_text("REPORT za.")

            fake1 = _SequencedFakeProvider(
                outputs={_OBJECT_UNDERSTANDING_SCHEMA: _COMPLETED_UNDERSTANDING_OUTPUT, _BUSINESS_RULE_SCHEMA: _rule_output()}
            )
            _run_full_pipeline(monkeypatch, asmnt_id, tmp, fake1)

            with get_session_factory()() as session:
                rule = session.scalars(select(BusinessRule).where(BusinessRule.assessment_id == asmnt_id)).first()
                rule.user_validated = True
                rule.user_notes = "Confirmed by the functional analyst."
                validated_id = rule.id
                session.commit()

            # Reprocessing regenerates the same exact rule text — a duplicate of the now
            # user-validated row. It must never be deleted by process_item, and consolidation
            # must prefer it as the merge survivor.
            fake2 = _SequencedFakeProvider(
                outputs={_OBJECT_UNDERSTANDING_SCHEMA: _COMPLETED_UNDERSTANDING_OUTPUT, _BUSINESS_RULE_SCHEMA: _rule_output()}
            )
            _run_full_pipeline(monkeypatch, asmnt_id, tmp, fake2)

            with get_session_factory()() as session:
                all_rules = list(session.scalars(select(BusinessRule).where(BusinessRule.assessment_id == asmnt_id)))
                assert len(all_rules) == 2

                validated = session.get(BusinessRule, validated_id)
                assert validated.status == "CANDIDATE"  # never relabeled MERGED
                assert validated.user_validated is True
                assert validated.user_notes == "Confirmed by the functional analyst."

                other = [r for r in all_rules if r.id != validated_id][0]
                assert other.status == "MERGED"
                assert other.consolidated_into_id == validated_id
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_list_business_rules_api_excludes_merged_by_default(client, monkeypatch) -> None:
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            (Path(tmp) / "a.abap").write_text("REPORT za.")
            (Path(tmp) / "b.abap").write_text("REPORT zb.")

            fake = _SequencedFakeProvider(
                outputs={_OBJECT_UNDERSTANDING_SCHEMA: _COMPLETED_UNDERSTANDING_OUTPUT, _BUSINESS_RULE_SCHEMA: _rule_output()}
            )
            _run_full_pipeline(monkeypatch, asmnt_id, tmp, fake)

            resp = client.get(f"/assessments/{asmnt_id}/business-rules")
            assert resp.status_code == 200
            body = resp.json()
            assert body["total"] == 1
            assert body["rules"][0]["status"] == "CANDIDATE"

            resp_all = client.get(f"/assessments/{asmnt_id}/business-rules?include_merged=true")
            assert resp_all.json()["total"] == 2
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_validate_business_rule_api_sets_flags_and_survives_reprocessing(client, monkeypatch) -> None:
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            (Path(tmp) / "a.abap").write_text("REPORT za.")

            fake = _SequencedFakeProvider(
                outputs={_OBJECT_UNDERSTANDING_SCHEMA: _COMPLETED_UNDERSTANDING_OUTPUT, _BUSINESS_RULE_SCHEMA: _rule_output()}
            )
            _run_full_pipeline(monkeypatch, asmnt_id, tmp, fake)

            with get_session_factory()() as session:
                rule_id = session.scalars(select(BusinessRule).where(BusinessRule.assessment_id == asmnt_id)).first().id

            resp = client.patch(
                f"/assessments/{asmnt_id}/business-rules/{rule_id}/validate",
                json={"user_validated": True, "user_notes": "Looks right."},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["user_validated"] is True
            assert body["user_notes"] == "Looks right."
            assert body["user_validated_at"] is not None

            resp2 = client.patch(
                f"/assessments/{asmnt_id}/business-rules/{rule_id}/validate",
                json={"user_validated": False},
            )
            assert resp2.json()["user_validated_at"] is None
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)
