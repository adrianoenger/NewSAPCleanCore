"""Registry of seed datasets and idempotent application logic."""

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
    SAPSystem,
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


def _seed_demo_client_system_assessment(session: Session) -> None:
    """Seed one Client, one SAP System and one Assessment for demo navigation."""
    # Client
    client = session.scalars(select(Client).where(Client.name == "Acme Industries")).first()
    if client is None:
        client = Client(
            name="Acme Industries",
            description="Synthetic demo client for PoC demonstrations.",
        )
        session.add(client)
        session.flush()  # populate client.id before referencing it

    # SAP System
    system = session.scalars(
        select(SAPSystem).where(
            SAPSystem.client_id == client.id, SAPSystem.sid == "S4D"
        )
    ).first()
    if system is None:
        system = SAPSystem(
            client_id=client.id,
            name="S/4HANA Development",
            sid="S4D",
            description="Demo S/4HANA 2023 system with sample custom code.",
        )
        session.add(system)
        session.flush()

    # Assessment
    assessment = session.scalars(
        select(Assessment).where(
            Assessment.sap_system_id == system.id,
            Assessment.name == "Clean Core PoC Assessment",
        )
    ).first()
    if assessment is None:
        session.add(
            Assessment(
                sap_system_id=system.id,
                name="Clean Core PoC Assessment",
                description="Initial assessment to demonstrate the Clean Core Analyzer PoC.",
                status=AssessmentStatus.CREATED.value,
            )
        )


def _seed_demo_source_scan(session: Session) -> None:
    """Seed a completed source scan for the demo assessment using demo-source files."""
    assessment = session.scalars(
        select(Assessment)
        .join(Assessment.sap_system)
        .join(SAPSystem.client)
        .where(
            Client.name == "Acme Industries",
            Assessment.name == "Clean Core PoC Assessment",
        )
    ).first()
    if assessment is None:
        return

    # Skip if a completed scan already exists
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
        .join(Assessment.sap_system)
        .join(SAPSystem.client)
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

    # Skip if objects already exist for this assessment
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


def _seed_rodobens_client_system_assessment(session: Session) -> None:
    """Seed Rodobens/ECC/Assessment01 — no pre-loaded scan, for full ingestion flow testing."""
    client = session.scalars(select(Client).where(Client.name == "Rodobens")).first()
    if client is None:
        client = Client(
            name="Rodobens",
            description="Cliente demo para testes de ingestão de fontes.",
        )
        session.add(client)
        session.flush()

    system = session.scalars(
        select(SAPSystem).where(SAPSystem.client_id == client.id, SAPSystem.sid == "ECC")
    ).first()
    if system is None:
        system = SAPSystem(
            client_id=client.id,
            name="ECC 6.0",
            sid="ECC",
            description="Sistema SAP ECC 6.0 demo.",
        )
        session.add(system)
        session.flush()

    assessment = session.scalars(
        select(Assessment).where(
            Assessment.sap_system_id == system.id,
            Assessment.name == "Assessment01",
        )
    ).first()
    if assessment is None:
        session.add(
            Assessment(
                sap_system_id=system.id,
                name="Assessment01",
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
        version=5,  # bumped: adds SAP object parsing step for demo-source files
        description="Synthetic demo dataset: Acme (with scan + parsed objects) + Rodobens (no scan).",
        steps=[
            _seed_demo_client_system_assessment,
            _seed_demo_source_scan,
            _seed_demo_sap_objects,
            _seed_rodobens_client_system_assessment,
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
