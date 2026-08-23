#!/usr/bin/env python3
"""
Mock alert traffic generator for AlertIQ ingest endpoints.

Stdlib only (see api_client.py) — runs on any plain python3, including the
deploy server. POSTs randomized Grafana/Prometheus webhook payloads to:
  {base}/api/v1/ingest/grafana/{source_id}
  {base}/api/v1/ingest/prometheus/{source_id}

Sizing a run:
  --count N [--time-range T]   spread N alerts across T; omit T for a
                                one-shot bulk/backfill burst.
  --alerts-per-minute R [--duration T]
                                legacy rate-based continuous stream.

--username/--password (or ALERTIQ_USERNAME/ALERTIQ_PASSWORD) auto-provisions
sources via login — no manual curl/source-id/token setup required.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import os
import random
import sys
import threading
import time
from dataclasses import dataclass
from typing import Literal

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from api_client import ApiClient, RequestFailed
from payloads import (
    FiredAlert,
    build_grafana_webhook,
    build_incident_burst,
    build_prometheus_webhook,
    build_resolution_webhook,
)
from provisioning import (
    DEFAULT_GRAFANA_SOURCE_NAME,
    DEFAULT_PROMETHEUS_SOURCE_NAME,
    ProvisioningError,
    delete_source_if_exists,
    ensure_source,
    login,
)

ProviderMode = Literal["grafana", "prometheus", "both", "alternate", "random"]


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    return v if v not in (None, "") else default


def _parse_duration(raw: str) -> float:
    """Accepts plain seconds ("90"), or a suffixed value: 45s, 10m, 2h."""
    raw = raw.strip().lower()
    if not raw:
        return 0.0
    units = {"s": 1.0, "m": 60.0, "h": 3600.0}
    if raw[-1] in units:
        return float(raw[:-1]) * units[raw[-1]]
    return float(raw)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Send mock Grafana / Prometheus webhook alerts to AlertIQ ingest.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--base-url",
        default=_env("ALERTIQ_BASE_URL", "http://127.0.0.1:8000"),
        help="API base URL (env ALERTIQ_BASE_URL).",
    )

    auth = p.add_argument_group("auto-provisioning (skip manual source setup)")
    auth.add_argument(
        "--username",
        default=_env("ALERTIQ_USERNAME"),
        help="Admin username used to log in and find-or-create sources (env ALERTIQ_USERNAME).",
    )
    auth.add_argument(
        "--password",
        default=None,
        help="Admin password (env ALERTIQ_PASSWORD). Never shown in --help output.",
    )

    manual = p.add_argument_group("manual source setup (overrides auto-provisioning)")
    manual.add_argument("--grafana-source-id", default=_env("ALERTIQ_GRAFANA_SOURCE_ID"))
    manual.add_argument("--prometheus-source-id", default=_env("ALERTIQ_PROMETHEUS_SOURCE_ID"))
    manual.add_argument(
        "--grafana-token",
        default=None,
        help="Webhook secret for the Grafana source (env ALERTIQ_GRAFANA_TOKEN). Never shown in --help output.",
    )
    manual.add_argument(
        "--prometheus-token",
        default=None,
        help="Webhook secret for the Prometheus source (env ALERTIQ_PROMETHEUS_TOKEN). Never shown in --help output.",
    )

    sizing = p.add_argument_group("run sizing (pick one style)")
    sizing.add_argument(
        "--count",
        type=int,
        default=None,
        metavar="N",
        help="Total alerts to send. With --time-range, spread across it; without, fire "
        "all N back-to-back (bulk/backfill mode).",
    )
    sizing.add_argument(
        "--time-range",
        default=None,
        metavar="T",
        help="Spread --count over this much time, e.g. 45s, 10m, 2h. Omit for a burst.",
    )
    sizing.add_argument(
        "--alerts-per-minute",
        type=float,
        default=None,
        metavar="N",
        help="Legacy rate-based mode: target POSTs/minute (ignored if --count is set).",
    )
    sizing.add_argument(
        "--duration",
        type=float,
        default=None,
        metavar="SEC",
        help="Legacy rate-based mode: stop after SEC seconds (omit to run until interrupted).",
    )

    p.add_argument(
        "--provider",
        choices=("grafana", "prometheus", "both", "alternate", "random"),
        default=_env("ALERTIQ_PROVIDER", "alternate"),
        help="alternate|both|random|grafana|prometheus.",
    )
    p.add_argument(
        "--burst-chance",
        type=float,
        default=0.15,
        metavar="P",
        help="Probability [0-1] that a unit is a correlated incident burst "
        "(3-6 alerts sharing app/component/region) instead of a single alert.",
    )
    p.add_argument(
        "--resolve-fraction",
        type=float,
        default=0.3,
        metavar="P",
        help="Fraction [0-1] of fired alerts that get a resolved follow-up later.",
    )
    p.add_argument(
        "--concurrency",
        type=int,
        default=6,
        metavar="N",
        help="Parallel requests in bulk mode (--count without --time-range).",
    )
    p.add_argument("--insecure", action="store_true", help="Disable TLS verification (dev HTTPS).")
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Only print the run summary, not one line per request (for large --count on a projector).",
    )
    reset = p.add_argument_group("reset (clears only this tool's own sources)")
    reset.add_argument(
        "--reset",
        action="store_true",
        help=f"Before running, delete the exact sources named {DEFAULT_GRAFANA_SOURCE_NAME!r} / "
        f"{DEFAULT_PROMETHEUS_SOURCE_NAME!r} if they exist (cascades to their alerts), then "
        "provision fresh ones. Never touches any other source. Requires --username/--password.",
    )
    reset.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip the --reset confirmation prompt (for scripted use).",
    )
    return p.parse_args()


def _ingest_path(provider: str, source_id: str) -> str:
    return f"/ingest/{provider}/{source_id}"


def _pick_provider(mode: ProviderMode, toggle: bool) -> str:
    if mode == "grafana":
        return "grafana"
    if mode == "prometheus":
        return "prometheus"
    if mode == "alternate":
        return "grafana" if toggle else "prometheus"
    return random.choice(("grafana", "prometheus"))


@dataclass
class SourceCreds:
    id: str
    token: str


def resolve_sources(client: ApiClient, args: argparse.Namespace) -> dict[str, SourceCreds]:
    """Manual ids/tokens win; otherwise auto-provision via login + get-or-create."""
    sources: dict[str, SourceCreds] = {}

    need_grafana = args.provider in ("grafana", "both", "alternate", "random")
    need_prometheus = args.provider in ("prometheus", "both", "alternate", "random")

    if args.grafana_source_id and args.grafana_token:
        sources["grafana"] = SourceCreds(args.grafana_source_id, args.grafana_token)
    if args.prometheus_source_id and args.prometheus_token:
        sources["prometheus"] = SourceCreds(args.prometheus_source_id, args.prometheus_token)

    missing_grafana = need_grafana and "grafana" not in sources
    missing_prometheus = need_prometheus and "prometheus" not in sources
    if not (missing_grafana or missing_prometheus):
        return sources

    if not (args.username and args.password):
        missing = []
        if missing_grafana:
            missing.append("--grafana-source-id/--grafana-token")
        if missing_prometheus:
            missing.append("--prometheus-source-id/--prometheus-token")
        print(
            f"error: missing {', '.join(missing)}, and no --username/--password "
            "to auto-provision. Set ALERTIQ_USERNAME/ALERTIQ_PASSWORD or pass IDs/tokens directly.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    try:
        login(client, args.username, args.password)
        if missing_grafana:
            info = ensure_source(client, name=DEFAULT_GRAFANA_SOURCE_NAME, provider_type="grafana")
            sources["grafana"] = SourceCreds(info.id, info.webhook_secret)
            print(f"Auto-provisioned Grafana source: {info.id}")
        if missing_prometheus:
            info = ensure_source(
                client, name=DEFAULT_PROMETHEUS_SOURCE_NAME, provider_type="prometheus"
            )
            sources["prometheus"] = SourceCreds(info.id, info.webhook_secret)
            print(f"Auto-provisioned Prometheus source: {info.id}")
    except ProvisioningError as e:
        print(f"error: {e}", file=sys.stderr)
        raise SystemExit(2)
    except RequestFailed as e:
        print(f"error: could not reach {args.base_url}: {e}", file=sys.stderr)
        raise SystemExit(2)

    return sources


def maybe_reset(client: ApiClient, args: argparse.Namespace) -> None:
    """If --reset was passed, delete this tool's own sources (exact match
    only) before the run provisions fresh ones."""
    if not args.reset:
        return
    if not (args.username and args.password):
        print(
            "error: --reset requires --username/--password (it needs a login to delete sources).",
            file=sys.stderr,
        )
        raise SystemExit(2)

    print(
        f"About to delete the sources named {DEFAULT_GRAFANA_SOURCE_NAME!r} and "
        f"{DEFAULT_PROMETHEUS_SOURCE_NAME!r} at {args.base_url} (and cascade-delete their alerts). "
        "No other source is touched."
    )
    if not args.yes:
        try:
            confirm = input("Type 'yes' to continue: ").strip().lower()
        except EOFError:
            confirm = ""
        if confirm != "yes":
            print("Aborted - nothing deleted.", file=sys.stderr)
            raise SystemExit(1)

    try:
        login(client, args.username, args.password)
        for name, provider_type in (
            (DEFAULT_GRAFANA_SOURCE_NAME, "grafana"),
            (DEFAULT_PROMETHEUS_SOURCE_NAME, "prometheus"),
        ):
            deleted = delete_source_if_exists(client, name=name, provider_type=provider_type)
            print(f"{'deleted' if deleted else 'not found, nothing to delete'}: {name}")
    except ProvisioningError as e:
        print(f"error: {e}", file=sys.stderr)
        raise SystemExit(2)
    except RequestFailed as e:
        print(f"error: could not reach {args.base_url}: {e}", file=sys.stderr)
        raise SystemExit(2)


_MAX_ATTEMPTS = 3
_RETRY_BACKOFF = (0.5, 1.5, 3.0)
_RETRYABLE_STATUS = {429, 502, 503, 504}


class Sender:
    """Wraps the client + source credentials; tracks fired alerts for later
    resolutions. Every public method is exception-safe — a failed request
    retries with backoff, then counts as a failure; it never raises, so one
    bad request can't take down a live run.
    """

    def __init__(self, client: ApiClient, sources: dict[str, SourceCreds], *, quiet: bool = False):
        self.client = client
        self.sources = sources
        self.quiet = quiet
        self.count = 0
        self.ok = 0
        self.failed = 0
        self.fired: list[FiredAlert] = []
        self._lock = threading.Lock()

    def send_one(self, provider: str) -> None:
        try:
            creds = self.sources[provider]
            path = _ingest_path(provider, creds.id)
            body, fired = (
                build_grafana_webhook() if provider == "grafana" else build_prometheus_webhook()
            )
            if self._post(provider, path, creds.token, body):
                with self._lock:
                    self.fired.append(fired)
        except Exception as e:  # noqa: BLE001 — one bad unit must not stop the run
            print(f"unexpected error building/sending {provider} alert: {e}", file=sys.stderr)

    def send_burst(self, provider: str, size: int) -> None:
        try:
            creds = self.sources[provider]
            path = _ingest_path(provider, creds.id)
            for spec in build_incident_burst(size):
                body, fired = (
                    build_grafana_webhook(spec)
                    if provider == "grafana"
                    else build_prometheus_webhook(spec)
                )
                if self._post(provider, path, creds.token, body):
                    with self._lock:
                        self.fired.append(fired)
                time.sleep(random.uniform(0.1, 0.5))
        except Exception as e:  # noqa: BLE001
            print(f"unexpected error building/sending {provider} burst: {e}", file=sys.stderr)

    def send_resolution(self, fired: FiredAlert) -> None:
        try:
            creds = self.sources[fired.provider]
            path = _ingest_path(fired.provider, creds.id)
            body = build_resolution_webhook(fired)
            self._post(f"{fired.provider} (resolve)", path, creds.token, body)
        except Exception as e:  # noqa: BLE001
            print(f"unexpected error sending {fired.provider} resolution: {e}", file=sys.stderr)

    def _post(self, label: str, path: str, token: str, body: dict) -> bool:
        """POST with a few retries on network errors / 429/5xx. Returns success."""
        with self._lock:
            self.count += 1
            n = self.count

        last_error = ""
        for attempt in range(_MAX_ATTEMPTS):
            try:
                status, resp_body = self.client.post(
                    path, json_body=body, headers={"X-Webhook-Token": token}
                )
            except RequestFailed as e:
                last_error = f"request error: {e}"
            else:
                if status == 202:
                    if not self.quiet:
                        print(f"[{n}] {label} -> {status} {resp_body}")
                    with self._lock:
                        self.ok += 1
                    return True
                if status not in _RETRYABLE_STATUS:
                    print(f"[{n}] {label} -> {status} {str(resp_body)[:200]}", file=sys.stderr)
                    with self._lock:
                        self.failed += 1
                    return False
                last_error = f"{status} {str(resp_body)[:200]}"

            if attempt < _MAX_ATTEMPTS - 1:
                time.sleep(_RETRY_BACKOFF[attempt])

        print(f"[{n}] {label} -> giving up after {_MAX_ATTEMPTS} attempts: {last_error}", file=sys.stderr)
        with self._lock:
            self.failed += 1
        return False

    def fire_unit(self, provider: str, burst_chance: float) -> None:
        if random.random() < burst_chance:
            self.send_burst(provider, random.randint(3, 6))
        else:
            self.send_one(provider)

    def send_pending_resolutions(self, fraction: float) -> None:
        sample_size = int(len(self.fired) * fraction)
        for fired in random.sample(self.fired, k=min(sample_size, len(self.fired))):
            time.sleep(random.uniform(0.05, 0.3))
            self.send_resolution(fired)

    def summary(self) -> str:
        return f"{self.ok} ok, {self.failed} failed, {self.count} total request(s)"


def run_bulk(args: argparse.Namespace, sender: Sender) -> None:
    """--count with no --time-range: fire everything back-to-back, in parallel."""
    providers = []
    toggle = False
    for _ in range(args.count):
        toggle = not toggle
        providers.append(_pick_provider(args.provider, toggle))

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency)
    futures = [pool.submit(sender.fire_unit, provider, args.burst_chance) for provider in providers]
    interrupted = False
    try:
        for f in concurrent.futures.as_completed(futures):
            f.result()  # fire_unit never raises; this only surfaces pool-internal errors
        pool.shutdown(wait=True)
    except KeyboardInterrupt:
        interrupted = True
        print(
            "\nInterrupted - cancelling requests that haven't started yet; "
            "in-flight ones will finish.",
            file=sys.stderr,
        )
        pool.shutdown(wait=True, cancel_futures=True)

    print(f"Bulk burst done for {args.count} unit(s) - {sender.summary()}")
    if not interrupted:
        sender.send_pending_resolutions(args.resolve_fraction)


def run_spread(args: argparse.Namespace, sender: Sender, seconds: float) -> None:
    """--count spread across --time-range, live, with jitter."""
    interval = seconds / args.count if args.count else 0.0
    toggle = False
    deadline = time.monotonic() + seconds

    print(f"Spreading {args.count} unit(s) across {seconds:.0f}s (~{interval:.2f}s apart)")

    sent_units = 0
    interrupted = False
    try:
        for _ in range(args.count):
            toggle = not toggle
            provider = _pick_provider(args.provider, toggle)
            sender.fire_unit(provider, args.burst_chance)
            sent_units += 1

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                continue
            jittered = max(0.0, random.uniform(interval * 0.5, interval * 1.5))
            time.sleep(min(jittered, remaining))
    except KeyboardInterrupt:
        interrupted = True
        print(f"\nInterrupted after {sent_units}/{args.count} unit(s) - wrapping up.", file=sys.stderr)

    print(f"Spread run done ({sent_units}/{args.count} unit(s) attempted) - {sender.summary()}")
    if not interrupted:
        sender.send_pending_resolutions(args.resolve_fraction)


def run_legacy_rate(args: argparse.Namespace, sender: Sender) -> None:
    """Original continuous rate-based stream (--alerts-per-minute [--duration])."""
    posts_per_cycle = 2 if args.provider == "both" else 1
    interval = (60.0 * posts_per_cycle) / args.alerts_per_minute
    print(f"Target: ~{args.alerts_per_minute} POSTs/min (cycle every ~{interval:.2f}s)")
    if args.duration:
        print(f"Duration: {args.duration}s")

    toggle = False
    deadline = time.monotonic() + args.duration if args.duration else None

    interrupted = False
    try:
        while True:
            if deadline is not None and time.monotonic() >= deadline:
                break
            loop_start = time.perf_counter()

            if args.provider == "both":
                sender.send_one("grafana")
                sender.send_one("prometheus")
            else:
                provider = _pick_provider(args.provider, toggle)
                toggle = not toggle
                sender.send_one(provider)

            elapsed = time.perf_counter() - loop_start
            sleep_for = max(0.0, interval - elapsed)
            if deadline is not None:
                remain = deadline - time.monotonic()
                sleep_for = min(sleep_for, max(0.0, remain))
            time.sleep(sleep_for)

            if deadline is not None and time.monotonic() >= deadline:
                break
    except KeyboardInterrupt:
        interrupted = True
        print("\nInterrupted - wrapping up.", file=sys.stderr)

    print(f"Done. {sender.summary()}")
    if not interrupted:
        sender.send_pending_resolutions(args.resolve_fraction)


def main() -> int:
    args = parse_args()
    # Resolved post-parse, not as argparse defaults, so --help never echoes a
    # real secret back when the env var is set.
    args.password = args.password or _env("ALERTIQ_PASSWORD")
    args.grafana_token = args.grafana_token or _env("ALERTIQ_GRAFANA_TOKEN")
    args.prometheus_token = args.prometheus_token or _env("ALERTIQ_PROMETHEUS_TOKEN")

    if not (0.0 <= args.burst_chance <= 1.0):
        print("error: --burst-chance must be between 0 and 1", file=sys.stderr)
        return 2
    if not (0.0 <= args.resolve_fraction <= 1.0):
        print("error: --resolve-fraction must be between 0 and 1", file=sys.stderr)
        return 2

    client = ApiClient(
        args.base_url.rstrip("/") + "/api/v1", timeout=30.0, insecure=args.insecure
    )

    try:
        maybe_reset(client, args)
        sources = resolve_sources(client, args)
    except KeyboardInterrupt:
        print("\nInterrupted during provisioning - nothing was sent.", file=sys.stderr)
        return 130

    print(f"Base URL: {args.base_url}")
    print(f"Provider mode: {args.provider}")

    sender = Sender(client, sources, quiet=args.quiet)

    if args.count is not None:
        if args.count <= 0:
            print("error: --count must be positive", file=sys.stderr)
            return 2
        seconds = _parse_duration(args.time_range) if args.time_range else 0.0
        if seconds > 0:
            run_spread(args, sender, seconds)
        else:
            run_bulk(args, sender)
    elif args.alerts_per_minute:
        if args.alerts_per_minute <= 0:
            print("error: --alerts-per-minute must be positive", file=sys.stderr)
            return 2
        run_legacy_rate(args, sender)
    else:
        print(
            "error: specify --count [--time-range T] or --alerts-per-minute [--duration T]",
            file=sys.stderr,
        )
        return 2

    if sender.failed:
        print(
            f"warning: {sender.failed} request(s) failed after retries - check the "
            "server/network above.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
