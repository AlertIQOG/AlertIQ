# Mock Alert Generator (Grafana & Prometheus)

Generates HTTP POST traffic that matches **Grafana unified alerting** and **Prometheus Alertmanager** webhook JSON shapes and sends them to AlertIQ's real ingest endpoints:

- `POST {base}/api/v1/ingest/grafana/{source_id}`
- `POST {base}/api/v1/ingest/prometheus/{source_id}`

This goes through the exact same code path as a real provider webhook — normalize → upsert → correlation engine — so generated data shows up in the feed, its filters (severity/status/region/application/component/source), and gets folded into aggregates the same way real alerts would.

## Quick start (recommended)

Standard-library only — no venv, no `pip install`, runs on any plain `python3` (including directly on the deploy server):

```bash
cd tools/alert_simulator
python3 wizard.py
```

The wizard asks a few questions (base URL, an AlertIQ login, how many alerts, how fast) and does everything else — no manual source setup. Answering "y" to the last prompt starts the run; Ctrl+C stops it cleanly at any point.

## Non-interactive: `simulator.py`

`wizard.py` is a thin front-end over `simulator.py`; call it directly for scripting/CI or finer control.

**Auto-provisioning** — give it an AlertIQ login and it finds-or-creates its own `AlertIQ Simulator - Grafana` / `- Prometheus` sources and reads back their id + webhook secret. Prefer environment variables over `--password` on the command line — a shell history entry or `ps`/`/proc` listing can otherwise expose it:

```bash
export ALERTIQ_USERNAME=<admin-user>
export ALERTIQ_PASSWORD=<admin-pass>

python simulator.py \
  --base-url http://127.0.0.1:8000 \
  --provider both \
  --count 200
```

**Sizing a run** (pick one):

- `--count N` alone — fire all N alerts back-to-back as fast as possible (a bulk/one-shot backfill — good for seeding a demo dataset).
- `--count N --time-range T` — spread N alerts live across T real seconds/minutes/hours (`45s`, `10m`, `2h`) with jitter, so they trickle in the way a live presentation would want.
- `--alerts-per-minute R [--duration T]` — legacy continuous-rate stream; runs until Ctrl+C if `--duration` is omitted.

**Realism knobs:**

- `--burst-chance P` (default `0.15`) — probability a unit is a *correlated incident burst* instead of a single alert: 3–6 alerts sharing app/component/region, drawn from one coherent symptom set (e.g. high CPU + latency spike + exhausted connection pool — "one incident, several symptoms," not unrelated alert names), fired a few hundred ms apart. Whether these actually fold into one aggregate in the UI depends on having a matching **active correlation rule** already configured in AlertIQ (Correlation Rules screen) — the burst just makes that realistic to trigger.
- `--resolve-fraction P` (default `0.3`) — this fraction of fired alerts get a `resolved` follow-up webhook a few seconds later, for the same fingerprint and original `startsAt`. This exercises the real update path (`Open` → `Solved`), not a second insert.
- `--provider` — `both` fires each source every cycle; `alternate` toggles; `random` picks one; `grafana`/`prometheus` pins it.
- Node names (`prod-billing-api-worker-4`, occasionally `stg-...`) and the `ALERT_NAMES`/severity-weighting pools were checked against this project's actual deployed database rather than guessed — see `payloads.py` for the full lists.

**Reliability** — every request retries up to 3 times (backoff) on network errors or `429/502/503/504`; a failed request after retries is logged and counted, never crashes the run. Ctrl+C at any point stops cleanly, cancels anything not yet in flight, skips the trailing resolutions, and still prints a summary (`N ok, M failed`). Bulk mode (`--count` without `--time-range`) sends requests in parallel (`--concurrency`, default `6`) so a large backfill doesn't take forever. `--quiet` prints only the run summary (not one line per request) — useful for a large `--count` on a projector.

**`--reset`** — before running, deletes the exact sources named `AlertIQ Simulator - Grafana` / `- Prometheus` if they exist (cascades to their alerts) and provisions fresh ones. Exact-name match only, never a pattern — it will never touch any other source, which matters on a shared server. Prompts for confirmation unless `--yes`/`-y` is also passed (the wizard asks once and passes `--yes` itself). A source with a lot of alerts can take a while to cascade-delete server-side; the tool gives that call extra time and double-checks the source is actually gone before reporting failure, rather than reporting a false failure on a slow-but-successful delete.

### Manual source setup

If you'd rather not pass a login (e.g. scripted against a source you already created), pass ids/tokens directly and skip `--username`/`--password`:

```bash
export API=http://127.0.0.1:8000/api/v1
TOKEN=$(curl -sS -X POST "$API/auth/login" \
  -d 'username=<user>&password=<password>' | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

curl -sS -X POST "$API/sources/" -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"Mock Grafana","provider_type":"grafana"}' | tee /tmp/gf.json

python simulator.py \
  --grafana-source-id '<uuid>' --grafana-token '<webhook_secret>' \
  --provider grafana --count 50
```

## Running it on the server

SSH into the host running AlertIQ, `cd tools/alert_simulator`, and run `python3 wizard.py` — no setup step, it's stdlib-only. Point the base URL at wherever the backend is actually listening (`http://127.0.0.1:8000` if the wizard runs on the same box as the API — e.g. behind the same Docker Compose stack).

## Verify ingestion

```bash
curl -sS "$API/alerts/?limit=5" -H "Authorization: Bearer $TOKEN"
curl -sS "$API/alerts/filters" -H "Authorization: Bearer $TOKEN"
```

`/alerts/filters` returns the distinct values currently backing the feed's dropdowns — a quick way to confirm generated alerts are populating severity/region/application/component/source correctly.
