"""Incident-specific service logic."""

from typing import Any

from sqlmodel import Session

from app.models.incident import Incident, IncidentStage
from app.services.base import CRUDBase
from app.services.events import event_bus
from app.services.rag.indexer import safe_index_incident


class IncidentService(CRUDBase[Incident]):
    """Generic CRUD plus a best-effort index when an incident is Resolved."""

    def create(self, session: Session, *, obj_in: Incident) -> Incident:
        created = super().create(session, obj_in=obj_in)
        if created.stage == IncidentStage.RESOLVED:
            safe_index_incident(session, created)
        event_bus.publish("incident.created", created.id)
        return created

    def update(
        self, session: Session, *, db_obj: Incident, update_data: dict[str, Any]
    ) -> Incident:
        updated = super().update(session, db_obj=db_obj, update_data=update_data)
        if updated.stage == IncidentStage.RESOLVED:
            safe_index_incident(session, updated)
        event_bus.publish("incident.updated", updated.id)
        return updated

    def remove(self, session: Session, *, id: Any) -> Incident | None:
        removed = super().remove(session, id=id)
        if removed is not None:
            event_bus.publish("incident.deleted", id)
        return removed


incident_service = IncidentService(Incident)
