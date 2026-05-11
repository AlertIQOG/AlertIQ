#!/usr/bin/env python3
"""
Mock alert traffic generator for AlertIQ ingest endpoints.

POSTs randomized Grafana and/or Prometheus Alertmanager webhook payloads to:
  {base}/api/v1/ingest/grafana/{source_id}
  {base}/api/v1/ingest/prometheus/{source_id}
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import time
from typing import Literal
from urllib.parse import urljoin

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

import httpx

from payloads import build_grafana_webhook, build_prometheus_webhook

ProviderMode = Literal["grafana", "prometheus", "both", "alternate", "random"]


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    return v if v not in (None, "") else default


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Send mock Grafana / Prometheus webhook alerts to AlertIQ ingest.",
    )
    p.add_argument(
        "--base-url",
        default=_env("ALERTIQ_BASE_URL", "http://127.0.0.1:8000"),
        help="API base URL (default: env ALERTIQ_BASE_URL or http://127.0.0.1:8000).",
    )
    p.add_argument(
        "--grafana-source-id",
        default=_env("ALERTIQ_GRAFANA_SOURCE_ID"),
        help="UUID path param for /ingest/grafana/{id} (env: ALERTIQ_GRAFANA_SOURCE_ID).",
    )
    p.add_argument(
        "--prometheus-source-id",
        default=_env("ALERTIQ_PROMETHEUS_SOURCE_ID"),
        help="UUID for /ingest/prometheus/{id} (env: ALERTIQ_PROMETHEUS_SOURCE_ID).",
    )
    p.add_argument(
        "--alerts-per-minute",
        type=float,
        default=float(_env("ALERTIQ_ALERTS_PER_MINUTE", "12")),
        metavar="N",
        help="Target HTTP POSTs per minute (default: 12, env ALERTIQ_ALERTS_PER_MINUTE).",
    )
    p.add_argument(
        "--provider",
        choices=("grafana", "prometheus", "both", "alternate", "random"),
        default=_env("ALERTIQ_PROVIDER", "alternate"),
        help="alternate|random|both|grafana|prometheus (default: alternate).",
    )
    p.add_argument(
        "--duration",
        type=float,
        default=None,
        metavar="SEC",
        help="Stop after SEC seconds (default: run until interrupted).",
    )
    p.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS verification (for dev HTTPS).",
    )
    return p.parse_args()


def _ingest_url(base: str, provider: str, source_id: str) -> str:
    base = base.rstrip("/") + "/"
    return urljoin(base, f"api/v1/ingest/{provider}/{source_id}")


def _pick_provider(mode: ProviderMode, toggle: bool) -> str:
    if mode == "grafana":
        return "grafana"
    if mode == "prometheus":
        return "prometheus"
    if mode == "alternate":
        return "grafana" if toggle else "prometheus"
    # random
    return random.choice(("grafana", "prometheus"))


def _interval_seconds(rate_per_min: float, *, posts_per_cycle: int) -> float:
    """Seconds between cycle starts so total POSTs/min ≈ rate (posts_per_cycle per cycle)."""
    if rate_per_min <= 0:
        raise ValueError("rate must be positive")
    return (60.0 * posts_per_cycle) / rate_per_min


def main() -> int:
    args = parse_args()
    mode: ProviderMode = args.provider  # type: ignore[assignment]

    if mode in ("grafana", "both", "alternate", "random") and not args.grafana_source_id:
        print("error: --grafana-source-id or ALERTIQ_GRAFANA_SOURCE_ID is required", file=sys.stderr)
        return 2
    if mode in ("prometheus", "both", "alternate", "random") and not args.prometheus_source_id:
        print("error: --prometheus-source-id or ALERTIQ_PROMETHEUS_SOURCE_ID is required", file=sys.stderr)
        return 2

    rate = args.alerts_per_minute
    if rate <= 0:
        print("error: --alerts-per-minute must be positive", file=sys.stderr)
        return 2

    posts_per_cycle = 2 if mode == "both" else 1
    interval = _interval_seconds(rate, posts_per_cycle=posts_per_cycle)
    base = args.base_url.rstrip("/")
    verify = not args.insecure

    print(f"Base URL: {base}")
    print(f"Target: ~{rate} POSTs/min (cycle every ~{interval:.2f}s, {posts_per_cycle} POST(s)/cycle)")
    print(f"Provider mode: {mode}")
    if args.duration:
        print(f"Duration: {args.duration}s")

    toggle = False
    deadline = time.monotonic() + args.duration if args.duration else None
    count = 0

    with httpx.Client(timeout=30.0, verify=verify) as client:
        while True:
            if deadline is not None and time.monotonic() >= deadline:
                break

            loop_start = time.perf_counter()

            def send(prov: str) -> None:
                nonlocal count
                source_id = args.grafana_source_id if prov == "grafana" else args.prometheus_source_id
                url = _ingest_url(base, prov, source_id)
                body = build_grafana_webhook() if prov == "grafana" else build_prometheus_webhook()
                try:
                    r = client.post(url, json=body)
                    count += 1
                    ok = r.status_code == 202
                    if ok:
                        print(f"[{count}] {prov} -> {r.status_code} {r.json()}")
                    else:
                        suffix = r.text[:200] if r.text else ""
                        print(f"[{count}] {prov} -> {r.status_code} {suffix}", file=sys.stderr)
                except httpx.RequestError as e:
                    print(f"{prov} request error: {e}", file=sys.stderr)

            if mode == "both":
                send("grafana")
                send("prometheus")
            elif mode == "alternate":
                prov = "grafana" if toggle else "prometheus"
                toggle = not toggle
                send(prov)
            elif mode == "random":
                send(random.choice(("grafana", "prometheus")))
            elif mode == "grafana":
                send("grafana")
            else:
                send("prometheus")

            elapsed = time.perf_counter() - loop_start
            sleep_for = max(0.0, interval - elapsed)
            if deadline is not None:
                remain = deadline - time.monotonic()
                if sleep_for > remain:
                    sleep_for = max(0.0, remain)
            time.sleep(sleep_for)

            if deadline is not None and time.monotonic() >= deadline:
                break

    print(f"Done. Sent {count} requests.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
