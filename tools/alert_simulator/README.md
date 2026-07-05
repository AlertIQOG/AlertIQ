# Mock Alert Simulator (Grafana & Prometheus)

Generates HTTP POST traffic that matches **Grafana unified alerting** and **Prometheus Alertmanager** webhook JSON shapes and sends them to AlertIQ:

- `POST {base}/api/v1/ingest/grafana/{source_id}`
- `POST {base}/api/v1/ingest/prometheus/{source_id}`

Reference payloads live under `templates/*.example.json`. The simulator randomizes `alertname`, `instance` (Prometheus), `severity` (`critical` / `warning` / `info`), `region`, `app`, `component`, `fingerprint`, and timestamps so each request is unlikely to deduplicate on `external_id`.

Environment variables can be copied from `.env.example` into a local `.env` and loaded with your shell (`set -a && source .env && set +a` in bash) before running `python simulator.py`.

## Setup

```bash
cd tools/alert_simulator
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Create two sources in AlertIQ (one per provider type is recommended for clarity).
The management API requires a login token, and each created source returns a
`webhook_secret` that ingest requests must send as the `X-Webhook-Token` header:

```bash
export API=http://127.0.0.1:8000/api/v1

TOKEN=$(curl -sS -X POST "$API/auth/login" \
  -d 'username=<user>&password=<password>' | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

curl -sS -X POST "$API/sources/" -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"Mock Grafana","provider_type":"grafana"}' | tee /tmp/gf.json
curl -sS -X POST "$API/sources/" -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"Mock Prometheus","provider_type":"prometheus"}' | tee /tmp/prom.json
```

Copy the `id` **and `webhook_secret`** fields from the responses into the environment or CLI flags below.

## Run

```bash
export ALERTIQ_BASE_URL=http://127.0.0.1:8000
export ALERTIQ_GRAFANA_SOURCE_ID='<grafana-source-uuid>'
export ALERTIQ_PROMETHEUS_SOURCE_ID='<prometheus-source-uuid>'
export ALERTIQ_GRAFANA_TOKEN='<grafana-webhook-secret>'
export ALERTIQ_PROMETHEUS_TOKEN='<prometheus-webhook-secret>'
export ALERTIQ_ALERTS_PER_MINUTE=30
export ALERTIQ_PROVIDER=alternate   # alternate | random | both | grafana | prometheus

python simulator.py
```

CLI equivalents:

```bash
python simulator.py \
  --base-url http://127.0.0.1:8000 \
  --grafana-source-id '<uuid>' \
  --prometheus-source-id '<uuid>' \
  --grafana-token '<secret>' \
  --prometheus-token '<secret>' \
  --alerts-per-minute 30 \
  --provider alternate \
  --duration 120
```

- **`--alerts-per-minute`**: target **HTTP POST** count per minute. In `both` mode each cycle sends **two** POSTs (Grafana then Prometheus); the interval is stretched so the total POST rate still matches this number.
- **`--provider`**: `alternate` toggles Grafana/Prometheus each cycle; `random` picks one; `both` sends both every cycle; `grafana` / `prometheus` fix the target.
- **`--duration`**: optional cap in seconds; omit to run until Ctrl+C.
- **`--insecure`**: skip TLS certificate verification.

Expect `202` responses with JSON like `{"created":1,"skipped":0}`. Repeated identical payloads would increment `skipped` because of deduplication; this tool avoids that by randomizing fingerprints and timestamps.

## Verify ingestion

```bash
curl -sS "$API/alerts/?limit=5" -H "Authorization: Bearer $TOKEN"
```

When your deployment publishes accepted alerts to Kafka, consuming those topics should show the same traffic end-to-end.
