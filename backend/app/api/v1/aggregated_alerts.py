"""
Aggregated-alert endpoints — read-only view over the correlation engine's output.

Aggregated alerts are produced automatically by the ingest → correlation flow
(see :mod:`app.services.correlation_engine`); they are not created directly via
the API, so only list/get are exposed here.
"""

import uuid

from fastapi import APIRouter, Query

from app.api.v1.dependencies import DbSession
from app.core.exceptions import NotFoundError
from app.models.aggregated_alert import AggregatedAlertStatus
from app.schemas.aggregated_alert import AggregatedAlertRead
from app.services.aggregated_alert import aggregated_alert_service

router = APIRouter()


@router.get("/", response_model=list[AggregatedAlertRead])
def list_aggregated_alerts(
    *,
    session: DbSession,
    status: AggregatedAlertStatus | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[AggregatedAlertRead]:
    """
    List aggregated alerts, optionally filtered by ``status`` (Open/Closed).

    With no filter, the newest aggregates are returned first.
    """
    if status is AggregatedAlertStatus.OPEN:
        return aggregated_alert_service.list_open(session, limit=limit)

    return aggregated_alert_service.get_filtered(
        session,
        filters={"status": status} if status is not None else {},
        skip=skip,
        limit=limit,
        order_by="last_seen",
        order_desc=True,
    )


@router.get("/{aggregate_id}", response_model=AggregatedAlertRead)
def get_aggregated_alert(
    *,
    session: DbSession,
    aggregate_id: uuid.UUID,
) -> AggregatedAlertRead:
    """Retrieve a single aggregated alert by its UUID."""
    aggregate = aggregated_alert_service.get(session, id=aggregate_id)
    if not aggregate:
        raise NotFoundError("AggregatedAlert", str(aggregate_id))
    return aggregate
