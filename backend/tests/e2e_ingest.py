"""Quick E2E test: POST a Grafana webhook payload to the ingest endpoint."""
import httpx
import json

SOURCE_ID = "1d625724-8d0b-4aac-8d7d-0a102c9914a0"

payload = {
    "status": "firing",
    "alerts": [
        {
            "status": "firing",
            "labels": {
                "alertname": "HighCPU",
                "severity": "critical",
                "app": "billing-api",
                "component": "processor",
                "region": "us-east-1",
            },
            "annotations": {
                "summary": "CPU usage above 90%",
                "description": "billing-api processor has high CPU for 5m.",
            },
            "startsAt": "2026-04-28T10:00:00Z",
            "endsAt": "0001-01-01T00:00:00Z",
            "fingerprint": "abc123def456",
            "values": {"A": 95.2},
        },
        {
            "status": "resolved",
            "labels": {
                "alertname": "MemoryLeak",
                "severity": "warning",
                "job": "auth-service",
                "component": "cache",
                "region": "eu-west-1",
            },
            "annotations": {"summary": "Memory leak resolved"},
            "fingerprint": "mem222resolved",
            "values": {},
        },
    ],
    "commonLabels": {"alertname": "HighCPU"},
    "commonAnnotations": {},
    "externalURL": "http://grafana.local",
    "groupLabels": {"alertname": "HighCPU"},
}

url = f"http://localhost:8000/api/v1/ingest/grafana/{SOURCE_ID}"

print(f"POST {url}")
r = httpx.post(url, json=payload)
print(f"Status: {r.status_code}")
print(f"Response: {json.dumps(r.json(), indent=2)}")

print("\n--- Sending same payload again (expect updated=2, created=0) ---")
r2 = httpx.post(url, json=payload)
print(f"Status: {r2.status_code}")
print(f"Response: {json.dumps(r2.json(), indent=2)}")
assert r2.json().get("updated") == 2, "Expected existing alerts to be updated, not re-created"

print("\n--- Checking alerts in DB ---")
r3 = httpx.get("http://localhost:8000/api/v1/alerts/", params={"source_id": SOURCE_ID})
print(f"Alerts count: {len(r3.json())}")
for a in r3.json():
    print(f"  - {a['message']} | {a['severity']} | {a['status']} | app={a['application']}")
