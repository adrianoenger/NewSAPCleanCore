"""SAP Signavio Process Insights adapter (ADR-017), rewritten against a real export.

The original profile (a `<SignavioSystem>`-rooted metadata XML, `keyFigureId`/`header`/`rows`
as top-level JSON keys) was invented — no sample existed when SPRINT-08 first shipped this
adapter. Validated later against a real ~28MB export, the actual structure differs in every
particular:

- System metadata is **not** one simple-attribute XML — it is standard ABAP-serialized XML
  (`<asx:abap>` namespace, `<HEADER_DATA><item><KEY>k</KEY><VALUE>v</VALUE></item>...`), split
  across two files (`ana_sys_header.xml`, `ana_sys_add_info.xml` — names vary, so any `.xml`
  member is scanned for this shape rather than hard-coding those two names).
- Each chunk's JSON is not flat — everything lives under a single `"dataSet"` key:
  `{"dataSet": {"serviceName", "serviceDescr", "serviceType", "keyFigureId", "timestamp",
  "completed", "header": [...], "data": [[...], ...]}}` (the row array is called `data`, not
  `rows`). Reading `chunk.get("rows")` against this shape always found nothing — the exact
  failure this adapter shipped with before a real sample surfaced it (silently zero records
  under a misleadingly non-failing status, since `_evidence_import_finalize` now separately
  guards against "capabilities detected but zero records extracted").

Each JSON chunk file is individually bounded ("chunked" by definition), so a chunk is read
fully; one JSON chunk member is one durable, checkpointable import batch.
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException
from sqlalchemy.orm import Session

from evidence.adapters.base import ImportBatchOutcome, ImportBatchPlan, InspectionResult, bulk_insert_evidence_records
from persistence.models import EvidenceDataset

DATASET_TYPE = "SIGNAVIO_PROCESS_INSIGHTS"
IMPORTER_VERSION = "2.0"


def _local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _json_members(zf: zipfile.ZipFile) -> list[str]:
    return sorted(n for n in zf.namelist() if n.lower().endswith(".json"))


def _xml_members(zf: zipfile.ZipFile) -> list[str]:
    return sorted(n for n in zf.namelist() if n.lower().endswith(".xml"))


def detect(filename: str, file_path: Path) -> bool:
    """Filename hint is a fast-path bonus; the deciding signal is either a chunk's `dataSet`
    JSON shape or the ABAP-serialized metadata XML's `UsageSystem` key."""
    lower = filename.lower()
    if not lower.endswith(".zip"):
        return False
    if "signavio" in lower:
        return True
    try:
        with zipfile.ZipFile(file_path) as zf:
            json_members = _json_members(zf)
            if json_members:
                with zf.open(json_members[0]) as fh:
                    head = fh.read(512)
                if b'"dataSet"' in head or b'"keyFigureId"' in head:
                    return True
            for member in _xml_members(zf):
                with zf.open(member) as fh:
                    head = fh.read(4096)
                if b"UsageSystem" in head or b"asx:abap" in head:
                    return True
    except (zipfile.BadZipFile, KeyError):
        return False
    return False


def _parse_abap_key_value_xml(fh) -> dict[str, str]:
    """Extract `<item><KEY>k</KEY><VALUE>v</VALUE></item>` pairs from ABAP-serialized XML,
    ignoring any other `item`-shaped element (e.g. `<SW_COMPONENT><item>...` has different
    children and is simply skipped, not guessed at)."""
    try:
        root = ET.parse(fh).getroot()
    except (ET.ParseError, DefusedXmlException):
        return {}
    result: dict[str, str] = {}
    for elem in root.iter():
        if _local_tag(elem.tag) != "item":
            continue
        key_text: str | None = None
        value_text: str = ""
        for child in elem:
            child_tag = _local_tag(child.tag)
            if child_tag == "KEY":
                key_text = (child.text or "").strip()
            elif child_tag == "VALUE":
                value_text = (child.text or "").strip()
        if key_text:
            result[key_text] = value_text
    return result


def _read_system_metadata(zf: zipfile.ZipFile) -> tuple[dict[str, str], list[str]]:
    xml_members = _xml_members(zf)
    if not xml_members:
        return {}, ["No system metadata XML found in Signavio package"]
    merged: dict[str, str] = {}
    warnings: list[str] = []
    for member in xml_members:
        try:
            with zf.open(member) as fh:
                merged.update(_parse_abap_key_value_xml(fh))
        except (NotImplementedError, RuntimeError) as exc:
            warnings.append(f"{member}: cannot read metadata XML ({exc})")
    return merged, warnings


def _peek_dataset(zf: zipfile.ZipFile, member: str) -> tuple[dict | None, list[str]]:
    try:
        with zf.open(member) as fh:
            payload = json.load(fh)
    except (json.JSONDecodeError, KeyError) as exc:
        return None, [f"{member}: unreadable JSON chunk ({exc})"]
    except (NotImplementedError, RuntimeError) as exc:
        return None, [f"{member}: cannot read chunk ({exc})"]
    data_set = payload.get("dataSet")
    if not isinstance(data_set, dict):
        return None, [f"{member}: no 'dataSet' object found"]
    return data_set, []


def inspect(file_path: Path) -> InspectionResult:
    warnings: list[str] = []
    try:
        with zipfile.ZipFile(file_path) as zf:
            metadata, meta_warnings = _read_system_metadata(zf)
            warnings.extend(meta_warnings)

            members = _json_members(zf)
            key_figures: set[str] = set()
            for member in members:
                data_set, chunk_warnings = _peek_dataset(zf, member)
                warnings.extend(chunk_warnings[:1])  # bounded — don't flood on many bad chunks
                if data_set and data_set.get("keyFigureId"):
                    key_figures.add(data_set["keyFigureId"])
    except zipfile.BadZipFile as exc:
        return InspectionResult(
            dataset_type=DATASET_TYPE, display_name=file_path.name, warnings=[f"Not a valid ZIP: {exc}"]
        )

    capabilities = ["PROCESS_KPI"] if key_figures else []
    if not members:
        warnings.append("No chunked JSON datasets found in Signavio package")
    elif not key_figures:
        warnings.append("No chunk carried a recognizable 'dataSet.keyFigureId' — nothing will be extracted")

    return InspectionResult(
        dataset_type=DATASET_TYPE,
        display_name=file_path.name,
        capabilities=capabilities,
        manifest={
            "system": metadata,
            "chunk_count": len(members),
            "key_figure_ids": sorted(key_figures),
        },
        source_system_hint=metadata.get("UsageSystem"),
        source_client_hint=metadata.get("UsageSystemClient"),
        warnings=warnings[:20],
    )


def plan_batches(file_path: Path, inspection: InspectionResult) -> list[ImportBatchPlan]:
    with zipfile.ZipFile(file_path) as zf:
        members = _json_members(zf)
    return [ImportBatchPlan(batch_key=member, payload={"member": member}) for member in members]


def import_batch(
    file_path: Path, dataset: EvidenceDataset, batch: ImportBatchPlan, session: Session
) -> ImportBatchOutcome:
    member = batch.payload["member"]

    with zipfile.ZipFile(file_path) as zf:
        data_set, warnings = _peek_dataset(zf, member)
    if data_set is None:
        return ImportBatchOutcome(records_imported=0, warnings=warnings)

    key_figure_id = data_set.get("keyFigureId")
    service_name = data_set.get("serviceName")
    service_descr = data_set.get("serviceDescr")
    service_type = data_set.get("serviceType")
    timestamp = data_set.get("timestamp")
    header = data_set.get("header") or []
    rows = data_set.get("data") or []

    if not rows:
        return ImportBatchOutcome(records_imported=0)

    # Bulk `INSERT ... ON CONFLICT DO NOTHING` (chunked to stay under Postgres's bind-param
    # limit — see bulk_insert_evidence_records) instead of one SELECT-then-INSERT round trip
    # per row: a real Signavio chunk can carry thousands of rows (confirmed: ~9600/chunk,
    # several million total across a real ~28MB export), and the per-row existence-check
    # pattern the other adapters still use does not scale to that.
    values = [
        {
            "dataset_id": dataset.id,
            "record_type": "signavio_kpi_observation",
            "capability": "PROCESS_KPI",
            "source_key": f"{member}:{row_index}",
            "record_fingerprint": hashlib.sha256(f"{member}:{row_index}".encode()).hexdigest()[:32],
            "normalized_payload": {
                "key_figure_id": key_figure_id,
                "service_name": service_name,
                "service_descr": service_descr,
                "service_type": service_type,
                "timestamp": timestamp,
                "header": header,
                "row": row,
            },
            "source_locator": {"member": member, "row_index": row_index, "key_figure_id": key_figure_id},
        }
        for row_index, row in enumerate(rows)
    ]
    imported = bulk_insert_evidence_records(session, values)
    session.flush()
    return ImportBatchOutcome(records_imported=imported)
