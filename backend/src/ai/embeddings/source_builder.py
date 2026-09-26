"""Embeddable source-text/metadata builder (Baseline core rule 14, ADR-004/ADR-008/ADR-017).

Collects the meaningful semantic entities of one Assessment and renders each into a short,
human-readable text plus a metadata dict usable as a search filter. Deliberately narrow in scope
(matches SPRINT-14's stated demonstrable outcome exactly — "rules/applications/objects/process
evidence"):

- ``SAP_OBJECT``: only objects with a `COMPLETED` `ObjectUnderstanding` are embeddable — the raw
  ABAP source is an opaque/raw bulk payload (never embedded directly); the AI-understood
  functional/technical purpose plus concepts is the meaningful semantic text.
- ``APPLICATION``: name/description/domain of every non-`MERGED` Application.
- ``BUSINESS_RULE``: condition/action of every `CANDIDATE` (non-`MERGED`) BusinessRule.
- ``EVIDENCE_RECORD``: quality-gated process/usage/user/role supplemental signals only — the same
  `MATCHED_EXACT`/`MATCHED_HEURISTIC`-correlated, business-capability-tagged pool
  `ai.clean_core_analysis.evidence_package` already trusts as business evidence. Never a raw bulk
  payload; only the already-normalized payload's short summary.

CleanCoreAssessment conclusions are intentionally not embedded here — not named in the sprint's
demonstrable outcome (rules/applications/objects/process evidence), so adding them would be scope
creep beyond what was planned.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.models import (
    Application,
    ApplicationStatus,
    BusinessRule,
    BusinessRuleStatus,
    EvidenceCorrelation,
    EvidenceCorrelationStatus,
    EvidenceDataset,
    EvidenceRecord,
    ObjectUnderstanding,
    ObjectUnderstandingStatus,
    SAPObject,
    SemanticEntityType,
)

_TARGET_SAP_OBJECT = "SAP_OBJECT"
_MATCHED_STATUSES = (EvidenceCorrelationStatus.MATCHED_EXACT.value, EvidenceCorrelationStatus.MATCHED_HEURISTIC.value)
_BUSINESS_CAPABILITIES = {
    "USAGE_SIGNAL",
    "PROCESS_KPI",
    "BUSINESS_PROCESS_SIGNAL",
    "USER_SIGNAL",
    "ROLE_SIGNAL",
    "AUTHORIZATION_SIGNAL",
}


@dataclass(frozen=True)
class EmbeddableEntity:
    entity_type: str
    entity_id: int
    content_text: str
    metadata: dict


def collect_embeddable_entities(session: Session, assessment_id: int) -> list[EmbeddableEntity]:
    entities: list[EmbeddableEntity] = [
        *_sap_object_entities(session, assessment_id),
        *_application_entities(session, assessment_id),
        *_business_rule_entities(session, assessment_id),
        *_evidence_record_entities(session, assessment_id),
    ]
    return entities


def _sap_object_entities(session: Session, assessment_id: int) -> list[EmbeddableEntity]:
    rows = session.execute(
        select(SAPObject, ObjectUnderstanding)
        .join(ObjectUnderstanding, ObjectUnderstanding.sap_object_id == SAPObject.id)
        .where(
            SAPObject.assessment_id == assessment_id,
            ObjectUnderstanding.status == ObjectUnderstandingStatus.COMPLETED.value,
        )
    )
    entities = []
    for obj, understanding in rows:
        text = "\n".join(
            part
            for part in (
                f"{obj.object_type} {obj.object_name}",
                understanding.functional_purpose,
                understanding.technical_purpose,
                f"Concepts: {', '.join(understanding.concepts)}" if understanding.concepts else "",
            )
            if part
        )
        entities.append(
            EmbeddableEntity(
                entity_type=SemanticEntityType.SAP_OBJECT.value,
                entity_id=obj.id,
                content_text=text,
                metadata={
                    "object_type": obj.object_type,
                    "object_name": obj.object_name,
                    "application_id": obj.application_id,
                },
            )
        )
    return entities


def _application_entities(session: Session, assessment_id: int) -> list[EmbeddableEntity]:
    apps = session.scalars(
        select(Application).where(
            Application.assessment_id == assessment_id,
            Application.status != ApplicationStatus.MERGED.value,
        )
    )
    entities = []
    for app in apps:
        if not (app.name or app.description):
            continue
        text = "\n".join(
            part
            for part in (app.name, app.description, f"Domain: {app.domain}" if app.domain else "")
            if part
        )
        entities.append(
            EmbeddableEntity(
                entity_type=SemanticEntityType.APPLICATION.value,
                entity_id=app.id,
                content_text=text,
                metadata={"domain": app.domain, "status": app.status},
            )
        )
    return entities


def _business_rule_entities(session: Session, assessment_id: int) -> list[EmbeddableEntity]:
    rules = session.scalars(
        select(BusinessRule).where(
            BusinessRule.assessment_id == assessment_id,
            BusinessRule.status == BusinessRuleStatus.CANDIDATE.value,
        )
    )
    entities = []
    for rule in rules:
        text = f"{rule.rule_type}: {rule.condition} -> {rule.action}"
        entities.append(
            EmbeddableEntity(
                entity_type=SemanticEntityType.BUSINESS_RULE.value,
                entity_id=rule.id,
                content_text=text,
                metadata={"rule_type": rule.rule_type, "sap_object_id": rule.sap_object_id},
            )
        )
    return entities


def _evidence_record_entities(session: Session, assessment_id: int) -> list[EmbeddableEntity]:
    rows = session.execute(
        select(EvidenceCorrelation, EvidenceRecord, EvidenceDataset)
        .join(EvidenceRecord, EvidenceCorrelation.evidence_record_id == EvidenceRecord.id)
        .join(EvidenceDataset, EvidenceRecord.dataset_id == EvidenceDataset.id)
        .where(
            EvidenceDataset.assessment_id == assessment_id,
            EvidenceCorrelation.target_type == _TARGET_SAP_OBJECT,
            EvidenceCorrelation.status.in_(_MATCHED_STATUSES),
        )
    )
    entities = []
    seen_record_ids: set[int] = set()
    for corr, rec, dataset in rows:
        if rec.capability not in _BUSINESS_CAPABILITIES or rec.id in seen_record_ids:
            continue
        seen_record_ids.add(rec.id)
        text = f"{dataset.dataset_type} / {rec.record_type}: {_short_payload(rec.normalized_payload)}"
        entities.append(
            EmbeddableEntity(
                entity_type=SemanticEntityType.EVIDENCE_RECORD.value,
                entity_id=rec.id,
                content_text=text,
                metadata={"capability": rec.capability, "correlated_object_id": corr.target_id},
            )
        )
    return entities


def _short_payload(payload: dict) -> str:
    parts = [f"{k}={v}" for k, v in list(payload.items())[:5]]
    return ", ".join(parts)[:200]
