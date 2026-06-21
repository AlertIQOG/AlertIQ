"""One-off backfill of the RAG chunk store.

Embeds every existing Solved alert (with its notes) and every Resolved
incident into ``rag_chunks`` so the Resolution Copilot works against
historical data immediately. Idempotent — unchanged records are skipped, so
it is safe to re-run.

Usage (from ``backend/``):
    python -m app.scripts.backfill_rag
"""

from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app.core.database import engine
from app.core.logging import logger, setup_logging
from app.models.alert import Alert, AlertStatus
from app.models.incident import Incident, IncidentStage
from app.services.rag.embedding import embedding_service
from app.services.rag.flatten import flatten_alert, flatten_incident
from app.services.rag.indexer import index_many


def run() -> None:
    setup_logging()

    if not embedding_service.is_configured():
        logger.error(
            "Embedding provider is not configured; cannot backfill the RAG store."
        )
        return

    # Load all source records and flatten them in one short-lived session, then
    # close it — index_many manages its own per-batch sessions during the long,
    # rate-limited embedding loop (so a dropped idle connection can't poison it).
    with Session(engine) as session:
        # Eager-load notes to avoid an N+1 round-trip per alert over the network.
        alerts = list(
            session.exec(
                select(Alert)
                .where(Alert.status == AlertStatus.SOLVED)
                .options(selectinload(Alert.notes))
            ).all()
        )
        incidents = list(
            session.exec(
                select(Incident).where(Incident.stage == IncidentStage.RESOLVED)
            ).all()
        )

        items: list[tuple[str, object, int, str]] = []
        for alert in alerts:
            text = flatten_alert(alert, list(alert.notes))
            items.append(("alert", alert.id, 0, text))
        for incident in incidents:
            items.append(("incident", incident.id, 0, flatten_incident(incident)))

    logger.info(
        "Backfill: %d Solved alerts + %d Resolved incidents to consider.",
        len(alerts),
        len(incidents),
    )
    indexed = index_many(engine, items)

    logger.info(
        "Backfill complete: %d chunk(s) (re)embedded, %d unchanged skipped.",
        indexed,
        len(items) - indexed,
    )


if __name__ == "__main__":
    run()
