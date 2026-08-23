#!/usr/bin/env python3
"""
Interactive wizard for the AlertIQ alert generator.

Asks a handful of questions (defaults shown in brackets, Enter to accept)
then calls simulator.main() with the equivalent argv.

    python wizard.py
"""

from __future__ import annotations

import getpass
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

import simulator  # noqa: E402
from api_client import ApiClient, RequestFailed  # noqa: E402
from provisioning import ProvisioningError, login  # noqa: E402


def ask(prompt: str, default: str) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"{prompt}{suffix}: ").strip()
    except EOFError:
        raw = ""
    return raw or default


def ask_password(prompt: str, default: str) -> str:
    """Like ``ask``, but the input isn't echoed and the default is never printed."""
    suffix = " [press Enter to keep current]" if default else ""
    try:
        raw = getpass.getpass(f"{prompt}{suffix}: ")
    except EOFError:
        raw = ""
    return raw or default


def ask_float(prompt: str, default: float) -> float:
    while True:
        raw = ask(prompt, str(default))
        try:
            return float(raw)
        except ValueError:
            print("  please enter a number")


def ask_int(prompt: str, default: int) -> int:
    while True:
        raw = ask(prompt, str(default))
        try:
            return int(raw)
        except ValueError:
            print("  please enter a whole number")


def ask_choice(prompt: str, choices: tuple[str, ...], default: str) -> str:
    while True:
        raw = ask(f"{prompt} ({'/'.join(choices)})", default)
        if raw in choices:
            return raw
        print(f"  please pick one of: {', '.join(choices)}")


def ask_yes_no(prompt: str, default: bool) -> bool:
    raw = ask(f"{prompt} (y/n)", "y" if default else "n").lower()
    return raw.startswith("y")


def main() -> int:
    print("=== AlertIQ alert generator ===")
    print("Press Enter on any question to accept the default shown in [brackets].\n")

    base_url = ask("AlertIQ base URL", os.environ.get("ALERTIQ_BASE_URL", "http://127.0.0.1:8000"))

    print(
        "\nThis needs an AlertIQ login to find (or create) its own Grafana/Prometheus "
        "mock sources - no manual source setup required."
    )
    username = ask("AlertIQ username", os.environ.get("ALERTIQ_USERNAME", ""))
    password = ask_password("AlertIQ password", os.environ.get("ALERTIQ_PASSWORD", ""))
    while not username or not password:
        print("  a username and password are required to auto-provision sources.")
        username = ask("AlertIQ username", username)
        password = ask_password("AlertIQ password", password)

    # Fail fast on a typo'd URL/login, not after the whole rest of the wizard.
    while True:
        client = ApiClient(base_url.rstrip("/") + "/api/v1", timeout=10.0)
        try:
            login(client, username, password)
            print("  login OK\n")
            break
        except RequestFailed as e:
            print(f"  could not reach {base_url}: {e}")
            base_url = ask("AlertIQ base URL", base_url)
        except ProvisioningError as e:
            print(f"  {e}")
            username = ask("AlertIQ username", username)
            password = ask_password("AlertIQ password", password)

    provider = ask_choice(
        "\nWhich source(s) should generate alerts?",
        ("both", "alternate", "random", "grafana", "prometheus"),
        "both",
    )

    print(
        "\nSize the run either as a one-shot bulk load (all at once, e.g. for a demo "
        "dataset) or spread live over a time window (e.g. for a running presentation)."
    )
    mode = ask_choice("Mode", ("bulk", "spread"), "bulk")
    count = ask_int("How many alerts total?", 50)
    time_range = ""
    if mode == "spread":
        time_range = ask("Spread across how long? (e.g. 30s, 5m, 1h)", "5m")

    burst_chance = ask_float(
        "\nFraction of alerts that should be a correlated incident burst (0-1)", 0.15
    )
    resolve_fraction = ask_float(
        "Fraction of fired alerts that should auto-resolve afterwards (0-1)", 0.3
    )

    reset = ask_yes_no(
        "\nClear this tool's own previous demo data first? (only deletes the "
        "'AlertIQ Simulator - *' sources it created, nothing else)",
        False,
    )

    print(f"\nRunning against {base_url} - Ctrl+C at any time stops cleanly.\n")
    if not ask_yes_no("Start now?", True):
        print("Cancelled.")
        return 0

    # Env, not argv: argv is visible to other local users via ps/proc.
    os.environ["ALERTIQ_USERNAME"] = username
    os.environ["ALERTIQ_PASSWORD"] = password

    argv = [
        "--base-url", base_url,
        "--provider", provider,
        "--count", str(count),
        "--burst-chance", str(burst_chance),
        "--resolve-fraction", str(resolve_fraction),
    ]
    if time_range:
        argv += ["--time-range", time_range]
    if reset:
        # Already confirmed above — skip simulator.py's own confirmation prompt.
        argv += ["--reset", "--yes"]

    sys.argv = ["simulator.py", *argv]
    return simulator.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelled.")
        raise SystemExit(130)
