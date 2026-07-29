"""
Seed a burst of alerts that the correlation engine should fold into aggregates.

The alerts enter through the real webhook ingest route
(``POST /ingest/grafana/{source_id}``, authenticated with the source's
``X-Webhook-Token``), so they pass through normalization, dedup/upsert and the
correlation engine exactly like a real Grafana notification would.

Create this rule manually first (UI → Correlation → Create Correlation Rule):

    Rule Name        : DB CPU saturation - Grafana
    Rule Scope       : Source = Grafana,  Region = Any
    Trigger Logic    : IF  component   Equals        database
                       AND cpu_usage   Greater than  90
    Group Alerts By  : region, application
    Time Window      : 30 Minutes
    Actions          : Aggregate Alerts   (leave "Send Email" off - no SMTP needed)

What this script then sends (7 alerts, one batch):

    us-east-1 / payments  x4  (cpu 93/96/91/99, one Critical)  -> aggregate #1, count 4
    eu-west-1 / payments  x2  (cpu 94/97)                      -> aggregate #2, count 2
    us-east-1 / payments  x1  (cpu 35)   condition fails       -> stays standalone
    us-east-1 / checkout  x1  (component=frontend) fails       -> stays standalone

Re-running with the same ``--batch`` is a no-op for the aggregates: the same
fingerprints upsert onto the same alerts, and the engine refuses to count a
member twice. Pass a new ``--batch`` value to add fresh members to the *same*
aggregates (count grows) while the 30-minute window is still open.

Each aggregate shows up in the **alerts feed** as a summary row badged
``AGG · n`` — the same treatment a hand-picked group gets — with its members
dismissed underneath it and reachable from the details panel.

One thing that can still make a working run look wrong: **another rule can
claim these alerts.** ``process_alert`` stops at the first active rule that
aggregates, and ``get_active`` applies no ordering — an older, broader rule
(e.g. one scoped to ``region=eu-west-1`` grouping only by ``region``) will win
and produce a different group key. Disable competing rules for a clean demo;
the summary below flags when this happens.

Requires a running backend and valid credentials.

Run from the backend/ directory:

    python -m scripts.send_correlated_alerts
    python -m scripts.send_correlated_alerts --batch 2
    python -m scripts.send_correlated_alerts --user admin --password secret
    ALERTIQ_API=http://localhost:8000/api/v1 python -m scripts.send_correlated_alerts
"""

import argparse
import os
import sys
from typing import Any, NamedTuple

import httpx


class AlertSpec(NamedTuple):
    """One alert to send, plus what we expect the engine to do with it."""

    node: str
    region: str
    application: str
    component: str
    cpu_usage: str
    severity: str  # grafana label value: info | warning | error | critical
    expectation: str  # human-readable note printed in the summary


# The four fields the rule cares about: component (condition), cpu_usage
# (condition), region + application (group_by). Everything else is flavour.
ALERT_SPECS: list[AlertSpec] = [
    # ── Group 1 — region=us-east-1|application=payments ────────────────
    # Four distinct alerts, all matching. The Critical one escalates the
    # aggregate's severity (merge_severity never de-escalates).
    AlertSpec("prod-payments-db-1", "us-east-1", "payments", "database", "93",
              "warning", "aggregate #1"),
    AlertSpec("prod-payments-db-2", "us-east-1", "payments", "database", "96",
              "error", "aggregate #1"),
    AlertSpec("prod-payments-db-3", "us-east-1", "payments", "database", "91",
              "warning", "aggregate #1"),
    AlertSpec("prod-payments-db-4", "us-east-1", "payments", "database", "99",
              "critical", "aggregate #1 (escalates severity to Critical)"),
    # ── Group 2 — region=eu-west-1|application=payments ────────────────
    # Same rule, different group_by values -> a second, separate aggregate.
    AlertSpec("eu-payments-db-1", "eu-west-1", "payments", "database", "94",
              "warning", "aggregate #2"),
    AlertSpec("eu-payments-db-2", "eu-west-1", "payments", "database", "97",
              "error", "aggregate #2"),
    # ── Control alerts — must NOT be aggregated ────────────────────────
    AlertSpec("prod-payments-db-9", "us-east-1", "payments", "database", "35",
              "info", "standalone (cpu_usage <= 90)"),
    AlertSpec("prod-checkout-web-1", "us-east-1", "checkout", "frontend", "98",
              "error", "standalone (component != database)"),
]

EXPECTED_AGGREGATED = sum(
    1 for spec in ALERT_SPECS if spec.expectation.startswith("aggregate")
)

# Group keys the engine builds from group_by = ["region", "application"] — but
# only if *this* rule is the first active one to match. Reporting follows the
# alert ids instead, so a different rule winning the alert is visible rather
# than looking like "nothing aggregated".
EXPECTED_GROUP_KEYS = {
    "region=us-east-1|application=payments": 4,
    "region=eu-west-1|application=payments": 2,
}


def fingerprint(spec: AlertSpec, batch: str) -> str:
    """Stable per-node fingerprint — becomes the alert's external_id."""
    return f"seed-correlation-{batch}-{spec.node}"


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


def warn_if_no_matching_rule(client: httpx.Client) -> None:
    """
    Print the enabled rules so a missing/mistyped rule is obvious before we send.

    The check mirrors the engine: an enabled rule whose scope is empty or
    ``source=Grafana``, and whose conditions only reference fields we send.
    """
    response = client.get("/correlation-rules/", params={"enabled": True})
    rules = response.raise_for_status().json()
    if not rules:
        print("    WARNING: no enabled correlation rules - nothing will aggregate.")
        return

    sent_fields = {
        "component", "cpu_usage", "region", "application", "severity", "source"
    }
    for rule in rules:
        scope_source = rule["scope"].get("source")
        fields = {condition["field"] for condition in rule["conditions"]}
        plausible = (
            scope_source in (None, "Grafana")
            and fields <= sent_fields
            and set(rule["group_by"]) <= sent_fields
        )
        flag = "OK " if plausible else "?? "
        print(
            f"    {flag}{rule['name']!r} scope={rule['scope']} "
            f"group_by={rule['group_by']} actions={rule['actions']} "
            f"window={rule['time_window_minutes']}m"
        )


def grafana_alert(spec: AlertSpec, batch: str) -> dict[str, Any]:
    """One firing alert in Grafana unified-alerting webhook shape."""
    return {
        "status": "firing",
        "fingerprint": fingerprint(spec, batch),
        "labels": {
            "alertname": f"High CPU on {spec.node}",
            "severity": spec.severity,
            "app": spec.application,
            "component": spec.component,
            "region": spec.region,
            "node_name": spec.node,
            # Grafana labels are strings; the engine coerces them for the
            # numeric operators (greater_than etc.).
            "cpu_usage": spec.cpu_usage,
        },
        "annotations": {
            "summary": f"CPU at {spec.cpu_usage}% on {spec.node}",
            "impact": f"{spec.application} requests degrading in {spec.region}",
        },
    }


def sent_alert_ids(client: httpx.Client, source_id: str, batch: str) -> dict[str, str]:
    """Map ``alert_id -> node`` for the alerts this run just ingested."""
    alerts = (
        client.get("/alerts/", params={"source_id": source_id, "limit": 500})
        .raise_for_status()
        .json()
    )
    wanted = {fingerprint(spec, batch): spec.node for spec in ALERT_SPECS}
    return {
        alert["id"]: wanted[alert["external_id"]]
        for alert in alerts
        if alert["external_id"] in wanted
    }


def report_aggregates(client: httpx.Client, ours: dict[str, str]) -> None:
    """
    Report every aggregate that actually contains one of the alerts we sent.

    Following the alert ids (rather than the group key we expected) is what
    makes a *different* rule winning the alert visible: ``process_alert``
    returns on the first active rule that aggregates, and ``get_active`` has no
    ordering — so an older, broader rule can legitimately claim these alerts.
    """
    aggregates = (
        client.get("/aggregated-alerts/", params={"limit": 500})
        .raise_for_status()
        .json()
    )

    claimed: set[str] = set()
    found = False
    for aggregate in aggregates:
        members = [aid for aid in aggregate["alert_ids"] if aid in ours]
        if not members:
            continue
        found = True
        claimed.update(members)

        expected = EXPECTED_GROUP_KEYS.get(aggregate["group_key"])
        if expected is None:
            note = "  <- another rule matched first, different group key"
        elif aggregate["count"] != expected:
            note = f"  (expected count={expected})"
        else:
            note = ""

        print(
            f"    [{aggregate['status']}] [{aggregate['severity']:8}] "
            f"count={aggregate['count']} {aggregate['group_key']} "
            f"rule={aggregate['rule_name']!r}{note}"
        )
        print(f"        members from this run: {sorted(ours[a] for a in members)}")

    if not found:
        print("    none. No active rule claimed any of these alerts - check that")
        print("    the rule exists, is enabled, and that its conditions/group_by")
        print("    match the fields this script sends.")

    standalone = sorted(node for aid, node in ours.items() if aid not in claimed)
    if standalone:
        print(f"    standalone (in no aggregate): {standalone}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed alerts that a correlation rule should aggregate."
    )
    parser.add_argument(
        "--api",
        default=os.environ.get("ALERTIQ_API", "http://localhost:8000/api/v1"),
        help="API base URL (default: $ALERTIQ_API or http://localhost:8000/api/v1).",
    )
    parser.add_argument(
        "--user",
        default=os.environ.get("ALERTIQ_USER", "aaa"),
        help="Login username (default: $ALERTIQ_USER or 'aaa').",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("ALERTIQ_PASS", "aaaaaaaa"),
        help="Login password (default: $ALERTIQ_PASS).",
    )
    parser.add_argument(
        "--batch",
        default="1",
        help=(
            "Fingerprint suffix. Re-running with the same value is idempotent; "
            "a new value adds fresh members to the same open aggregates."
        ),
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

        print("==> Enabled correlation rules")
        warn_if_no_matching_rule(client)

        print("==> Finding a source to attach the alerts to")
        source_id, webhook_secret = get_or_create_source(client)
        print(f"    using source_id={source_id}")

        print(f"==> Ingesting {len(ALERT_SPECS)} alerts (batch={args.batch})")
        for spec in ALERT_SPECS:
            print(
                f"    {spec.node:20} region={spec.region:10} "
                f"app={spec.application:9} component={spec.component:9} "
                f"cpu={spec.cpu_usage:>3}  -> {spec.expectation}"
            )

        payload = {
            "status": "firing",
            "alerts": [grafana_alert(spec, args.batch) for spec in ALERT_SPECS],
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
        if counts["aggregated"] != EXPECTED_AGGREGATED:
            print(
                f"    NOTE: {counts['aggregated']}/{EXPECTED_AGGREGATED} alerts were "
                "aggregated (re-runs of the same batch report 0 newly counted "
                "members only if the alerts were already folded in)."
            )

        print("==> Aggregates containing these alerts")
        report_aggregates(client, sent_alert_ids(client, source_id, args.batch))

    print()
    print("Done. Open the alerts feed: each group is one row badged 'AGG - n'")
    print("(hover it for the rule name); click it to see the grouped members.")
    print("Re-run with --batch 2 to watch the counts grow inside the same window.")
    return 0


if __name__ == "__main__":
    sys.exit(main())