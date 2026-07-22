"""
Seed two semantically-similar alerts: one Solved (indexed into RAG as a
precedent) and one Open (a query alert you can run "Generate suggestion" on).

The alerts enter the system through the real webhook ingest route
(``POST /ingest/grafana/{source_id}``, authenticated with the source's
``X-Webhook-Token``), exactly like a Grafana notification would — so they
also pass through dedup/upsert and the correlation engine.

The two alerts share message/application/component/region (so their embedded
text matches) but carry distinct fingerprints, which keeps their external_id
distinct so neither upserts over the other.

The Solved alert is marked Solved via PATCH (which triggers indexing) and gets
a resolution note — so the Resolution Copilot has a real precedent to cite
when you generate a suggestion on the Open one.

Requires a running backend and valid credentials.

Run from the backend/ directory:

    python -m scripts.send_similar_alerts
    python -m scripts.send_similar_alerts --user admin --password secret
    ALERTIQ_API=http://localhost:8000/api/v1 python -m scripts.send_similar_alerts
"""

import argparse
import os
import sys
from typing import Any

import httpx

# Shared (identity) fields — keep these equal so the alerts are "similar".
MESSAGE = "Memory usage above 80% on the auth database"
APPLICATION = "auth"
COMPONENT = "database"
REGION = "us-west-1"
SEVERITY = "Warning"  # one of: Info | Warning | Error | Critical
IMPACT = "Checkout writes slowing down risk of failed transactions"

PRECEDENT_NODE = "prod-payments-db-1"
QUERY_NODE = "prod-payments-db-2"

RESOLUTION_NOTE = {
    "author": "oncall",
    "content": (
        "Root cause: archived WAL filled the volume. Cleared old WAL segments "
        "and expanded the disk by 50GB. Write latency returned to baseline "
        "after 30m of monitoring."
    ),
}


def fingerprint(node: str) -> str:
    """Stable per-node fingerprint — becomes the alert's external_id."""
    return f"seed-copilot-{node}"


def login(client: httpx.Client, username: str, password: str) -> str:
    """Return a bearer token, exiting with the server response on failure."""
    response = client.post(
        "/auth/login", data={"username": username, "password": password}
    )
    token = response.json().get("access_token") if response.is_success else None
    if not token:
        print(f"error: login failed. Response:\n{response.text}", file=sys.stderr)
        sys.exit(1)
    return token


def get_or_create_source(client: httpx.Client) -> tuple[str, str]:
    """
    Return ``(source_id, webhook_secret)`` for a source that can ingest.

    Prefers an existing source that has a webhook secret; otherwise creates a
    demo source (creation auto-generates a secret).
    """
    sources = client.get("/sources/").raise_for_status().json()
    for source in sources:
        if source.get("webhook_secret"):
            return source["id"], source["webhook_secret"]

    print("    no source with a webhook secret found - creating one")
    created = (
        client.post(
            "/sources/", json={"name": "demo-seed", "provider_type": "grafana"}
        )
        .raise_for_status()
        .json()
    )
    return created["id"], created["webhook_secret"]


def grafana_alert(node: str) -> dict[str, Any]:
    """One firing alert in Grafana unified-alerting webhook shape."""
    return {
        "status": "firing",
        "fingerprint": fingerprint(node),
        "labels": {
            "alertname": MESSAGE,
            "severity": SEVERITY.lower(),
            "app": APPLICATION,
            "component": COMPONENT,
            "region": REGION,
            "node_name": node,
        },
        "annotations": {"impact": IMPACT},
    }


def find_alert_id(client: httpx.Client, source_id: str, node: str) -> str:
    """
    Resolve an ingested alert's id by its external_id (= our fingerprint).

    The ingest route only returns counts, so we look the alert back up.
    """
    alerts = (
        client.get("/alerts/", params={"source_id": source_id, "limit": 500})
        .raise_for_status()
        .json()
    )
    external_id = fingerprint(node)
    for alert in alerts:
        if alert["external_id"] == external_id:
            return alert["id"]
    print(
        f"error: ingested alert with external_id={external_id} not found "
        f"on source {source_id}",
        file=sys.stderr,
    )
    sys.exit(1)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed a Solved precedent + a similar Open alert for the copilot."
    )
    parser.add_argument(
        "--api",
        default=os.environ.get("ALERTIQ_API", "http://localhost:8000/api/v1"),
        help="API base URL (default: $ALERTIQ_API or http://localhost:8000/api/v1).",
    )
    parser.add_argument(
        "--user",
        default=os.environ.get("ALERTIQ_USER", "aaa"),
        help="Login username (default: $ALERTIQ_USER or 'ttt').",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("ALERTIQ_PASS", "aaaaaaaa"),
        help="Login password (default: $ALERTIQ_PASS).",
    )
    args = parser.parse_args()

    try:
        return seed(args)
    except httpx.HTTPStatusError as exc:
        print(
            f"error: {exc.request.method} {exc.request.url} failed with "
            f"HTTP {exc.response.status_code}:\n{exc.response.text}",
            file=sys.stderr,
        )
    except httpx.HTTPError as exc:
        print(f"error: request to {args.api} failed: {exc}", file=sys.stderr)
    return 1


def seed(args: argparse.Namespace) -> int:
    with httpx.Client(base_url=args.api, timeout=30) as client:
        print(f"==> Logging in as '{args.user}' at {args.api}")
        token = login(client, args.user, args.password)
        client.headers["Authorization"] = f"Bearer {token}"

        print("==> Finding a source to attach the alerts to")
        source_id, webhook_secret = get_or_create_source(client)
        print(f"    using source_id={source_id}")

        print("==> Ingesting both alerts via the Grafana webhook route")
        payload = {
            "status": "firing",
            "alerts": [grafana_alert(PRECEDENT_NODE), grafana_alert(QUERY_NODE)],
        }
        counts = (
            client.post(
                f"/ingest/grafana/{source_id}",
                json=payload,
                headers={"X-Webhook-Token": webhook_secret},
            )
            .raise_for_status()
            .json()
        )
        print(f"    ingest accepted: {counts}")

        solved_id = find_alert_id(client, source_id, PRECEDENT_NODE)
        open_id = find_alert_id(client, source_id, QUERY_NODE)

        # The Grafana normalizer doesn't map impact onto the alert column, so
        # set it here to keep the embedded precedent text complete. The Solved
        # transition (via PATCH) is what triggers RAG indexing.
        print("==> Marking the precedent Solved")
        client.patch(
            f"/alerts/{solved_id}", json={"status": "Solved", "impact": IMPACT}
        ).raise_for_status()
        client.patch(f"/alerts/{open_id}", json={"impact": IMPACT}).raise_for_status()

        # A resolution note makes it a useful precedent (and re-indexes the
        # alert with the note included, via the /notes endpoint).
        client.post(
            f"/alerts/{solved_id}/notes/", json=RESOLUTION_NOTE
        ).raise_for_status()
        print(f"    solved_id={solved_id} (Solved, indexed, 1 resolution note)")
        print(f"    open_id={open_id} (Open)")

    print()
    print("Done. Two similar alerts created:")
    print(f"  - SOLVED precedent : {solved_id}  (node {PRECEDENT_NODE})")
    print(f"  - OPEN query       : {open_id}  (node {QUERY_NODE})")
    print()
    print("Try it: open the OPEN alert in the UI and click 'Generate suggestion' -")
    print("the copilot should retrieve the SOLVED alert (and its note) as precedent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())