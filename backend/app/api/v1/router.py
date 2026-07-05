from fastapi import APIRouter, Depends

from app.api.v1 import (
    alerts,
    auth,
    correlation_rule,
    health,
    incidents,
    ingest,
    notes,
    sources,
)
from app.api.v1.dependencies import get_current_user

router = APIRouter()

# Requires a valid bearer token on every route of the router it's applied to.
# /health stays open for uptime checks, /ingest uses per-source webhook
# secrets instead, and /auth/login must be reachable to obtain a token.
protected = [Depends(get_current_user)]

router.include_router(health.router, prefix="/health", tags=["Health"])
router.include_router(auth.router, prefix="/auth", tags=["Auth"])
router.include_router(
    sources.router, prefix="/sources", tags=["Sources"], dependencies=protected
)
router.include_router(
    alerts.router, prefix="/alerts", tags=["Alerts"], dependencies=protected
)
router.include_router(
    notes.router,
    prefix="/alerts/{alert_id}/notes",
    tags=["Notes"],
    dependencies=protected,
)
router.include_router(ingest.router, prefix="/ingest", tags=["Ingest"])
router.include_router(
    incidents.router, prefix="/incidents", tags=["Incidents"], dependencies=protected
)
router.include_router(
    correlation_rule.router,
    prefix="/correlation-rules",
    tags=["Correlation Rules"],
    dependencies=protected,
)
