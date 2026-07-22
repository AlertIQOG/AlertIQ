"""Incident endpoints."""

import uuid

from fastapi import APIRouter, Depends, status

from app.api.v1.dependencies import DbSession, PaginationParams
from app.core.exceptions import ConflictError, NotFoundError
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
    """Create an incident, refusing to double-book an already-linked alert."""
    data = body.model_dump()

    # Every promoted alert is linked; fall back to the single id for older clients.
    linked = list(data.get("linked_alert_ids") or [])
    if not linked and data.get("linked_alert_id") is not None:
        linked = [data["linked_alert_id"]]
    if linked and data.get("linked_alert_id") is None:
        data["linked_alert_id"] = linked[0]

    already_open = incident_service.open_incident_by_alert(session)
    clashing = [aid for aid in linked if aid in already_open]
    if clashing:
        raise ConflictError(
            f"{len(clashing)} of the selected alert(s) already have an open incident."
        )

    data["linked_alert_ids"] = [str(aid) for aid in linked]
    db_obj = Incident.model_validate(data)
    return incident_service.create(session, obj_in=db_obj)


@router.patch("/{incident_id}", response_model=IncidentRead)
def update_incident(*, session: DbSession, incident_id: uuid.UUID, body: IncidentUpdate) -> IncidentRead:
    incident = incident_service.get(session, id=incident_id)
    if not incident:
        raise NotFoundError("Incident", str(incident_id))
    update_data = body.model_dump(exclude_unset=True)
    return incident_service.update(session, db_obj=incident, update_data=update_data)


@router.delete("/{incident_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_incident(*, session: DbSession, incident_id: uuid.UUID) -> None:
    incident = incident_service.remove(session, id=incident_id)
    if not incident:
        raise NotFoundError("Incident", str(incident_id))
