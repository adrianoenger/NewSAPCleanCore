"""Registry of seed datasets and idempotent application logic (SPRINT-04: Assessment-centric)."""

import hashlib
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ingestion.classifier import classify
from parsing.dispatcher import parse_file
from persistence.models import (
    Assessment,
    AssessmentStatus,
    Client,
    SAPObject,
    ScanStatus,
    SeedRun,
    SourceFile,
    SourceScan,
)

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
                    description=p.description,
                    line_start=p.line_start,
                    line_end=p.line_end,
                    attributes=p.attributes,
                )
            )


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
        version=6,
        description="Synthetic demo dataset (Assessment-centric): Acme (scan + parsed objects) + Rodobens (no scan).",
        steps=[
            _seed_acme_assessment,
            _seed_demo_source_scan,
            _seed_demo_sap_objects,
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
