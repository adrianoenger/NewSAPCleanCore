"""SAP object parsing routes — trigger parsing, browse objects, object detail."""
import os

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.schemas.parsing import ParseJobRead, SAPObjectDetailRead, SAPObjectRead
from parsing.dispatcher import parse_file
from persistence.database import get_session
from persistence.models import Assessment, SAPObject, SourceFile, SourceScan
from settings import get_settings

router = APIRouter(prefix="/assessments", tags=["parsing"])


def _require_assessment(assessment_id: int, session: Session) -> Assessment:
    a = session.get(Assessment, assessment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return a


def _parse_scan_files(scan_id: int, assessment_id: int, database_url: str) -> None:
    """Background task: read + parse every ABAP/DDIC source file in a scan."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(database_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as session:
        files = list(
            session.scalars(
                select(SourceFile).where(
                    SourceFile.scan_id == scan_id,
                    SourceFile.category.in_(["abap_source", "ddic"]),
                )
            )
        )
        scan_row = session.get(SourceScan, scan_id)
        scan_root = scan_row.source_path if scan_row else ""

        for sf in files:
            abs_path = os.path.join(scan_root, sf.rel_path)
            try:
                with open(abs_path, encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
            except OSError:
                continue

            # Remove existing objects for this file to allow re-parse
            session.execute(
                select(SAPObject).where(SAPObject.source_file_id == sf.id)
            )
            existing = list(
                session.scalars(select(SAPObject).where(SAPObject.source_file_id == sf.id))
            )
            for obj in existing:
                session.delete(obj)

            parsed = parse_file(content, sf.rel_path, sf.category)
            for p in parsed:
                session.add(
                    SAPObject(
                        assessment_id=assessment_id,
                        source_file_id=sf.id,
                        object_type=p.object_type,
                        object_name=p.object_name,
                        description=p.description,
                        line_start=p.line_start,
                        line_end=p.line_end,
                        attributes=p.attributes,
                    )
                )

        session.commit()


@router.post(
    "/{assessment_id}/scans/{scan_id}/parse",
    response_model=ParseJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_parse(
    assessment_id: int,
    scan_id: int,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> ParseJobRead:
    _require_assessment(assessment_id, session)
    scan = session.get(SourceScan, scan_id)
    if scan is None or scan.assessment_id != assessment_id:
        raise HTTPException(status_code=404, detail="Scan not found")

    settings = get_settings()
    background_tasks.add_task(
        _parse_scan_files, scan_id, assessment_id, settings.database_url
    )
    return ParseJobRead(scan_id=scan_id, status="accepted")


@router.get("/{assessment_id}/objects", response_model=list[SAPObjectRead])
def list_objects(
    assessment_id: int,
    object_type: str | None = None,
    limit: int = 200,
    offset: int = 0,
    session: Session = Depends(get_session),
) -> list[SAPObject]:
    _require_assessment(assessment_id, session)
    q = select(SAPObject).where(SAPObject.assessment_id == assessment_id)
    if object_type:
        q = q.where(SAPObject.object_type == object_type)
    return list(
        session.scalars(q.order_by(SAPObject.object_name).offset(offset).limit(limit))
    )


@router.get("/{assessment_id}/objects/{object_id}", response_model=SAPObjectDetailRead)
def get_object(
    assessment_id: int,
    object_id: int,
    session: Session = Depends(get_session),
) -> SAPObject:
    _require_assessment(assessment_id, session)
    obj = session.get(SAPObject, object_id)
    if obj is None or obj.assessment_id != assessment_id:
        raise HTTPException(status_code=404, detail="SAP object not found")
    return obj
