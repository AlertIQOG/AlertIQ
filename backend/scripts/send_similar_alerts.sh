#!/usr/bin/env bash
#
# send_similar_alerts.sh — seed two semantically-similar alerts: one Solved
# (indexed into RAG as a precedent) and one Open (a query alert you can run
# "Generate suggestion" on).
#
# The two alerts share message/application/component/region (so their embedded
# text matches) but differ by node_name, which keeps their external_id distinct
# so neither upserts over the other.
#
# The Solved alert is marked Solved via PATCH (which triggers indexing) and gets
# a resolution note — so the Resolution Copilot has a real precedent to cite
# when you generate a suggestion on the Open one.
#
# Requirements: curl (no jq needed). A running backend and valid credentials.
#
# Usage:
#   ./send_similar_alerts.sh
#   ALERTIQ_API=http://localhost:8000/api/v1 ALERTIQ_USER=admin ALERTIQ_PASS=secret ./send_similar_alerts.sh
#
set -euo pipefail

BASE_URL="${ALERTIQ_API:-http://localhost:8000/api/v1}"
USERNAME="${ALERTIQ_USER:-ttt}"
PASSWORD="${ALERTIQ_PASS:-tttttttt}"

# Shared (identity) fields — keep these equal so the alerts are "similar".
# Avoid double quotes / backslashes here (values are embedded into JSON below).
MESSAGE="Disk usage above 90% on the payments database"
APPLICATION="payments"
COMPONENT="database"
REGION="us-east-1"
SEVERITY="Critical"   # one of: Info | Warning | Error | Critical
IMPACT="Checkout writes slowing down; risk of failed transactions"

command -v curl >/dev/null 2>&1 || { echo "error: 'curl' is required but not installed." >&2; exit 1; }

# Extract the first string value for a top-level JSON key from stdin.
# Good enough for the flat fields we read (access_token, id) without jq.
json_field() {
  grep -o "\"$1\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" | head -1 | sed 's/.*:[[:space:]]*"//; s/"$//'
}

echo "==> Logging in as '$USERNAME' at $BASE_URL"
LOGIN=$(curl -sS -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "username=$USERNAME" \
  --data-urlencode "password=$PASSWORD")
TOKEN=$(printf '%s' "$LOGIN" | json_field access_token)
if [ -z "$TOKEN" ]; then
  echo "error: login failed. Response:" >&2
  echo "$LOGIN" >&2
  exit 1
fi

# Authenticated request helper: api METHOD PATH [JSON_BODY]
api() {
  local method="$1" path="$2" body="${3:-}"
  if [ -n "$body" ]; then
    curl -sS -X "$method" "$BASE_URL$path" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d "$body"
  else
    curl -sS -X "$method" "$BASE_URL$path" \
      -H "Authorization: Bearer $TOKEN"
  fi
}

echo "==> Finding a source to attach the alerts to"
SOURCE_ID=$(api GET "/sources/" | json_field id)
if [ -z "$SOURCE_ID" ]; then
  echo "    no source found — creating one"
  SOURCE_ID=$(api POST "/sources/" '{"name":"demo-seed","provider_type":"manual"}' | json_field id)
fi
[ -n "$SOURCE_ID" ] || { echo "error: could not obtain a source id." >&2; exit 1; }
echo "    using source_id=$SOURCE_ID"

# Build an alert body for a given node_name + status.
alert_body() {
  local node="$1" status="$2"
  cat <<JSON
{"source_id":"$SOURCE_ID","message":"$MESSAGE","application":"$APPLICATION","component":"$COMPONENT","region":"$REGION","severity":"$SEVERITY","impact":"$IMPACT","node_name":"$node","status":"$status"}
JSON
}

echo "==> Creating the SOLVED alert (precedent)"
SOLVED_ID=$(api POST "/alerts/" "$(alert_body 'prod-payments-db-1' 'Open')" | json_field id)
[ -n "$SOLVED_ID" ] || { echo "error: failed to create solved alert." >&2; exit 1; }

# Direct creation does not index; transitioning to Solved via PATCH does.
api PATCH "/alerts/$SOLVED_ID" '{"status":"Solved"}' >/dev/null

# A resolution note makes it a useful precedent (and re-indexes the alert with
# the note included, via the /notes endpoint).
NOTE_BODY='{"author":"oncall","content":"Root cause: archived WAL filled the volume. Cleared old WAL segments and expanded the disk by 50GB. Write latency returned to baseline after 30m of monitoring."}'
api POST "/alerts/$SOLVED_ID/notes/" "$NOTE_BODY" >/dev/null
echo "    solved_id=$SOLVED_ID (Solved, indexed, 1 resolution note)"

echo "==> Creating the OPEN alert (query)"
OPEN_ID=$(api POST "/alerts/" "$(alert_body 'prod-payments-db-2' 'Open')" | json_field id)
[ -n "$OPEN_ID" ] || { echo "error: failed to create open alert." >&2; exit 1; }
echo "    open_id=$OPEN_ID (Open)"

echo
echo "Done. Two similar alerts created:"
echo "  - SOLVED precedent : $SOLVED_ID  (node prod-payments-db-1)"
echo "  - OPEN query       : $OPEN_ID  (node prod-payments-db-2)"
echo
echo "Try it: open the OPEN alert in the UI and click 'Generate suggestion' —"
echo "the copilot should retrieve the SOLVED alert (and its note) as precedent."
