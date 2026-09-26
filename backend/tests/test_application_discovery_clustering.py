"""SPRINT-11 — Application Discovery: deterministic clustering unit tests (CAP-001).

Exercises `ai.application_discovery.clustering.build_candidate_clusters` directly against real
fixtures (no AI provider involved) — dependency, shared_package and shared_concept signals, plus
the "no signal -> singleton cluster" default.
"""
from __future__ import annotations

from sqlalchemy import text

from ai.application_discovery.clustering import build_candidate_clusters
from persistence.database import get_session_factory
from persistence.models import (
    ATCFinding,
    ATCRun,
    Assessment,
    AssessmentStatus,
    Client,
    ObjectUnderstanding,
    ObjectUnderstandingStatus,
    SAPObject,
    SAPObjectDependency,
    SourceFile,
    SourceScan,
)


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


def _make_scan(session, assessment_id: int) -> int:
    scan = SourceScan(assessment_id=assessment_id, source_path="/tmp/fixture", status="completed")
    session.add(scan)
    session.flush()
    return scan.id


def _make_object(session, assessment_id: int, scan_id: int, object_type: str, object_name: str) -> SAPObject:
    source_file = SourceFile(
        scan_id=scan_id,
        assessment_id=assessment_id,
        rel_path=f"{object_name}.abap",
        size_bytes=10,
        mtime=0.0,
        sha256="0" * 64,
        category="abap",
    )
    session.add(source_file)
    session.flush()
    obj = SAPObject(
        assessment_id=assessment_id,
        source_file_id=source_file.id,
        object_type=object_type,
        object_name=object_name,
        canonical_key=f"{object_type.upper()}::{object_name.upper()}",
    )
    session.add(obj)
    session.flush()
    return obj


def test_no_signal_yields_singleton_clusters():
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
    try:
        with get_session_factory()() as session:
            scan_id = _make_scan(session, asmnt_id)
            a = _make_object(session, asmnt_id, scan_id, "report", "ZA")
            b = _make_object(session, asmnt_id, scan_id, "report", "ZB")
            session.commit()

            clusters = build_candidate_clusters(session, asmnt_id, scan_id)
            assert {tuple(c.object_ids) for c in clusters} == {(a.id,), (b.id,)}
            assert all(c.signals == [] for c in clusters)
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_dependency_signal_groups_connected_objects():
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
    try:
        with get_session_factory()() as session:
            scan_id = _make_scan(session, asmnt_id)
            caller = _make_object(session, asmnt_id, scan_id, "program", "ZA")
            callee = _make_object(session, asmnt_id, scan_id, "function_module", "Z_DO_THING")
            unrelated = _make_object(session, asmnt_id, scan_id, "report", "ZC")
            session.add(
                SAPObjectDependency(
                    assessment_id=asmnt_id,
                    source_object_id=caller.id,
                    target_name="Z_DO_THING",
                    target_type="function_module",
                    dep_type="CALL_FUNCTION",
                    confidence="CERTAIN",
                )
            )
            session.commit()

            clusters = build_candidate_clusters(session, asmnt_id, scan_id)
            by_members = {frozenset(c.object_ids): c for c in clusters}
            assert frozenset({caller.id, callee.id}) in by_members
            assert frozenset({unrelated.id}) in by_members
            grouped = by_members[frozenset({caller.id, callee.id})]
            assert any(s.signal_type == "dependency" for s in grouped.signals)
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_shared_package_signal_via_atc_finding_groups_objects_without_dependency():
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
    try:
        with get_session_factory()() as session:
            scan_id = _make_scan(session, asmnt_id)
            a = _make_object(session, asmnt_id, scan_id, "report", "ZA")
            b = _make_object(session, asmnt_id, scan_id, "report", "ZB")
            run = ATCRun(assessment_id=asmnt_id, source_filename="atc.xlsx")
            session.add(run)
            session.flush()
            for obj in (a, b):
                session.add(
                    ATCFinding(
                        atc_run_id=run.id,
                        assessment_id=asmnt_id,
                        source_row_number=1,
                        raw_payload={},
                        package_name_raw="ZPKG_SALES",
                        correlated_object_id=obj.id,
                    )
                )
            session.commit()

            clusters = build_candidate_clusters(session, asmnt_id, scan_id)
            assert {a.id, b.id} in [set(c.object_ids) for c in clusters]
            grouped = next(c for c in clusters if set(c.object_ids) == {a.id, b.id})
            assert any(s.signal_type == "shared_package" for s in grouped.signals)
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_shared_concept_signal_groups_a_minority_but_not_a_majority():
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
    try:
        with get_session_factory()() as session:
            scan_id = _make_scan(session, asmnt_id)
            objs = [_make_object(session, asmnt_id, scan_id, "report", f"Z{i}") for i in range(4)]
            # "pricing" shared by exactly 2 of 4 objects (50%, at the threshold) -> distinguishing.
            # "abap" shared by all 4 objects (100%) -> too generic, ignored. One ObjectUnderstanding
            # row per object (unique per sap_object_id) carries both concepts where applicable.
            for i, obj in enumerate(objs):
                concepts = ["abap", "pricing"] if i < 2 else ["abap"]
                session.add(
                    ObjectUnderstanding(
                        assessment_id=asmnt_id,
                        sap_object_id=obj.id,
                        status=ObjectUnderstandingStatus.COMPLETED.value,
                        concepts=concepts,
                        confidence=0.8,
                        provider="fake",
                        model_id="fake-model",
                        prompt_capability="object_understanding",
                        prompt_version="v1",
                    )
                )
            session.commit()
        with get_session_factory()() as session:
            objs_by_key = {
                obj.object_name: obj.id
                for obj in session.query(SAPObject).filter(SAPObject.assessment_id == asmnt_id)
            }
            clusters = build_candidate_clusters(session, asmnt_id, scan_id)
            member_sets = [set(c.object_ids) for c in clusters]
            assert {objs_by_key["Z0"], objs_by_key["Z1"]} in member_sets
            assert {objs_by_key["Z2"]} in member_sets
            assert {objs_by_key["Z3"]} in member_sets
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)
