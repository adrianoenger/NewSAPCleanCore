"""CLI: `python -m seed apply [dataset]` / `python -m seed status`."""

import argparse

from persistence.database import get_session_factory
from seed.registry import DATASETS, apply_dataset, list_runs


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m seed")
    sub = parser.add_subparsers(dest="command", required=True)
    apply_cmd = sub.add_parser("apply", help="apply a synthetic seed dataset (idempotent)")
    apply_cmd.add_argument("dataset", nargs="?", default="demo", choices=sorted(DATASETS))
    sub.add_parser("status", help="list applied seed datasets")
    args = parser.parse_args()

    with get_session_factory()() as session:
        if args.command == "apply":
            ran = apply_dataset(session, args.dataset)
            version = DATASETS[args.dataset].version
            state = "applied" if ran else "already up to date"
            print(f"seed '{args.dataset}' v{version}: {state}")
        else:
            runs = list_runs(session)
            if not runs:
                print("no seed datasets applied")
            for run in runs:
                print(f"{run.name} v{run.version} applied_at={run.applied_at.isoformat()}")


if __name__ == "__main__":
    main()
