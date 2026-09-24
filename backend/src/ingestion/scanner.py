"""Background directory scanner — walks a source tree, hashes files, persists SourceFile rows.

Supports resuming interrupted scans: files already persisted for a scan are skipped.
"""

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ingestion.classifier import classify
from persistence.models import ScanStatus, SourceFile, SourceScan


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def run_scan(scan_id: int, source_path: str, assessment_id: int, db_url: str) -> None:
    """Synchronous scan executed in a background thread. Resumes automatically if interrupted."""
    engine = create_engine(db_url)
    with Session(engine) as session:
        scan = session.get(SourceScan, scan_id)
        if scan is None:
            return

        root = Path(source_path)
        if not root.is_dir():
            scan.status = ScanStatus.FAILED.value
            scan.error = f"Path not found or not a directory: {source_path}"
            session.commit()
            return

        try:
            root_real = root.resolve(strict=True)

            # Resume: collect rel_paths already persisted for this scan
            existing_rels: set[str] = set(
                session.scalars(
                    select(SourceFile.rel_path).where(SourceFile.scan_id == scan_id)
                )
            )

            scan.status = ScanStatus.SCANNING.value
            session.commit()

            # Collect all candidate files (respects symlink safety)
            all_files: list[Path] = []
            for abs_path in sorted(root_real.rglob("*")):
                if not abs_path.is_file():
                    continue
                try:
                    abs_path.resolve(strict=True).relative_to(root_real)
                except (OSError, ValueError):
                    continue
                all_files.append(abs_path)

            scan.total_files = len(all_files) + len(existing_rels)
            session.commit()

            count = len(existing_rels)  # files already done in a previous run
            batch: list[SourceFile] = []

            for abs_path in all_files:
                rel = str(abs_path.relative_to(root_real)).replace(os.sep, "/")
                if rel in existing_rels:
                    continue  # already scanned in a previous run

                stat = abs_path.stat()
                sha = _sha256(abs_path)
                category = classify(rel)
                batch.append(
                    SourceFile(
                        scan_id=scan_id,
                        assessment_id=assessment_id,
                        rel_path=rel,
                        size_bytes=stat.st_size,
                        mtime=stat.st_mtime,
                        sha256=sha,
                        category=category,
                    )
                )
                count += 1

                if len(batch) >= 10:
                    session.add_all(batch)
                    batch.clear()
                    scan.scanned_files = count
                    session.commit()

            if batch:
                session.add_all(batch)
            scan.status = ScanStatus.COMPLETED.value
            scan.scanned_files = count
            scan.completed_at = datetime.now(timezone.utc)
            session.commit()

        except Exception as exc:  # noqa: BLE001
            scan.status = ScanStatus.FAILED.value
            scan.error = str(exc)
            session.commit()
