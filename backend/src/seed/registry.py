"""Registry of seed datasets and idempotent application logic (SPRINT-04: Assessment-centric)."""

import hashlib
import io
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import openpyxl
from sqlalchemy import select
from sqlalchemy.orm import Session

from atc.persistence import persist_atc_import
from evidence.adapters import hana_sizing
from ingestion.classifier import classify
from parsing.dispatcher import parse_file
from pipeline.engine import create_pipeline_run, run_pipeline
from pipeline.stages import canonical_object_key
from persistence.models import (
    Assessment,
    AssessmentStatus,
    ATCRun,
    Client,
    EvidenceArtifact,
    EvidenceArtifactRole,
    EvidenceDataset,
    EvidenceDatasetStatus,
    SAPObject,
    ScanStatus,
    SeedRun,
    SourceFile,
    SourceScan,
)
from settings import get_settings

SeedStep = Callable[[Session], None]


@dataclass(frozen=True)
class SeedDataset:
    name: str
    version: int
    description: str
    steps: list[SeedStep] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Seed steps — each must be idempotent (upsert / merge by natural key)
# ---------------------------------------------------------------------------


def _seed_acme_assessment(session: Session) -> None:
    """Seed Acme Industries client and demo assessment (with scan + parsed objects)."""
    client = session.scalars(select(Client).where(Client.name == "Acme Industries")).first()
    if client is None:
        client = Client(
            name="Acme Industries",
            description="Synthetic demo client for PoC demonstrations.",
        )
        session.add(client)
        session.flush()

    assessment = session.scalars(
        select(Assessment).where(
            Assessment.client_id == client.id,
            Assessment.name == "Clean Core PoC Assessment",
        )
    ).first()
    if assessment is None:
        session.add(
            Assessment(
                client_id=client.id,
                name="Clean Core PoC Assessment",
                sap_source_system="S/4HANA Development (S4D)",
                description="Initial assessment to demonstrate the Clean Core Analyzer PoC.",
                status=AssessmentStatus.CREATED.value,
            )
        )
        session.flush()


def _seed_demo_source_scan(session: Session) -> None:
    """Seed a completed source scan for the Acme demo assessment using demo-source files."""
    assessment = session.scalars(
        select(Assessment)
        .join(Assessment.client)
        .where(
            Client.name == "Acme Industries",
            Assessment.name == "Clean Core PoC Assessment",
        )
    ).first()
    if assessment is None:
        return

    existing = session.scalars(
        select(SourceScan).where(
            SourceScan.assessment_id == assessment.id,
            SourceScan.status == ScanStatus.COMPLETED.value,
        )
    ).first()
    if existing is not None:
        return

    demo_root = Path("/workspace/demo-source")
    if not demo_root.is_dir():
        return

    files = [p for p in sorted(demo_root.rglob("*")) if p.is_file()]
    scan = SourceScan(
        assessment_id=assessment.id,
        source_path=str(demo_root),
        status=ScanStatus.COMPLETED.value,
        total_files=len(files),
        scanned_files=len(files),
    )
    session.add(scan)
    session.flush()

    for abs_path in files:
        stat = abs_path.stat()
        rel = str(abs_path.relative_to(demo_root)).replace(os.sep, "/")
        h = hashlib.sha256()
        with open(abs_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        session.add(
            SourceFile(
                scan_id=scan.id,
                assessment_id=assessment.id,
                rel_path=rel,
                size_bytes=stat.st_size,
                mtime=stat.st_mtime,
                sha256=h.hexdigest(),
                category=classify(rel),
            )
        )


def _seed_demo_sap_objects(session: Session) -> None:
    """Parse demo-source ABAP/DDIC files and persist SAPObject entities."""
    assessment = session.scalars(
        select(Assessment)
        .join(Assessment.client)
        .where(
            Client.name == "Acme Industries",
            Assessment.name == "Clean Core PoC Assessment",
        )
    ).first()
    if assessment is None:
        return

    scan = session.scalars(
        select(SourceScan).where(
            SourceScan.assessment_id == assessment.id,
            SourceScan.status == ScanStatus.COMPLETED.value,
        )
    ).first()
    if scan is None:
        return

    existing_count = session.query(SAPObject).filter(
        SAPObject.assessment_id == assessment.id
    ).count()
    if existing_count > 0:
        return

    files = list(
        session.scalars(
            select(SourceFile).where(
                SourceFile.scan_id == scan.id,
                SourceFile.category.in_(["abap_source", "ddic"]),
            )
        )
    )

    demo_root = Path("/workspace/demo-source")
    for sf in files:
        abs_path = demo_root / sf.rel_path
        try:
            content = abs_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        parsed = parse_file(content, sf.rel_path, sf.category)
        for p in parsed:
            session.add(
                SAPObject(
                    assessment_id=assessment.id,
                    source_file_id=sf.id,
                    object_type=p.object_type,
                    object_name=p.object_name,
                    canonical_key=canonical_object_key(p.object_type, p.object_name),
                    description=p.description,
                    line_start=p.line_start,
                    line_end=p.line_end,
                    attributes=p.attributes,
                )
            )


_ATC_HEADERS = ["Priority", "Check Title", "Check Message", "Object name", "Object Type", "Package"]
_ATC_ROWS = [
    [1, "CL_BADI_IMPLEMENTATION", "Implicit BAdI enhancement detected", "ZCL_CUSTOM_ORDER", "CLAS", "ZPACKAGE"],
    [2, "OBSOLETE_STATEMENT", "Obsolete ABAP statement in use", "ZFM_PROCESS_ORDER", "FUNC", "ZPACKAGE"],
    [3, "PERFORMANCE_WARNING", "SELECT inside LOOP detected", "ZPROGRAM_REPORT", "PROG", "ZPACKAGE"],
    [1, "S4HANA_SIMPLIFICATION", "Simplification item impact", "ZCL_UTILITY_HELPER", "CLAS", "ZPACKAGE"],
]


def _seed_demo_atc_import(session: Session) -> None:
    """Seed a compact, reproducible ATC run for the Acme demo assessment (CAP-005, SPRINT-17) —
    a handful of findings against the demo-source objects, imported through the same
    `atc.persistence.persist_atc_import` a real XLSX upload uses, so the demo can show
    correlated ATC findings without requiring a manual upload step."""
    assessment = session.scalars(
        select(Assessment)
        .join(Assessment.client)
        .where(
            Client.name == "Acme Industries",
            Assessment.name == "Clean Core PoC Assessment",
        )
    ).first()
    if assessment is None:
        return

    existing = session.scalars(select(ATCRun).where(ATCRun.assessment_id == assessment.id)).first()
    if existing is not None:
        return

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ATC Results"
    ws.append(_ATC_HEADERS)
    for row in _ATC_ROWS:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)

    persist_atc_import(session, assessment.id, "atc_demo_sample.xlsx", buf.getvalue())


_HANA_SIZING_SAMPLE = """
--------------------------------------------------------------------------------
| SIZING RESULTS IN GiB                                                        |
|------------------------------------------------------------------------------|
| The anticipated maximum requirements for the HANA DATABASE SERVER are:       |
|                                                                              |
| - Memory requirement                                                 1.240,0 |
| - Net data volume size on disk                                       3.150,5 |
--------------------------------------------------------------------------------

 SID                                                                       ACM
 NW release:                                                         756 SP 02

--------------------------------------------------------------------------------
|   LARGEST COLUMN              ESTIMATED MEMORY              ESTIMATED RECORD |
|   LOADABLE TABLES               SIZE IN GiB                      COUNT       |
|------------------------------------------------------------------------------|
| DBTABLOG                                 84,0                   210.512.004  |
| ACDOCA                                   41,2                   512.883.771  |
--------------------------------------------------------------------------------
"""


def _seed_demo_evidence_dataset(session: Session) -> None:
    """Seed a compact, reproducible supplemental-evidence dataset for the Acme demo assessment
    (CAP-005, SPRINT-17) — a small real-format HANA Sizing Report .txt, imported through the same
    adapter/durable-pipeline path (`evidence.adapters.hana_sizing` + a real `evidence_import`
    PipelineRun) a real upload uses, so the demo shows a genuine supplemental-evidence dataset
    without requiring a multi-GB Panaya/Signavio export."""
    assessment = session.scalars(
        select(Assessment)
        .join(Assessment.client)
        .where(
            Client.name == "Acme Industries",
            Assessment.name == "Clean Core PoC Assessment",
        )
    ).first()
    if assessment is None:
        return

    existing = session.scalars(
        select(EvidenceDataset).where(EvidenceDataset.assessment_id == assessment.id)
    ).first()
    if existing is not None:
        return

    settings = get_settings()
    filename = "HANA_SIZING_ACME.TXT"
    content = _HANA_SIZING_SAMPLE.encode("utf-8")
    digest = hashlib.sha256(content).hexdigest()

    dataset = EvidenceDataset(
        assessment_id=assessment.id,
        dataset_type=hana_sizing.DATASET_TYPE,
        display_name=filename,
        source_filename=filename,
        source_sha256=digest,
        source_size_bytes=len(content),
        importer_name="hana_sizing",
        importer_version=hana_sizing.IMPORTER_VERSION,
        status=EvidenceDatasetStatus.INSPECTED.value,
    )
    session.add(dataset)
    session.flush()

    dest = Path(settings.evidence_storage_path) / str(dataset.id) / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)

    session.add(
        EvidenceArtifact(
            dataset_id=dataset.id,
            member_name=filename,
            artifact_role=EvidenceArtifactRole.PRIMARY.value,
            size_bytes=len(content),
            sha256=digest,
            storage_path=str(dest),
        )
    )
    session.commit()

    run = create_pipeline_run(
        session, assessment.id, str(dest), kind="evidence_import", evidence_dataset_id=dataset.id,
    )
    run_pipeline(run.id, settings.database_url)


def _seed_rodobens_assessment(session: Session) -> None:
    """Seed Rodobens client and ECC assessment — no pre-loaded scan, for full ingestion flow testing."""
    client = session.scalars(select(Client).where(Client.name == "Rodobens")).first()
    if client is None:
        client = Client(
            name="Rodobens",
            description="Cliente demo para testes de ingestão de fontes.",
        )
        session.add(client)
        session.flush()

    assessment = session.scalars(
        select(Assessment).where(
            Assessment.client_id == client.id,
            Assessment.name == "Assessment01",
        )
    ).first()
    if assessment is None:
        session.add(
            Assessment(
                client_id=client.id,
                name="Assessment01",
                sap_source_system="ECC 6.0",
                description="Assessment inicial para testes de ingestão de fontes.",
                status=AssessmentStatus.CREATED.value,
            )
        )


# ---------------------------------------------------------------------------
# Dataset registry
# ---------------------------------------------------------------------------

DATASETS: dict[str, SeedDataset] = {
    "demo": SeedDataset(
        name="demo",
        version=8,
        description=(
            "Synthetic demo dataset (Assessment-centric): Acme (scan + parsed objects + compact "
            "ATC run + compact HANA Sizing evidence dataset) + Rodobens (no scan)."
        ),
        steps=[
            _seed_acme_assessment,
            _seed_demo_source_scan,
            _seed_demo_sap_objects,
            _seed_demo_atc_import,
            _seed_demo_evidence_dataset,
            _seed_rodobens_assessment,
        ],
    ),
}


def apply_dataset(session: Session, name: str) -> bool:
    """Apply a dataset if missing or outdated. Returns True when seed steps ran."""
    dataset = DATASETS[name]
    run = session.get(SeedRun, name)
    if run is not None and run.version >= dataset.version:
        return False
    for step in dataset.steps:
        step(session)
    if run is None:
        session.add(SeedRun(name=name, version=dataset.version))
    else:
        run.version = dataset.version
    session.commit()
    return True


def list_runs(session: Session) -> list[SeedRun]:
    return list(session.scalars(select(SeedRun).order_by(SeedRun.name)))
