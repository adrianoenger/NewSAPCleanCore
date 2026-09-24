"""CRUD-light routes for Client, SAPSystem and Assessment entities."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from api.schemas.client_system_assessment import (
    AssessmentCreate,
    AssessmentRead,
    ClientCreate,
    ClientRead,
    SAPSystemCreate,
    SAPSystemRead,
)
from persistence.database import get_session
from persistence.models import Assessment, AssessmentStatus, Client, SAPSystem

router = APIRouter(prefix="/clients", tags=["clients"])


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------


@router.post("", response_model=ClientRead, status_code=status.HTTP_201_CREATED)
def create_client(body: ClientCreate, session: Session = Depends(get_session)) -> Client:
    client = Client(name=body.name, description=body.description)
    session.add(client)
    session.commit()
    session.refresh(client)
    return client


@router.get("", response_model=list[ClientRead])
def list_clients(session: Session = Depends(get_session)) -> list[Client]:
    return list(session.scalars(select(Client).order_by(Client.name)))


@router.get("/{client_id}", response_model=ClientRead)
def get_client(client_id: int, session: Session = Depends(get_session)) -> Client:
    client = session.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


# ---------------------------------------------------------------------------
# SAP Systems (nested under client)
# ---------------------------------------------------------------------------


@router.post(
    "/{client_id}/systems",
    response_model=SAPSystemRead,
    status_code=status.HTTP_201_CREATED,
)
def create_system(
    client_id: int, body: SAPSystemCreate, session: Session = Depends(get_session)
) -> SAPSystem:
    client = session.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    system = SAPSystem(
        client_id=client_id,
        name=body.name,
        sid=body.sid,
        description=body.description,
    )
    session.add(system)
    session.commit()
    session.refresh(system)
    return system


@router.get("/{client_id}/systems", response_model=list[SAPSystemRead])
def list_systems(
    client_id: int, session: Session = Depends(get_session)
) -> list[SAPSystem]:
    client = session.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return list(
        session.scalars(
            select(SAPSystem)
            .where(SAPSystem.client_id == client_id)
            .order_by(SAPSystem.name)
        )
    )


# ---------------------------------------------------------------------------
# Assessments (nested under system)
# ---------------------------------------------------------------------------


@router.post(
    "/{client_id}/systems/{system_id}/assessments",
    response_model=AssessmentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_assessment(
    client_id: int,
    system_id: int,
    body: AssessmentCreate,
    session: Session = Depends(get_session),
) -> Assessment:
    system = session.get(SAPSystem, system_id)
    if system is None or system.client_id != client_id:
        raise HTTPException(status_code=404, detail="SAP system not found")
    assessment = Assessment(
        sap_system_id=system_id,
        name=body.name,
        description=body.description,
        status=AssessmentStatus.CREATED.value,
    )
    session.add(assessment)
    session.commit()
    session.refresh(assessment)
    return assessment


@router.get(
    "/{client_id}/systems/{system_id}/assessments",
    response_model=list[AssessmentRead],
)
def list_assessments(
    client_id: int,
    system_id: int,
    session: Session = Depends(get_session),
) -> list[Assessment]:
    system = session.get(SAPSystem, system_id)
    if system is None or system.client_id != client_id:
        raise HTTPException(status_code=404, detail="SAP system not found")
    return list(
        session.scalars(
            select(Assessment)
            .where(Assessment.sap_system_id == system_id)
            .order_by(Assessment.name)
        )
    )


@router.get(
    "/{client_id}/systems/{system_id}/assessments/{assessment_id}",
    response_model=AssessmentRead,
)
def get_assessment(
    client_id: int,
    system_id: int,
    assessment_id: int,
    session: Session = Depends(get_session),
) -> Assessment:
    system = session.get(SAPSystem, system_id)
    if system is None or system.client_id != client_id:
        raise HTTPException(status_code=404, detail="SAP system not found")
    assessment = session.get(Assessment, assessment_id)
    if assessment is None or assessment.sap_system_id != system_id:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return assessment
