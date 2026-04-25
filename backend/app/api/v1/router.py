from fastapi import APIRouter

from app.api.v1 import alerts, health, sources

router = APIRouter()

router.include_router(health.router, prefix="/health", tags=["Health"])
router.include_router(sources.router, prefix="/sources", tags=["Sources"])
router.include_router(alerts.router, prefix="/alerts", tags=["Alerts"])
