"""Incident endpoints."""

import uuid

from fastapi import APIRouter, Depends, status

from app.api.v1.dependencies import DbSession, PaginationParams
from app.core.exceptions import NotFoundError
from app.models.incident import Incident
from app.schemas.incident import IncidentCreate, IncidentRead, IncidentUpdate
from app.services.incident import incident_service

router = APIRouter()


@router.get("/", response_model=list[IncidentRead])
def list_incidents(*, session: DbSession, pagination: PaginationParams = Depends()) -> list[IncidentRead]:
    return incident_service.get_multi(session, skip=pagination.skip, limit=pagination.limit)


@router.get("/{incident_id}", response_model=IncidentRead)
def get_incident(*, session: DbSession, incident_id: uuid.UUID) -> IncidentRead:
    incident = incident_service.get(session, id=incident_id)
    if not incident:
        raise NotFoundError("Incident", str(incident_id))
    return incident


@router.post("/", response_model=IncidentRead, status_code=status.HTTP_201_CREATED)
def create_incident(*, session: DbSession, body: IncidentCreate) -> IncidentRead:
    db_obj = Incident.model_validate(body.model_dump())
    return incident_service.create(session, obj_in=db_obj)


@router.patch("/{incident_id}", response_model=IncidentRead)
def update_incident(*, session: DbSession, incident_id: uuid.UUID, body: IncidentUpdate) -> IncidentRead:
    incident = incident_service.get(session, id=incident_id)
    if not incident:
        raise NotFoundError("Incident", str(incident_id))
    update_data = body.model_dump(exclude_unset=True)
    return incident_service.update(session, db_obj=incident, update_data=update_data)
