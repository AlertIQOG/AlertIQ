"""One-off backfill of the RAG chunk store.

Embeds every existing Solved alert (with its notes) and every Resolved
incident into ``rag_chunks`` so the Resolution Copilot works against
historical data immediately. Idempotent — unchanged records are skipped, so
it is safe to re-run.

Usage (from ``backend/``):
    python -m app.scripts.backfill_rag
"""

from sqlmodel import Session, select

from app.core.database import engine
from app.core.logging import logger, setup_logging
from app.models.alert import Alert, AlertStatus
from app.models.incident import Incident, IncidentStage
from app.services.rag.embedding import embedding_service
from app.services.rag.indexer import index_alert, index_incident


def run() -> None:
    setup_logging()

    if not embedding_service.is_configured():
        logger.error("VOYAGE_API_KEY is not set; cannot backfill the RAG store.")
        return

    with Session(engine) as session:
        alerts = list(
            session.exec(select(Alert).where(Alert.status == AlertStatus.SOLVED)).all()
        )
        incidents = list(
            session.exec(
                select(Incident).where(Incident.stage == IncidentStage.RESOLVED)
            ).all()
        )

        alerts_changed = 0
        for alert in alerts:
            _, changed = index_alert(session, alert)
            alerts_changed += int(changed)

        incidents_changed = 0
        for incident in incidents:
            _, changed = index_incident(session, incident)
            incidents_changed += int(changed)

    logger.info(
        "Backfill complete: %d/%d alerts and %d/%d incidents (re)indexed "
        "(unchanged ones skipped).",
        alerts_changed,
        len(alerts),
        incidents_changed,
        len(incidents),
    )


if __name__ == "__main__":
    run()
