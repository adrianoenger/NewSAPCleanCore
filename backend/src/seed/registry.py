"""Registry of seed datasets and idempotent application logic."""

from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.models import SeedRun

SeedStep = Callable[[Session], None]


@dataclass(frozen=True)
class SeedDataset:
    name: str
    version: int
    description: str
    steps: list[SeedStep] = field(default_factory=list)


# Each step must be idempotent (upsert by natural key) so re-applying a newer version is safe.
DATASETS: dict[str, SeedDataset] = {
    "demo": SeedDataset(
        name="demo",
        version=1,
        description="Synthetic demo dataset; domain entities are added from SPRINT-01 onward.",
        steps=[],
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
