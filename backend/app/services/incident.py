"""Incident-specific service logic."""

import uuid
from typing import Any

from sqlmodel import Session, select

from app.models.incident import Incident, IncidentStage
from app.services.base import CRUDBase
from app.services.events import event_bus
from app.services.rag.indexer import safe_index_incident


class IncidentService(CRUDBase[Incident]):
    """Generic CRUD plus a best-effort index when an incident is Resolved."""

    def open_incident_by_alert(self, session: Session) -> dict[uuid.UUID, uuid.UUID]:
        """Map every alert with an unresolved incident to that incident's id.

        Resolved incidents are excluded — once resolved, an alert may legitimately
        be promoted again. Unresolved incidents are a naturally small set, so this
        is a single query rather than one lookup per alert.
        """
        incidents = session.exec(
            select(Incident).where(Incident.stage != IncidentStage.RESOLVED)
        ).all()

        mapping: dict[uuid.UUID, uuid.UUID] = {}
        for incident in incidents:
            linked = list(incident.linked_alert_ids or [])
            if incident.linked_alert_id is not None:
                linked.append(incident.linked_alert_id)
            for raw in linked:
                try:
                    mapping.setdefault(uuid.UUID(str(raw)), incident.id)
                except (ValueError, TypeError):
                    continue
        return mapping

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
