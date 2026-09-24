"""CRUD-light routes for Client and Assessment entities (SPRINT-04: Assessment-centric)."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.schemas.client_system_assessment import (
    AssessmentCreate,
    AssessmentListItem,
    AssessmentRead,
    ClientCreate,
    ClientRead,
)
from persistence.database import get_session
from persistence.models import Assessment, AssessmentStatus, Client

router = APIRouter(tags=["clients"])


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------


@router.post("/clients", response_model=ClientRead, status_code=status.HTTP_201_CREATED)
def create_client(body: ClientCreate, session: Session = Depends(get_session)) -> Client:
    client = Client(name=body.name, description=body.description)
    session.add(client)
    session.commit()
    session.refresh(client)
    return client


@router.get("/clients", response_model=list[ClientRead])
def list_clients(session: Session = Depends(get_session)) -> list[Client]:
    return list(session.scalars(select(Client).order_by(Client.name)))


@router.get("/clients/{client_id}", response_model=ClientRead)
def get_client(client_id: int, session: Session = Depends(get_session)) -> Client:
    client = session.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


# ---------------------------------------------------------------------------
# Assessments (standalone — not nested under client/system)
# ---------------------------------------------------------------------------


@router.get("/assessments", response_model=list[AssessmentListItem])
def list_assessments(
    client_id: int | None = Query(default=None),
    name: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[AssessmentListItem]:
    q = select(Assessment, Client.name.label("client_name")).join(
        Client, Assessment.client_id == Client.id
    )
    if client_id is not None:
        q = q.where(Assessment.client_id == client_id)
    if name is not None:
        q = q.where(Assessment.name.ilike(f"%{name}%"))
    q = q.order_by(Assessment.created_at.desc())
    rows = session.execute(q).all()
    return [
        AssessmentListItem(
            id=a.id,
            client_id=a.client_id,
            client_name=cn,
            name=a.name,
            sap_source_system=a.sap_source_system,
            status=a.status,
            created_at=a.created_at,
        )
        for a, cn in rows
    ]


@router.post("/assessments", response_model=AssessmentRead, status_code=status.HTTP_201_CREATED)
def create_assessment(
    body: AssessmentCreate, session: Session = Depends(get_session)
) -> Assessment:
    client = session.get(Client, body.client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    assessment = Assessment(
        client_id=body.client_id,
        name=body.name,
        sap_source_system=body.sap_source_system,
        description=body.description,
        status=AssessmentStatus.CREATED.value,
    )
    session.add(assessment)
    session.commit()
    session.refresh(assessment)
    return assessment


@router.get("/assessments/{assessment_id}", response_model=AssessmentRead)
def get_assessment(
    assessment_id: int, session: Session = Depends(get_session)
) -> Assessment:
    assessment = session.get(Assessment, assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return assessment
