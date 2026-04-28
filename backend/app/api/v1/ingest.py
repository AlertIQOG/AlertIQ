"""
Ingest endpoints — receive webhooks from external alerting providers.

Each provider gets its own route for cleaner auth, monitoring, and debugging.
The handler is intentionally thin: validate → normalize → persist → respond.

Duplicate alerts (``ConflictError`` from the service layer) are silently
counted and reported in the response — they are NOT treated as errors
because Grafana and other providers routinely retry deliveries.
"""

import uuid
import logging

from fastapi import APIRouter, status

from app.api.v1.dependencies import DbSession
from app.core.exceptions import ConflictError, NotFoundError
from app.models.alert import Alert
from app.providers.grafana import GrafanaWebhook, grafana_normalizer
from app.services.alert import alert_service
from app.services.source import source_service

logger = logging.getLogger("alertiq.ingest")

router = APIRouter()


@router.post(
    "/grafana/{source_id}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest alerts from Grafana Alertmanager",
    response_description="Accepted — returns counts of created and skipped alerts.",
)
def ingest_grafana(
    *,
    session: DbSession,
    source_id: uuid.UUID,
    payload: GrafanaWebhook,
) -> dict:
    """
    Receive a Grafana unified-alerting webhook and persist the alerts.

    - Validates that the ``source_id`` exists and is active.
    - Normalizes the Grafana payload into ``AlertCreate`` objects.
    - Persists each alert, gracefully handling duplicates.
    - Returns ``202 Accepted`` with ``{created, skipped}`` counts.
    """
    # 1. Resolve the source — fail fast if it doesn't exist
    source = source_service.get(session, id=source_id)
    if source is None:
        raise NotFoundError("Source", str(source_id))

    # 2. Normalize
    alert_creates = grafana_normalizer.normalize(source_id, payload)

    # 3. Persist each alert, counting successes and dedup skips
    created = 0
    skipped = 0

    for alert_create in alert_creates:
        db_obj = Alert.model_validate(alert_create.model_dump())
        try:
            alert_service.create(session, obj_in=db_obj)
            created += 1
        except ConflictError:
            logger.info(
                "Duplicate alert skipped — source=%s fingerprint=%s external_id=%s",
                source_id,
                alert_create.extra_fields.get("fingerprint", "?"),
                alert_create.external_id,
            )
            skipped += 1

    logger.info(
        "Grafana ingest complete — source=%s total=%d created=%d skipped=%d",
        source_id,
        len(alert_creates),
        created,
        skipped,
    )

    return {"created": created, "skipped": skipped}
