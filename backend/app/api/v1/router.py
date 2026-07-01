from fastapi import APIRouter
from app.api.v1 import alerts, correlation_rule, health, incidents, ingest, notes, sources

router = APIRouter()

router.include_router(health.router, prefix="/health", tags=["Health"])
router.include_router(sources.router, prefix="/sources", tags=["Sources"])
router.include_router(alerts.router, prefix="/alerts", tags=["Alerts"])
router.include_router(notes.router, prefix="/alerts/{alert_id}/notes", tags=["Notes"])
router.include_router(ingest.router, prefix="/ingest", tags=["Ingest"])
router.include_router(incidents.router, prefix="/incidents", tags=["Incidents"])
router.include_router(correlation_rule.router, prefix="/correlation-rule", tags=["Correlation Rule"],)
