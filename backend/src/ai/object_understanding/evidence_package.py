"""Object evidence package builder (ADR-006/ADR-012 + Baseline "AI Processing").

Assembles a provider-agnostic package — canonical source facts, correlated ATC findings,
correlated supplemental evidence — for one SAPObject. Nothing here ever imports a provider SDK;
`render_prompt` turns the package into plain text handed to any `AIProvider`.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai.chunking import chunk_source
from persistence.models import (
    ATCFinding,
    EvidenceCorrelation,
    EvidenceCorrelationStatus,
    EvidenceDataset,
    EvidenceRecord,
    SAPObject,
    SourceFile,
    SourceScan,
)

_TARGET_SAP_OBJECT = "SAP_OBJECT"
_MATCHED_STATUSES = (EvidenceCorrelationStatus.MATCHED_EXACT.value, EvidenceCorrelationStatus.MATCHED_HEURISTIC.value)

# Bounds how much ABAP source text is sent per completion — large objects are chunked
# (ai.chunking) and only as many whole chunks as fit this budget are included.
MAX_CODE_EXCERPT_CHARS = 12000


@dataclass(frozen=True)
class EvidenceItem:
    """One citable piece of evidence; `ref_id` is what the model must echo back in
    `ObjectUnderstandingResult.evidence_refs` to prove a claim is evidence-bound."""

    ref_id: str
    source_type: str  # "ATC_FINDING" | "SUPPLEMENTAL_EVIDENCE"
    entity_id: int
    summary: str


@dataclass(frozen=True)
class ObjectEvidencePackage:
    object_id: int
    object_type: str
    object_name: str
    description: str
    code_excerpt_chunks: list[str]
    code_truncated: bool
    code_item: EvidenceItem | None = None
    atc_items: list[EvidenceItem] = field(default_factory=list)
    supplemental_items: list[EvidenceItem] = field(default_factory=list)

    def all_items(self) -> list[EvidenceItem]:
        items = [*self.atc_items, *self.supplemental_items]
        if self.code_item is not None:
            items.append(self.code_item)
        return items


def build_evidence_package(session: Session, obj: SAPObject) -> ObjectEvidencePackage:
    code_excerpt_chunks, truncated = _load_code_excerpt(session, obj)

    atc_findings = list(
        session.scalars(select(ATCFinding).where(ATCFinding.correlated_object_id == obj.id))
    )
    atc_items = [
        EvidenceItem(
            ref_id=f"ATC-{f.id}",
            source_type="ATC_FINDING",
            entity_id=f.id,
            summary=f"{f.check_title or 'ATC finding'}: {(f.check_message or '').strip()[:300]}",
        )
        for f in atc_findings
    ]

    rows = list(
        session.execute(
            select(EvidenceCorrelation, EvidenceRecord, EvidenceDataset)
            .join(EvidenceRecord, EvidenceCorrelation.evidence_record_id == EvidenceRecord.id)
            .join(EvidenceDataset, EvidenceRecord.dataset_id == EvidenceDataset.id)
            .where(
                EvidenceCorrelation.target_type == _TARGET_SAP_OBJECT,
                EvidenceCorrelation.target_id == obj.id,
                EvidenceCorrelation.status.in_(_MATCHED_STATUSES),
            )
        )
    )
    supplemental_items = [
        EvidenceItem(
            ref_id=f"EVD-{rec.id}",
            source_type="SUPPLEMENTAL_EVIDENCE",
            entity_id=rec.id,
            summary=f"{dataset.dataset_type} / {rec.record_type} ({rec.capability}): {_short_payload(rec.normalized_payload)}",
        )
        for _corr, rec, dataset in rows
    ]

    code_item = (
        EvidenceItem(ref_id="SRC-1", source_type="SOURCE_CODE", entity_id=obj.source_file_id, summary="source code excerpt")
        if code_excerpt_chunks
        else None
    )

    return ObjectEvidencePackage(
        object_id=obj.id,
        object_type=obj.object_type,
        object_name=obj.object_name,
        description=obj.description,
        code_excerpt_chunks=code_excerpt_chunks,
        code_truncated=truncated,
        code_item=code_item,
        atc_items=atc_items,
        supplemental_items=supplemental_items,
    )


def _load_code_excerpt(session: Session, obj: SAPObject) -> tuple[list[str], bool]:
    source_file = session.get(SourceFile, obj.source_file_id)
    if source_file is None:
        return [], False
    scan = session.get(SourceScan, source_file.scan_id)
    if scan is None:
        return [], False

    abs_path = os.path.join(scan.source_path, source_file.rel_path)
    try:
        with open(abs_path, encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError:
        return [], False

    start = max(obj.line_start - 1, 0)
    end = obj.line_end if obj.line_end is not None else len(lines)
    excerpt = "".join(lines[start:end])

    chunks = chunk_source(excerpt)
    included: list[str] = []
    total = 0
    for chunk in chunks:
        if included and total + len(chunk) > MAX_CODE_EXCERPT_CHARS:
            break
        included.append(chunk)
        total += len(chunk)

    return included, len(included) < len(chunks)


def _short_payload(payload: dict) -> str:
    parts = [f"{k}={v}" for k, v in list(payload.items())[:5]]
    return ", ".join(parts)[:300]


def render_prompt(package: ObjectEvidencePackage) -> str:
    """Render `package` into the user-turn text handed to the provider."""
    lines = [
        f"Object: {package.object_type} {package.object_name}",
        f"Description: {package.description or '(none)'}",
        "",
        "Source code excerpt" + (" (truncated — object larger than the analysis budget):" if package.code_truncated else ":"),
        "```abap",
        "\n".join(package.code_excerpt_chunks) if package.code_excerpt_chunks else "(no source available)",
        "```",
        "",
        "Evidence available for citation (use these ref_id values in evidence_refs):",
    ]
    if not package.all_items():
        lines.append("(none — no correlated ATC finding or supplemental evidence for this object)")
    for item in package.all_items():
        lines.append(f"- {item.ref_id} [{item.source_type}]: {item.summary}")

    return "\n".join(lines)
