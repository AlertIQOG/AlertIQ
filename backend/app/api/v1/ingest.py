"""
Ingest endpoints — receive webhooks from external alerting providers.

Each provider gets its own route for cleaner auth, monitoring, and debugging.
The handler is intentionally thin: validate → normalize → persist → correlate → respond.

Duplicate alerts are upserted: existing alerts are updated with the latest
mutable state (severity, extra_fields, impact) from the provider rather than
being skipped.

After each alert is persisted it is run through the correlation engine, which
may fold it into an ``AggregatedAlert`` (see
:mod:`app.services.correlation_engine`).  Correlation is best-effort: a failure
there is logged but never fails the webhook or loses the already-persisted alert.
"""

import logging
import uuid

from fastapi import APIRouter, status

from app.api.v1.dependencies import DbSession, ValidWebhookSourceId
from app.providers.grafana import GrafanaWebhook, grafana_normalizer
from app.providers.prometheus import PrometheusWebhook, prometheus_normalizer
from app.schemas.alert import AlertCreate
from app.services.alert import alert_service
from app.services.correlation_engine import correlation_engine

logger = logging.getLogger("alertiq.ingest")

router = APIRouter()


def _persist_and_correlate(
    session: DbSession,
    *,
    source_id: uuid.UUID,
    provider: str,
    alert_creates: list[AlertCreate],
) -> dict:
    """
    Upsert each normalized alert and run it through the correlation engine.

    Returns ``{created, updated, aggregated}`` counts, where ``aggregated`` is
    the number of alerts that were folded into (or opened) an aggregate.
    """
    created = 0
    updated = 0
    aggregated = 0

    for alert_create in alert_creates:
        alert, is_new = alert_service.upsert(session, obj_in=alert_create)
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

        # Best-effort correlation: never let a rule error drop the alert.
        try:
            if correlation_engine.process_alert(session, alert) is not None:
                aggregated += 1
        except Exception:  # noqa: BLE001 — correlation must not break ingest
            session.rollback()
            logger.exception(
                "Correlation failed — source=%s alert=%s (alert persisted, left standalone)",
                source_id,
                alert.id,
            )

    logger.info(
        "%s ingest complete — source=%s total=%d created=%d updated=%d aggregated=%d",
        provider,
        source_id,
        len(alert_creates),
        created,
        updated,
        aggregated,
    )
    return {"created": created, "updated": updated, "aggregated": aggregated}


@router.post(
    "/grafana/{source_id}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest alerts from Grafana Alertmanager",
    response_description="Accepted — returns counts of created, updated and aggregated alerts.",
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
    - Runs each alert through the correlation engine (may aggregate it).
    - Returns ``202 Accepted`` with ``{created, updated, aggregated}`` counts.
    """
    alert_creates = grafana_normalizer.normalize(source_id, payload)

    return _persist_and_correlate(
        session,
        source_id=source_id,
        provider="Grafana",
        alert_creates=alert_creates,
    )


@router.post(
    "/prometheus/{source_id}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest alerts from Prometheus Alertmanager",
    response_description="Accepted — returns counts of created, updated and aggregated alerts.",
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
    Upserts each alert, runs it through the correlation engine, and returns
    ``202 Accepted`` with ``{created, updated, aggregated}`` counts.
    """
    alert_creates = prometheus_normalizer.normalize(source_id, payload)

    return _persist_and_correlate(
        session,
        source_id=source_id,
        provider="Prometheus",
        alert_creates=alert_creates,
    )
