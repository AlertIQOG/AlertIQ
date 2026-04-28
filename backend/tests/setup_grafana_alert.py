"""
Provision a Grafana alert rule via API that fires immediately,
triggering the AlertIQ webhook contact point.

Steps:
  1. Create a TestData datasource (Grafana built-in, no external DB needed)
  2. Create an alert rule using a fixed-value query that always exceeds the threshold
"""

import httpx
import json
import sys

GRAFANA = "http://localhost:3001"
AUTH = ("admin", "admin")

client = httpx.Client(base_url=GRAFANA, auth=AUTH, timeout=15)


# ── Step 1: Create TestData datasource ───────────────────────────────
print("1. Creating TestData datasource...")
ds_payload = {
    "name": "TestData",
    "type": "testdata",
    "access": "proxy",
    "isDefault": True,
}

r = client.post("/api/datasources", json=ds_payload)
if r.status_code == 200:
    ds_uid = r.json()["datasource"]["uid"]
    print(f"   [OK] Created datasource (uid={ds_uid})")
elif r.status_code == 409:
    # Already exists — fetch its uid
    r2 = client.get("/api/datasources/name/TestData")
    ds_uid = r2.json()["uid"]
    print(f"   [OK] Datasource already exists (uid={ds_uid})")
else:
    print(f"   [FAIL] Failed: {r.status_code} {r.text}")
    sys.exit(1)


# ── Step 2: Create a folder for the alert rule ──────────────────────
print("2. Creating alert folder...")
folder_payload = {"title": "AlertIQ Test Alerts"}
r = client.post("/api/folders", json=folder_payload)
if r.status_code == 200:
    folder_uid = r.json()["uid"]
    print(f"   [OK] Created folder (uid={folder_uid})")
elif r.status_code == 409:
    # Already exists
    r2 = client.get("/api/folders")
    folder_uid = next(f["uid"] for f in r2.json() if f["title"] == "AlertIQ Test Alerts")
    print(f"   [OK] Folder already exists (uid={folder_uid})")
else:
    print(f"   [FAIL] Failed: {r.status_code} {r.text}")
    sys.exit(1)


# ── Step 3: Create the alert rule ───────────────────────────────────
print("3. Creating alert rule (always-firing)...")

rule_group_payload = {
    "name": "alertiq-test-group",
    "interval": "10s",
    "rules": [
        {
            "grafana_alert": {
                "title": "HighCPU - Always Firing",
                "condition": "threshold",
                "no_data_state": "Alerting",
                "exec_err_state": "Alerting",
                "data": [
                    {
                        "refId": "A",
                        "relativeTimeRange": {"from": 60, "to": 0},
                        "datasourceUid": ds_uid,
                        "model": {
                            "refId": "A",
                            "scenarioId": "random_walk",
                            "seriesCount": 1,
                            "hide": False,
                        },
                    },
                    {
                        "refId": "reduce",
                        "relativeTimeRange": {"from": 0, "to": 0},
                        "datasourceUid": "__expr__",
                        "model": {
                            "refId": "reduce",
                            "type": "reduce",
                            "datasource": {"type": "__expr__", "uid": "__expr__"},
                            "reducer": "last",
                            "expression": "A",
                        },
                    },
                    {
                        "refId": "threshold",
                        "relativeTimeRange": {"from": 0, "to": 0},
                        "datasourceUid": "__expr__",
                        "model": {
                            "refId": "threshold",
                            "type": "threshold",
                            "datasource": {"type": "__expr__", "uid": "__expr__"},
                            "expression": "reduce",
                            "conditions": [
                                {
                                    "evaluator": {
                                        "type": "gt",
                                        "params": [-999999],
                                    },
                                    "operator": {"type": "and"},
                                    "reducer": {"type": "last"},
                                }
                            ],
                        },
                    },
                ],
                "labels": {
                    "severity": "critical",
                    "app": "billing-api",
                    "component": "processor",
                    "region": "us-east-1",
                },
                "annotations": {
                    "summary": "CPU usage is extremely high on billing-api",
                    "description": "The billing-api processor has sustained CPU > 90% for over 5 minutes.",
                },
            },
            "for": "0s",
            "annotations": {
                "summary": "CPU usage is extremely high on billing-api",
                "description": "The billing-api processor has sustained CPU > 90% for over 5 minutes.",
            },
            "labels": {
                "severity": "critical",
                "app": "billing-api",
                "component": "processor",
                "region": "us-east-1",
            },
        },
    ],
}

r = client.post(
    f"/api/ruler/grafana/api/v1/rules/{folder_uid}",
    json=rule_group_payload,
    headers={"X-Disable-Provenance": "true"},
)

if r.status_code in (200, 201, 202):
    print(f"   [OK] Alert rule created! Status: {r.status_code}")
else:
    print(f"   [FAIL] Failed: {r.status_code}")
    print(f"   Response: {r.text}")
    sys.exit(1)


print()
print("=" * 60)
print("Done! The alert will fire within ~10 seconds and Grafana")
print("will POST a webhook to your AlertIQ ingest endpoint.")
print()
print("Watch the backend logs for incoming alerts.")
print("Check Grafana Alerting: http://localhost:3001/alerting/list")
print("=" * 60)
