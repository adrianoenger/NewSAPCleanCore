"""EvidenceDatasetAdapter contract (ADR-017).

Lifecycle: inspect -> validate -> import/stream -> normalize -> (correlate -> summarize).
Adapters own format-specific parsing only (Panaya XML, Signavio ZIP/JSON, HANA sizing TXT,
SAP Readiness Check DOCX); correlation and summarization are shared, provider-agnostic
steps applied uniformly to the canonical EvidenceRecord rows an adapter produces — see
`evidence.correlation`.

Every adapter module (`evidence.adapters.panaya`, `.signavio`, `.hana_sizing`,
`.readiness_check`) exposes the same four functions so the pipeline stage and API routes
can dispatch on `dataset_type` without branching on provider-specific internals:

    detect(filename, file_path) -> bool
    inspect(file_path) -> InspectionResult
    plan_batches(file_path, inspection) -> list[ImportBatchPlan]
    import_batch(file_path, dataset, batch, session) -> ImportBatchOutcome

`detect` sniffs actual ZIP/XML/JSON structure, not just the filename — a real export's
filename rarely contains the provider's name, so filename hints are a fast-path bonus,
never the only signal (same reason ATC's importer never hard-codes one reviewed
filename/schema as the only valid input).

`plan_batches`/`import_batch` split large sources into checkpointable, resumable units
(one WorkItem per batch) so nothing requires loading a whole package into memory at once.
"""
from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO, Protocol

from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from persistence.models import EvidenceRecord

if TYPE_CHECKING:
    from persistence.models import EvidenceDataset


def peek_xml_root_tag(zf: zipfile.ZipFile, member: str) -> str | None:
    """Cheaply read just the root element's tag (namespace stripped, lowercased) of a
    ZIP member, without parsing the rest of the document — used for content-based
    format detection so a package doesn't need a provider name in its filename."""
    try:
        with zf.open(member) as fh:
            for event, elem in ET.iterparse(fh, events=("start",)):
                return elem.tag.rsplit("}", 1)[-1].lower()
    except (ET.ParseError, DefusedXmlException, KeyError):
        return None
    return None


# ---------------------------------------------------------------------------
# Illegal-XML-character sanitization
#
# Real SAP ETL exports (confirmed on an actual 2.8GB Panaya export) are not always
# strictly well-formed XML: raw ABAP/text content can carry control bytes (e.g. a
# literal 0x1C) and/or escaped illegal numeric character references (e.g. `&#0;` for a
# NUL byte in a garbled field) — both outright forbidden by the XML 1.0 Char production,
# and both make `expat` abort the whole parse with no way to resume. Stripping them in a
# streaming wrapper (bounded memory, one pass) is the only way to parse such a file at all
# without fabricating replacement content for the removed bytes.
# ---------------------------------------------------------------------------

_ILLEGAL_XML_BYTES = bytes(b for b in range(0x00, 0x20) if b not in (0x09, 0x0A, 0x0D)) + bytes([0x7F])
_CHARREF_RE = re.compile(rb"&#x([0-9A-Fa-f]+);|&#([0-9]+);")


def _is_illegal_codepoint(cp: int) -> bool:
    if cp in (0x09, 0x0A, 0x0D):
        return False
    if cp < 0x20 or cp == 0x7F:
        return True
    if 0xD800 <= cp <= 0xDFFF or cp in (0xFFFE, 0xFFFF):
        return True
    return False


def _strip_illegal_charrefs(chunk: bytes) -> bytes:
    def repl(m: re.Match) -> bytes:
        cp = int(m.group(1), 16) if m.group(1) is not None else int(m.group(2))
        return b"" if _is_illegal_codepoint(cp) else m.group(0)

    return _CHARREF_RE.sub(repl, chunk)


class SanitizingXMLStream:
    """Read-only wrapper that strips illegal raw control bytes and illegal numeric XML
    character references from a binary stream before the XML parser ever sees them.

    Boundary-safe for arbitrary chunk sizes: the last `_TAIL` bytes of every read are held
    back until the next call (or EOF) so a `&#x1234;`-style reference split across two
    reads is never evaluated half-formed.
    """

    _TAIL = 16

    def __init__(self, fh: BinaryIO, chunk_size: int = 1 << 20) -> None:
        self._fh = fh
        self._chunk_size = chunk_size
        self._carry = b""

    def read(self, size: int = -1) -> bytes:
        """Never return `b""` unless the source is truly exhausted — a caller (expat's
        incremental parser included) is entitled to treat an empty read as EOF, so a
        transient "not enough buffered yet to safely emit" state must keep pulling from
        the source internally rather than surface a premature empty read.

        Char-ref substitution runs on the *combined* carry+raw buffer before any slicing —
        never on the emitted slice alone. Slicing first and substituting after would let a
        reference get sliced exactly between its emitted half and its still-buffered half,
        so neither half would match the pattern and the illegal reference would leak
        through intact (caught by test_sanitizing_stream_strips_illegal_control_bytes_and_charrefs
        with a deliberately tiny read size to force the split).
        """
        want = size if size and size > 0 else self._chunk_size
        while True:
            raw = self._fh.read(want)
            if not raw:
                emit, self._carry = self._carry, b""  # EOF: flush everything held back
                return emit
            raw = raw.translate(None, delete=_ILLEGAL_XML_BYTES)
            buf = _strip_illegal_charrefs(self._carry + raw)
            safe_len = max(0, len(buf) - self._TAIL)
            if safe_len == 0:
                self._carry = buf
                continue
            emit, self._carry = buf[:safe_len], buf[safe_len:]
            return emit


_POSTGRES_MAX_BIND_PARAMS = 65535


def bulk_insert_evidence_records(session: Session, values: list[dict]) -> int:
    """Bulk-insert `EvidenceRecord` rows via `INSERT ... ON CONFLICT DO NOTHING`, chunked to
    stay under PostgreSQL's 65535-bind-parameter limit — confirmed necessary: a real Signavio
    chunk with ~9600 rows x 7 columns (~67k params) crashed in a single statement, the same
    class of failure `evidence.correlation.correlate_dataset_records` was fixed for earlier.

    Idempotency comes from the DB's own unique constraint (`ON CONFLICT DO NOTHING`), not
    from a SELECT-then-INSERT existence check per row — that pattern does not scale to a
    real dataset's row counts (confirmed: a real ~28MB Signavio export produced several
    million rows). Returns the number of rows actually inserted — `cursor.rowcount` is
    unreliable for a multi-row insert (psycopg reports -1, "not determinable"), so this
    counts `RETURNING` rows instead.
    """
    if not values:
        return 0
    columns_per_row = len(values[0])
    safe_chunk_size = max(1, _POSTGRES_MAX_BIND_PARAMS // columns_per_row)
    inserted = 0
    for i in range(0, len(values), safe_chunk_size):
        stmt = (
            pg_insert(EvidenceRecord.__table__)
            .values(values[i : i + safe_chunk_size])
            .on_conflict_do_nothing(index_elements=["dataset_id", "record_fingerprint"])
            .returning(EvidenceRecord.id)
        )
        inserted += len(session.execute(stmt).fetchall())
    return inserted


@dataclass
class InspectionResult:
    dataset_type: str
    display_name: str
    capabilities: list[str] = field(default_factory=list)
    manifest: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    source_system_hint: str | None = None
    source_client_hint: str | None = None


@dataclass
class ImportBatchPlan:
    """One checkpointable unit of import work — becomes one durable WorkItem payload."""

    batch_key: str
    payload: dict = field(default_factory=dict)


@dataclass
class ImportBatchOutcome:
    """`records_imported` counts whatever canonical rows a batch persisted — usually
    EvidenceRecord, but an artifact-registration-only adapter (one with no reliable
    decoder for its raw content) would count EvidenceArtifact rows instead."""

    records_imported: int = 0
    warnings: list[str] = field(default_factory=list)


class EvidenceDatasetAdapter(Protocol):
    dataset_type: str

    def detect(self, filename: str, file_path: Path) -> bool: ...

    def inspect(self, file_path: Path) -> InspectionResult: ...

    def plan_batches(self, file_path: Path, inspection: InspectionResult) -> list[ImportBatchPlan]: ...

    def import_batch(
        self, file_path: Path, dataset: "EvidenceDataset", batch: ImportBatchPlan, session: Session
    ) -> ImportBatchOutcome: ...
