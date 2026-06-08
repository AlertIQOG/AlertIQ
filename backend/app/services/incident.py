from app.models.incident import Incident
from app.services.base import CRUDBase

incident_service = CRUDBase(Incident)
