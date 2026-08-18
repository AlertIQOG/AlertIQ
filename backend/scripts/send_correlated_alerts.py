"""
Seed a burst of alerts that the correlation engine should fold into aggregates.

Uses only the Python 3 standard library (urllib + json) — no venv or
``pip install`` required; any plain ``python3`` can run it.

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

What this script then sends (7 alerts, one batch). The alerts describe
different database symptoms — lock waits, autovacuum falling behind, a cold
buffer cache — because a realistic group is *related*, not identical; only the
four fields the rule reads (component, cpu_usage, region, application) are held
to what the rule needs:

    us-east-1 / auth       x3  (cpu 95/92/98, one Critical) -> aggregate #1, count 3
    ap-south-1 / inventory x2  (cpu 91/97)                  -> aggregate #2, count 2
    us-east-1 / reporting  x1  (cpu 44)  condition fails    -> stays standalone
    us-east-1 / search     x1  (component=api) fails        -> stays standalone

To send a different set, edit ``ALERT_SPECS`` and bump ``FINGERPRINT_PREFIX``
(see the note there). Alert headlines are composed from each spec's ``node``,
so renaming a node cannot leave a stale name behind in its message.

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

    python scripts/send_correlated_alerts.py
    python -m scripts.send_correlated_alerts
    python -m scripts.send_correlated_alerts --batch 2
    python -m scripts.send_correlated_alerts --user admin --password secret
    ALERTIQ_API=http://localhost:8000/api/v1 python -m scripts.send_correlated_alerts
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, NamedTuple


class ApiError(Exception):
    """An API call returned a non-2xx status."""

    def __init__(self, method: str, url: str, status: int, body: str) -> None:
        super().__init__(f"{method} {url} failed with HTTP {status}")
        self.method = method
        self.url = url
        self.status = status
        self.body = body


class ApiClient:
    """Minimal stdlib JSON client: bearer-token header + error surfacing."""

    def __init__(self, base_url: str, timeout: float = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.headers: dict[str, str] = {}

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        form: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        url = self.base_url + path
        if params:
            url += "?" + urllib.parse.urlencode(params)

        data: bytes | None = None
        request_headers = dict(self.headers)
        if headers:
            request_headers.update(headers)
        if form is not None:
            data = urllib.parse.urlencode(form).encode()
            request_headers["Content-Type"] = "application/x-www-form-urlencoded"
        elif json_body is not None:
            data = json.dumps(json_body).encode()
            request_headers["Content-Type"] = "application/json"

        req = urllib.request.Request(
            url, data=data, headers=request_headers, method=method
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                body = response.read().decode()
        except urllib.error.HTTPError as exc:
            raise ApiError(
                method, url, exc.code, exc.read().decode(errors="replace")
            ) from None
        return json.loads(body) if body else None

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        return self.request("GET", path, params=params)

    def post(
        self,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        form: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        return self.request(
            "POST", path, json_body=json_body, form=form, headers=headers
        )


class AlertSpec(NamedTuple):
    """One alert to send, plus what we expect the engine to do with it."""

    node: str
    symptom: str  # what went wrong; the node is appended to form the headline
    region: str
    application: str
    component: str
    cpu_usage: str
    severity: str  # grafana label value: info | warning | error | critical
    impact: str  # annotation; shows on the alert, not used for matching
    expectation: str  # human-readable note printed in the summary

    @property
    def message(self) -> str:
        """Headline sent as the Grafana ``alertname``.

        Composed rather than stored so renaming a node cannot leave a stale
        node name behind in its own alert text.
        """
        return f"{self.symptom} on {self.node}"


# Only four fields decide the outcome: component and cpu_usage (the rule's
# conditions) and region + application (its group_by). Messages, nodes,
# severities and impacts vary freely — a real incident produces related
# symptoms, not eight copies of one alert.
ALERT_SPECS: list[AlertSpec] = [
    # ── Group 1 — region=us-east-1|application=auth ────────────────────
    # One database under pressure, seen three different ways. The Critical
    # member escalates the whole aggregate (merge_severity never de-escalates).
    AlertSpec(
        node="prod-auth-db-1",
        symptom="Sessions table lock wait timeout",
        region="us-east-1", application="auth", component="database",
        cpu_usage="95", severity="error",
        impact="Sign-ins timing out; users bounced to the login page",
        expectation="aggregate #1",
    ),
    AlertSpec(
        node="prod-auth-db-2",
        symptom="Autovacuum falling behind, 1.2M dead tuples",
        region="us-east-1", application="auth", component="database",
        cpu_usage="92", severity="warning",
        impact="Table bloat growing; queries degrading hour over hour",
        expectation="aggregate #1",
    ),
    AlertSpec(
        node="prod-auth-db-3",
        symptom="Buffer cache hit ratio down to 71%",
        region="us-east-1", application="auth", component="database",
        cpu_usage="98", severity="critical",
        impact="Token validation reading from disk; auth p99 above SLO",
        expectation="aggregate #1 (escalates severity to Critical)",
    ),
    # ── Group 2 — region=ap-south-1|application=inventory ──────────────
    # Same rule, different group_by values -> a second, separate aggregate.
    AlertSpec(
        node="ap-inventory-db-1",
        symptom="stock_levels index bloat at 340%",
        region="ap-south-1", application="inventory", component="database",
        cpu_usage="91", severity="warning",
        impact="Stock lookups scanning; oversell risk during peak",
        expectation="aggregate #2",
    ),
    AlertSpec(
        node="ap-inventory-db-2",
        symptom="Checkpoint taking 90s, IO saturated",
        region="ap-south-1", application="inventory", component="database",
        cpu_usage="97", severity="error",
        impact="Warehouse sync backing up behind write stalls",
        expectation="aggregate #2",
    ),
    # ── Control alerts — must NOT be aggregated ────────────────────────
    # Each fails exactly one condition, so a missing group is traceable to a
    # specific clause of the rule rather than to "correlation is broken".
    AlertSpec(
        node="reporting-db-1",
        symptom="Nightly aggregation job running long",
        region="us-east-1", application="reporting", component="database",
        cpu_usage="44", severity="info",
        impact="Morning dashboards may lag by an hour",
        expectation="standalone (cpu_usage <= 90)",
    ),
    AlertSpec(
        node="prod-search-api-1",
        symptom="Search p95 above 800ms",
        region="us-east-1", application="search", component="api",
        cpu_usage="96", severity="error",
        impact="Product search feels sluggish; conversion dipping",
        expectation="standalone (component != database)",
    ),
]

EXPECTED_AGGREGATED = sum(
    1 for spec in ALERT_SPECS if spec.expectation.startswith("aggregate")
)

# Group keys the engine builds from group_by = ["region", "application"] — but
# only if *this* rule is the first active one to match. Reporting follows the
# alert ids instead, so a different rule winning the alert is visible rather
# than looking like "nothing aggregated".
EXPECTED_GROUP_KEYS = {
    "region=us-east-1|application=auth": 3,
    "region=ap-south-1|application=inventory": 2,
}


# Namespaces this script's fingerprints. Bump it whenever the alert *content*
# changes: ingest upserts by (source_id, external_id) and never rewrites an
# existing alert's message, so reusing a fingerprint would resurrect the old
# text — and an old member alert is already Dismissed, which the engine skips.
FINGERPRINT_PREFIX = "seed-db-pressure"


def fingerprint(spec: AlertSpec, batch: str) -> str:
    """Stable per-node fingerprint — becomes the alert's external_id."""
    return f"{FINGERPRINT_PREFIX}-{batch}-{spec.node}"


def login(client: ApiClient, username: str, password: str) -> str:
    """Return a bearer token, exiting with the server response on failure."""
    try:
        response = client.post(
            "/auth/login", form={"username": username, "password": password}
        )
        token = response.get("access_token")
    except ApiError as exc:
        print(f"error: login failed. Response:\n{exc.body}", file=sys.stderr)
        sys.exit(1)
    if not token:
        print(f"error: login failed. Response:\n{response}", file=sys.stderr)
        sys.exit(1)
    return token


def get_or_create_source(client: ApiClient) -> tuple[str, str]:
    """
    Return ``(source_id, webhook_secret)`` for a source that can ingest.

    Prefers an existing source that has a webhook secret; otherwise creates a
    demo source (creation auto-generates a secret).
    """
    sources = client.get("/sources/")
    for source in sources:
        if source.get("webhook_secret"):
            return source["id"], source["webhook_secret"]

    print("    no source with a webhook secret found - creating one")
    created = client.post(
        "/sources/", json_body={"name": "demo-seed", "provider_type": "grafana"}
    )
    return created["id"], created["webhook_secret"]


def warn_if_no_matching_rule(client: ApiClient) -> None:
    """
    Print the enabled rules so a missing/mistyped rule is obvious before we send.

    The check mirrors the engine: an enabled rule whose scope is empty or
    ``source=Grafana``, and whose conditions only reference fields we send.
    """
    rules = client.get("/correlation-rules/", params={"enabled": "true"})
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
            "alertname": spec.message,
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
            "impact": spec.impact,
        },
    }


def sent_alert_ids(client: ApiClient, source_id: str, batch: str) -> dict[str, str]:
    """Map ``alert_id -> node`` for the alerts this run just ingested."""
    alerts = client.get("/alerts/", params={"source_id": source_id, "limit": 500})
    wanted = {fingerprint(spec, batch): spec.node for spec in ALERT_SPECS}
    return {
        alert["id"]: wanted[alert["external_id"]]
        for alert in alerts
        if alert["external_id"] in wanted
    }


def report_aggregates(client: ApiClient, ours: dict[str, str]) -> None:
    """
    Report every aggregate that actually contains one of the alerts we sent.

    Following the alert ids (rather than the group key we expected) is what
    makes a *different* rule winning the alert visible: ``process_alert``
    returns on the first active rule that aggregates, and ``get_active`` has no
    ordering — so an older, broader rule can legitimately claim these alerts.
    """
    aggregates = client.get("/aggregated-alerts/", params={"limit": 500})

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
    except ApiError as exc:
        print(
            f"error: {exc.method} {exc.url} failed with "
            f"HTTP {exc.status}:\n{exc.body}",
            file=sys.stderr,
        )
    except urllib.error.URLError as exc:
        print(f"error: request to {args.api} failed: {exc.reason}", file=sys.stderr)
    return 1


def seed(args: argparse.Namespace) -> int:
    client = ApiClient(args.api, timeout=30)
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
        print(f"    {spec.message}")
        print(
            f"      region={spec.region:10} app={spec.application:9} "
            f"component={spec.component:9} cpu={spec.cpu_usage:>3}  "
            f"-> {spec.expectation}"
        )

    payload = {
        "status": "firing",
        "alerts": [grafana_alert(spec, args.batch) for spec in ALERT_SPECS],
    }
    counts = client.post(
        f"/ingest/grafana/{source_id}",
        json_body=payload,
        headers={"X-Webhook-Token": webhook_secret},
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
