"""Registry of seed datasets and idempotent application logic."""

from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.models import Assessment, AssessmentStatus, Client, SAPSystem, SeedRun

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


# ---------------------------------------------------------------------------
# Dataset registry
# ---------------------------------------------------------------------------

DATASETS: dict[str, SeedDataset] = {
    "demo": SeedDataset(
        name="demo",
        version=2,  # bumped: CAP-003 adds Client/SAPSystem/Assessment rows
        description="Synthetic demo dataset with one Client, SAP System and Assessment.",
        steps=[_seed_demo_client_system_assessment],
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
