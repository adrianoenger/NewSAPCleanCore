"""Panaya ETL adapter (ADR-017), rewritten against a real ~2.8GB customer export.

No reviewed Panaya sample existed when this adapter was first written (ADR-017's original
`<PanayaExport>` profile was an invented placeholder). Validated later against an actual export,
the real structure is a single `<ROOT_ELEMENT>` containing `<HEADER .../>` (system metadata as
attributes), `<ETL_RUN_PARAMS>`, and ~90 sibling **sections** (`<REPOSITORY_OBJECTS>`,
`<PROGRAMS>`, `<WHERE_USED_TABLE>`, `<SCI_HANA_ISSUES>`, ...), each holding thousands to millions
of flat, attribute-only child records. The file is **not** wrapped in a ZIP in practice — a bare
multi-gigabyte `.xml` — though a ZIP-wrapped variant is still supported in case some export
configuration produces one.

Two real, load-bearing quirks this adapter handles that the invented profile never anticipated:

1. **Not strictly well-formed XML.** Raw ABAP/text content can carry literal illegal control
   bytes (confirmed: a raw `0x1C` inside a `<![CDATA[...]]>`-adjacent comment) *and* escaped
   illegal numeric character references (confirmed: `&#0;` for a NUL byte in a garbled field).
   Both are outright forbidden by the XML 1.0 `Char` production and abort `expat` with no way to
   resume. `evidence.adapters.base.SanitizingXMLStream` strips both, streaming, before the parser
   ever sees them — dropping only the illegal placeholder markers, never fabricating content.
2. **Scale.** ~90 sections, several in the single-digit millions of rows (confirmed:
   `SCI_HANA_PERFORMANCE_ISSUES_DETAILS` ~5M, `WHERE_USED_TABLE` ~1.2M). Importing every row of
   every section is not a PoC-appropriate goal. This adapter extracts a small **curated** subset
   of sections with verified, correlatable attribute shapes (`_CURATED_SECTIONS`); every section
   — curated or not — is still counted in `inspect()`'s manifest so nothing is invisible, and a
   curated section's rows are capped (`_MAX_RECORDS_PER_SECTION`) with an explicit truncation
   warning rather than an unbounded import. Extending the curated set to another section is a
   one-line dict entry once its real attribute shape has been verified — never guessed.

Because random access into a multi-gigabyte XML isn't practical, each batch = one curated
section, re-streamed from the start of the file and stopped as soon as that section's closing
tag is consumed (sections earlier in the document finish fast; a late section like
`WHERE_USED_TABLE` costs close to a full pass — acceptable for a one-time background import).
"""
from __future__ import annotations

import hashlib
import zipfile
from contextlib import contextmanager
from pathlib import Path

from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException
from sqlalchemy import select
from sqlalchemy.orm import Session

from evidence.adapters.base import ImportBatchOutcome, ImportBatchPlan, InspectionResult, SanitizingXMLStream
from persistence.models import EvidenceDataset, EvidenceRecord

DATASET_TYPE = "PANAYA_ETL"
IMPORTER_VERSION = "2.0"

_SIGNATURE = b"EXPORT_TOOL_VERSION"
_MAX_RECORDS_PER_SECTION = 20000

# Verified against the real export — only sections with a confirmed, correlatable attribute
# shape are listed. Everything else is counted (inspect()'s manifest) but not persisted as
# records yet; add an entry here once a new section's real shape is verified.
_CURATED_SECTIONS: dict[str, dict[str, str]] = {
    "REPOSITORY_OBJECTS": {
        "capability": "TECHNICAL_OBJECT_METADATA", "record_type": "panaya_repository_object",
        "object_name_attr": "OBJ_NAME", "object_type_attr": "OBJECT", "package_attr": "DEVCLASS",
    },
    "PROGRAMS": {
        "capability": "TECHNICAL_OBJECT_METADATA", "record_type": "panaya_program",
        "object_name_attr": "NAME",
    },
    "FUNCTIONS": {
        "capability": "TECHNICAL_OBJECT_METADATA", "record_type": "panaya_function",
        "object_name_attr": "FUNCNAME",
    },
    "MODIFICATIONS": {
        "capability": "SOURCE_CODE", "record_type": "panaya_modification",
        "object_name_attr": "OBJ_NAME", "object_type_attr": "OBJ_TYPE",
    },
    "NOTES_HEADER": {
        "capability": "S4_CONVERSION_SIGNAL", "record_type": "panaya_sap_note",
    },
}


def detect(filename: str, file_path: Path) -> bool:
    lower = filename.lower()
    if "panaya" in lower:
        return True
    if not (lower.endswith(".xml") or lower.endswith(".zip")):
        return False
    try:
        with _open_xml_stream(file_path) as stream:
            head = stream.read(65536)
    except (zipfile.BadZipFile, ValueError, OSError):
        return False
    return _SIGNATURE in head


def _local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find_primary_xml_member(zf: zipfile.ZipFile) -> str | None:
    xml_members = [n for n in zf.namelist() if n.lower().endswith(".xml")]
    if not xml_members:
        return None
    return max(xml_members, key=lambda n: zf.getinfo(n).file_size)


@contextmanager
def _open_xml_stream(file_path: Path):
    """Yield a `SanitizingXMLStream` over the primary XML, whether `file_path` is a bare
    `.xml` (the real-world case) or a ZIP wrapping one (kept for defense in depth)."""
    if file_path.suffix.lower() == ".zip":
        with zipfile.ZipFile(file_path) as zf:
            xml_name = _find_primary_xml_member(zf)
            if xml_name is None:
                raise ValueError("No XML member found in ZIP")
            try:
                fh = zf.open(xml_name)
            except NotImplementedError as exc:
                method = zipfile.compressor_names.get(zf.getinfo(xml_name).compress_type, "unknown")
                raise NotImplementedError(
                    f"ZIP member {xml_name!r} uses compression method '{method}', which Python's "
                    f"standard zipfile module cannot decode ({exc}). Re-export as a bare .xml (no "
                    f"ZIP) or with a supported method (store/deflate/bzip2/lzma), or upload the "
                    f"already-unzipped .xml directly if you have it."
                ) from exc
            with fh:
                yield SanitizingXMLStream(fh)
    else:
        with open(file_path, "rb") as raw:
            yield SanitizingXMLStream(raw)


def inspect(file_path: Path) -> InspectionResult:
    header_attrs: dict[str, str] = {}
    section_counts: dict[str, int] = {}
    depth = 0
    current_section: str | None = None

    try:
        with _open_xml_stream(file_path) as stream:
            for event, elem in ET.iterparse(stream, events=("start", "end")):
                tag = _local_tag(elem.tag)
                if event == "start":
                    depth += 1
                    if depth == 2:
                        current_section = tag
                        section_counts.setdefault(tag, 0)
                        if tag == "HEADER":
                            header_attrs = dict(elem.attrib)
                else:
                    if depth == 3 and current_section is not None:
                        section_counts[current_section] += 1
                    if depth >= 2:
                        elem.clear()
                    depth -= 1
    except (zipfile.BadZipFile, ValueError) as exc:
        return InspectionResult(dataset_type=DATASET_TYPE, display_name=file_path.name, warnings=[str(exc)])
    except (ET.ParseError, DefusedXmlException) as exc:
        return InspectionResult(
            dataset_type=DATASET_TYPE, display_name=file_path.name,
            warnings=[f"XML parse error even after illegal-character sanitization: {exc}"],
        )
    except (NotImplementedError, RuntimeError) as exc:
        # zipfile.open() raises these for an unsupported compression method or an
        # encrypted entry (only reachable via the ZIP-wrapped fallback path) —
        # `_open_xml_stream` already names the specific method for NotImplementedError.
        return InspectionResult(dataset_type=DATASET_TYPE, display_name=file_path.name, warnings=[str(exc)])
    except OSError as exc:
        return InspectionResult(dataset_type=DATASET_TYPE, display_name=file_path.name, warnings=[f"Cannot read file: {exc}"])

    capabilities = sorted(
        {info["capability"] for name, info in _CURATED_SECTIONS.items() if section_counts.get(name)}
    )
    warnings: list[str] = []
    if not section_counts:
        warnings.append("No recognized Panaya ETL sections found")

    return InspectionResult(
        dataset_type=DATASET_TYPE,
        display_name=file_path.name,
        capabilities=capabilities,
        manifest={
            "header": header_attrs,
            "section_counts": section_counts,
            "curated_sections": {n: section_counts.get(n, 0) for n in _CURATED_SECTIONS},
        },
        source_system_hint=header_attrs.get("SYSTEM_ID"),
        source_client_hint=header_attrs.get("CLIENT"),
        warnings=warnings,
    )


def plan_batches(file_path: Path, inspection: InspectionResult) -> list[ImportBatchPlan]:
    counts = inspection.manifest.get("section_counts", {})
    return [
        ImportBatchPlan(batch_key=name, payload={"section": name})
        for name in _CURATED_SECTIONS
        if counts.get(name, 0) > 0
    ]


def import_batch(
    file_path: Path, dataset: EvidenceDataset, batch: ImportBatchPlan, session: Session
) -> ImportBatchOutcome:
    section = batch.payload["section"]
    info = _CURATED_SECTIONS[section]
    rows: list[tuple[int, dict]] = []
    depth = 0
    current_section: str | None = None
    row_index = 0
    truncated = False

    with _open_xml_stream(file_path) as stream:
        for event, elem in ET.iterparse(stream, events=("start", "end")):
            tag = _local_tag(elem.tag)
            if event == "start":
                depth += 1
                if depth == 2:
                    current_section = tag
            else:
                if depth == 3 and current_section == section:
                    if row_index < _MAX_RECORDS_PER_SECTION:
                        rows.append((row_index, dict(elem.attrib)))
                    else:
                        truncated = True
                    row_index += 1
                if depth >= 2:
                    elem.clear()
                depth -= 1
                if depth == 1 and current_section == section:
                    break  # done with the target section — no need to read the rest of the file

    imported = 0
    for idx, attrs in rows:
        source_key = f"{section}:{idx}"
        fingerprint = hashlib.sha256(source_key.encode()).hexdigest()[:32]
        already = session.execute(
            select(EvidenceRecord.id).where(
                EvidenceRecord.dataset_id == dataset.id, EvidenceRecord.record_fingerprint == fingerprint
            )
        ).first()
        if already is not None:
            continue

        object_name = attrs.get(info["object_name_attr"]) if "object_name_attr" in info else None
        object_type = attrs.get(info["object_type_attr"]) if "object_type_attr" in info else None
        package_name = attrs.get(info["package_attr"]) if "package_attr" in info else None

        session.add(
            EvidenceRecord(
                dataset_id=dataset.id,
                record_type=info["record_type"],
                capability=info["capability"],
                source_key=source_key,
                record_fingerprint=fingerprint,
                object_name=object_name or None,
                object_type=object_type or None,
                package_name=package_name or None,
                normalized_payload=attrs,
                source_locator={"section": section, "row_index": idx},
            )
        )
        imported += 1
        if imported % 500 == 0:
            session.flush()

    session.flush()
    warnings = (
        [f"Section {section} truncated to {_MAX_RECORDS_PER_SECTION} records — more rows exist in the source"]
        if truncated else []
    )
    return ImportBatchOutcome(records_imported=imported, warnings=warnings)
