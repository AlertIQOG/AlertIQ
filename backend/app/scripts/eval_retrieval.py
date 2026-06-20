"""Evaluate retrieval quality: precision@k / recall@k over a labeled set.

You hand-label a small relevance set: for a handful of query alerts, list the
``source_id``s of the chunks (past alerts/incidents) that *should* be retrieved.
This script runs the retriever for each query and reports how well the ranking
matches your labels, plus the similarity scores so you can tune the floor.

Labels file (JSON) — see ``eval_labels.example.json``:
    [
      {"alert_id": "<uuid>", "relevant_source_ids": ["<uuid>", "<uuid>"]},
      ...
    ]

Usage (from ``backend/``, after backfilling real data with a Voyage key):
    python -m app.scripts.eval_retrieval                       # default file + k
    python -m app.scripts.eval_retrieval my_labels.json 10     # file, k
"""

import json
import sys
import uuid
from pathlib import Path

from sqlmodel import Session

from app.core.config import settings
from app.core.database import engine
from app.core.logging import logger, setup_logging
from app.services.alert import alert_service
from app.services.rag.embedding import embedding_service
from app.services.rag.retriever import find_similar_for_alert

_DEFAULT_LABELS = Path(__file__).with_name("eval_labels.json")


def _evaluate(labels: list[dict], k: int) -> None:
    precisions: list[float] = []
    recalls: list[float] = []

    with Session(engine) as session:
        for entry in labels:
            alert_id = uuid.UUID(entry["alert_id"])
            relevant = {uuid.UUID(s) for s in entry["relevant_source_ids"]}

            alert = alert_service.get(session, id=alert_id)
            if alert is None:
                logger.warning("Skipping unknown alert %s", alert_id)
                continue

            # floor=0 so ranking quality is measured independent of the cutoff.
            _, hits = find_similar_for_alert(session, alert, top_k=k, floor=0.0)
            retrieved = [h.source_id for h in hits]
            hit_set = set(retrieved) & relevant

            precision = len(hit_set) / k if k else 0.0
            recall = len(hit_set) / len(relevant) if relevant else 0.0
            precisions.append(precision)
            recalls.append(recall)

            scores = ", ".join(
                f"{h.source_type[:3]}:{h.similarity:.3f}"
                f"{'*' if h.source_id in relevant else ''}"
                for h in hits
            )
            logger.info(
                "alert %s | P@%d=%.2f R@%d=%.2f | ranked: [%s]",
                alert_id,
                k,
                precision,
                k,
                recall,
                scores,
            )

    n = len(precisions)
    if n == 0:
        logger.error("No evaluable queries found.")
        return
    logger.info(
        "MEAN over %d queries | precision@%d=%.3f | recall@%d=%.3f "
        "(* marks a labeled-relevant hit)",
        n,
        k,
        sum(precisions) / n,
        k,
        sum(recalls) / n,
    )


def run() -> None:
    setup_logging()

    if not embedding_service.is_configured():
        logger.error("VOYAGE_API_KEY is not set; cannot run retrieval evaluation.")
        return

    path = Path(sys.argv[1]) if len(sys.argv) > 1 else _DEFAULT_LABELS
    k = int(sys.argv[2]) if len(sys.argv) > 2 else settings.RAG_TOP_K

    if not path.exists():
        logger.error(
            "Labels file %s not found. Copy eval_labels.example.json and fill it in.",
            path,
        )
        return

    labels = json.loads(path.read_text(encoding="utf-8"))
    _evaluate(labels, k)


if __name__ == "__main__":
    run()
