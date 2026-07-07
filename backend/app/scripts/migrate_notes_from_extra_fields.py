"""One-off migration: move legacy notes out of ``alerts.extra_fields._notes``
into the first-class ``notes`` table.

Older UI builds saved operational notes into ``extra_fields._notes`` via a plain
alert PATCH. Those notes never reached the ``notes`` table, so the Resolution
Copilot (which embeds notes from that table) could not see them. This script
copies each legacy note into a real ``Note`` row, drops the ``_notes`` key from
``extra_fields``, and re-indexes any Solved parent so its RAG chunk picks the
notes up.

Idempotent: once an alert's ``_notes`` key is removed it is no longer matched,
so re-running is safe. Preserves the original ``created_at`` when present and
falls back to author ``"legacy"`` (the old blob had no author field).

Usage (from ``backend/``, against whichever DB holds the data — e.g. prod):
    python -m app.scripts.migrate_notes_from_extra_fields          # apply
    python -m app.scripts.migrate_notes_from_extra_fields --dry-run  # preview
"""

import sys
from datetime import datetime

from sqlalchemy import func
from sqlmodel import Session, select

from app.core.database import engine
from app.core.logging import logger, setup_logging
from app.models.alert import Alert, AlertStatus
from app.models.note import Note
from app.services.rag.indexer import safe_index_alert


def _parse_created_at(raw: object) -> datetime | None:
    """Best-effort parse of an ISO timestamp from the legacy blob."""
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def run(dry_run: bool = False) -> None:
    setup_logging()

    migrated_notes = 0
    migrated_alerts = 0
    solved_reindexed = 0

    with Session(engine) as session:
        # Only alerts that still carry a top-level ``_notes`` key in JSONB.
        alerts = list(
            session.exec(
                select(Alert).where(func.jsonb_exists(Alert.extra_fields, "_notes"))
            ).all()
        )

        logger.info("Found %d alert(s) with legacy _notes to migrate.", len(alerts))

        for alert in alerts:
            legacy = alert.extra_fields.get("_notes") or []
            if not isinstance(legacy, list):
                logger.warning(
                    "Alert %s: _notes is not a list (%s) — skipping.",
                    alert.id, type(legacy).__name__,
                )
                continue

            created_here = 0
            for entry in legacy:
                if not isinstance(entry, dict):
                    continue
                content = (entry.get("content") or "").strip()
                if not content:
                    continue
                note = Note(
                    alert_id=alert.id,
                    author=(entry.get("author") or "legacy"),
                    content=content,
                )
                created_at = _parse_created_at(entry.get("created_at"))
                if created_at is not None:
                    note.created_at = created_at
                session.add(note)
                created_here += 1

            # Drop the _notes key (reassigning marks the JSONB column dirty).
            alert.extra_fields = {
                k: v for k, v in alert.extra_fields.items() if k != "_notes"
            }
            session.add(alert)

            migrated_notes += created_here
            migrated_alerts += 1
            logger.info(
                "Alert %s: migrated %d note(s)%s.",
                alert.id, created_here,
                " [dry-run]" if dry_run else "",
            )

        if dry_run:
            session.rollback()
            logger.info(
                "DRY RUN — no changes committed. Would migrate %d note(s) across "
                "%d alert(s).", migrated_notes, migrated_alerts,
            )
            return

        session.commit()

        # Re-index Solved parents so their RAG chunks include the notes.
        for alert in alerts:
            fresh = session.get(Alert, alert.id)
            if fresh is not None and fresh.status == AlertStatus.SOLVED:
                safe_index_alert(session, fresh)
                solved_reindexed += 1

    logger.info(
        "Migration complete: %d note(s) across %d alert(s); %d Solved alert(s) "
        "re-indexed.", migrated_notes, migrated_alerts, solved_reindexed,
    )


if __name__ == "__main__":
    run(dry_run="--dry-run" in sys.argv)
