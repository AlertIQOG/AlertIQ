"""
Ingest endpoints — receive webhooks from external alerting providers.

Each provider gets its own route for cleaner auth, monitoring, and debugging.
The handler is intentionally thin: validate → normalize → persist → respond.

Duplicate alerts are upserted: existing alerts are updated with the latest
mutable state (severity, extra_fields, impact) from the provider rather than
being skipped.
"""

import logging

from fastapi import APIRouter, status

from app.api.v1.dependencies import DbSession, ValidWebhookSourceId
from app.providers.grafana import GrafanaWebhook, grafana_normalizer
from app.providers.prometheus import PrometheusWebhook, prometheus_normalizer
from app.services.alert import alert_service

logger = logging.getLogger("alertiq.ingest")

router = APIRouter()


@router.post(
    "/grafana/{source_id}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest alerts from Grafana Alertmanager",
    response_description="Accepted — returns counts of created and updated alerts.",
)
def ingest_grafana(
    *,
    session: DbSession,
    source_id: ValidWebhookSourceId,
    payload: GrafanaWebhook,
) -> dict:
    """
    Receive a Grafana unified-alerting webhook and persist the alerts.

    - Authenticates the request via the source's ``X-Webhook-Token`` secret
      (which also validates that the ``source_id`` exists).
    - Normalizes the Grafana payload into ``AlertCreate`` objects.
    - Upserts each alert: new alerts are inserted, existing ones are updated.
    - Returns ``202 Accepted`` with ``{created, updated}`` counts.
    """
    alert_creates = grafana_normalizer.normalize(source_id, payload)

    created = 0
    updated = 0
    for alert_create in alert_creates:
        _, is_new = alert_service.upsert(session, obj_in=alert_create)
        if is_new:
            created += 1
        else:
            updated += 1
            logger.info(
                "Existing alert updated — source=%s fingerprint=%s external_id=%s",
                source_id,
                alert_create.extra_fields.get("fingerprint", "?"),
                alert_create.external_id,
            )

    logger.info(
        "Grafana ingest complete — source=%s total=%d created=%d updated=%d",
        source_id,
        len(alert_creates),
        created,
        updated,
    )

    return {"created": created, "updated": updated}


@router.post(
    "/prometheus/{source_id}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest alerts from Prometheus Alertmanager",
    response_description="Accepted — returns counts of created and updated alerts.",
)
def ingest_prometheus(
    *,
    session: DbSession,
    source_id: ValidWebhookSourceId,
    payload: PrometheusWebhook,
) -> dict:
    """
    Receive a Prometheus Alertmanager webhook and persist the alerts.

    Authenticates via the source's ``X-Webhook-Token`` secret.
    Upserts each alert: new alerts are inserted, existing ones are updated.
    Returns ``202 Accepted`` with ``{created, updated}`` counts.
    """
    alert_creates = prometheus_normalizer.normalize(source_id, payload)

    created = 0
    updated = 0
    for alert_create in alert_creates:
        _, is_new = alert_service.upsert(session, obj_in=alert_create)
        if is_new:
            created += 1
        else:
            updated += 1
            logger.info(
                "Existing alert updated — source=%s fingerprint=%s external_id=%s",
                source_id,
                alert_create.extra_fields.get("fingerprint", "?"),
                alert_create.external_id,
            )

    logger.info(
        "Prometheus ingest complete — source=%s total=%d created=%d updated=%d",
        source_id,
        len(alert_creates),
        created,
        updated,
    )
    return {"created": created, "updated": updated}
