# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What AlertIQ is

AlertIQ is an academic degree final project (פרויקט גמר). It ingests alerts from external monitoring providers (Grafana unified alerting, Prometheus Alertmanager), normalizes them into a single internal model, deduplicates them, and presents them through a web UI for triage and incident management. It is a monorepo with three independent parts:

- `backend/` — FastAPI + SQLModel (PostgreSQL) REST API. The system of record.
- `frontend/` — Next.js 16 (App Router) + React 19 + Tailwind v4 dashboard.
- `tools/alert_simulator/` — a standalone Python script that fires realistic Grafana/Prometheus webhook traffic at the backend for local testing.

## Commands

### Backend (run from `backend/`)
```bash
# Full dev stack: backend + PostgreSQL + Grafana + Prometheus + Alertmanager
docker compose up -d            # Grafana :3001 (admin/admin), Postgres :5432, Prometheus :9090, Alertmanager :9093

# Run the API directly (needs a reachable PostgreSQL — set DATABASE_URL)
uvicorn app.main:app --reload   # http://localhost:8000 ; OpenAPI docs at /docs

pytest                          # run all tests
pytest tests/test_grafana_normalizer.py            # single file
pytest tests/test_grafana_normalizer.py::test_name # single test

ruff check .                    # lint (rules: E, F, I; line length 88)
ruff format .                   # format
mypy app                        # type-check (non-strict)
```
Note: `tests/e2e_ingest.py` and `tests/setup_grafana_alert.py` are manual integration scripts, not pytest tests (they lack the `test_` filename prefix and are not auto-collected).

Testing reality: there is **no conftest.py and no test-DB fixture**. Existing tests are pure-logic tests (normalizers, `test_security.py`, `test_user_service.py`) plus `TestClient` tests with monkeypatched service singletons (`test_health.py`, `test_auth.py`); anything DB-backed needs a real reachable PostgreSQL (importing `app.main` runs `create_all`, so even TestClient tests need `DATABASE_URL` to resolve). There is also no CI (`.github/workflows/` does not exist) — lint/type/test runs are manual. Note: `ruff check`/`mypy`/`eslint` currently report pre-existing violations on files untouched by recent work; keep new code clean rather than fixing the backlog in unrelated PRs.

### Frontend (run from `frontend/`)
```bash
npm run dev     # Next dev server on :3000
npm run build
npm run lint    # eslint (flat config, eslint-config-next)
```
There is no frontend test suite.

### Simulator (run from `tools/alert_simulator/`)
`python simulator.py` — see `tools/alert_simulator/README.md`. Requires existing source UUIDs created via `POST /api/v1/sources/` **and their webhook secrets** (`--grafana-token` / `--prometheus-token` or `ALERTIQ_*_TOKEN` env vars) since ingest requires `X-Webhook-Token`. Randomizes fingerprints/timestamps so requests don't dedupe.

## Backend architecture

Strict layering, enforced by convention — keep it intact:

```
api/v1/*.py   → thin routers: validate (Pydantic schema) → delegate to service → return *Read schema
services/*.py → business logic; speak only in domain models + domain exceptions
models/*.py   → SQLModel table definitions
schemas/*.py  → Pydantic Create/Read/Update DTOs (responses NEVER return raw DB models)
core/*.py     → config, database engine/session, logging, exceptions
providers/*.py→ webhook adapters that normalize provider payloads into AlertCreate
```

Key invariants to respect when editing:

- **Services never import FastAPI / HTTPException / status codes.** They raise domain exceptions (`NotFoundError`, `ConflictError`, `AuthenticationError` → 401, `AuthorizationError` → 403 in `core/exceptions.py`), which are mapped to HTTP responses by handlers registered in `register_exception_handlers`. Routers raise `NotFoundError` directly when a resource is missing.
- **Authentication (two mechanisms).** Human users: JWT bearer tokens (`core/security.py` — bcrypt password hashing + PyJWT HS256 signed with `SECRET_KEY`). `POST /auth/login` (OAuth2 password form, works with the /docs Authorize button) returns `{access_token, user}`; `GET /auth/me` echoes the current user. `get_current_user` in `api/v1/dependencies.py` resolves the token; it is applied **per-router in `api/v1/router.py`** via `dependencies=protected` — individual routers/services stay auth-agnostic. Unprotected: `/health` (uptime checks), `/auth` (login itself), `/ingest` (webhook secrets instead). Machine webhooks: each `Source` has a server-generated `webhook_secret` (returned by the sources API); ingest requests must send it as `X-Webhook-Token` (constant-time compared in `verify_webhook_token`; missing/wrong → 401, source with NULL secret → 401). There is no self-registration — create the first admin with `python -m app.scripts.create_admin <user> <password>`.
- **Alert `assignee`** is a dedicated nullable column (the username of the assigned user), distinct from the provider-supplied `operator` field — don't conflate them. Set via `PATCH /alerts/{id}`, filterable via `?assignee=`.
- **`CRUDBase` (`services/base.py`) is the generic CRUD layer.** Domain services subclass it (e.g. `AlertService`) or instantiate it directly (`incident_service = CRUDBase(Incident)`, `note_service`). Its `get_filtered` uses SQLAlchemy column introspection to build WHERE clauses dynamically: a filter key that matches a model column becomes `col = value`; otherwise it falls back to probing the model's first JSONB column (`jsonb_col->>key = value`). **Consequence: adding a new server-side filter is a one-line change** — add a `Query` param to the relevant `FilterParams` subclass in `api/v1/dependencies.py`; no service change needed.
- **Provider normalizers are duck-typed**, not inherited. Any object with a `normalize(source_id, payload) -> list[AlertCreate]` method satisfies the `AlertNormalizer` Protocol (`providers/base.py`). Each provider exports a module-level singleton (`grafana_normalizer`, `prometheus_normalizer`). To add a provider: write a normalizer + a Pydantic webhook schema, then add a route in `api/v1/ingest.py`.
- **Deduplication / upsert.** Alerts have a unique constraint on `(source_id, external_id)`. Ingest calls `alert_service.upsert`, which on re-fire updates **only** `severity`/`extra_fields`/`impact` — `created_at`, `message`, `application`, `component`, `region`, `node_name`, `operator` are never touched. Status is overwritten only when the provider reports `SOLVED` — user-set workflow states (`In progress`, `Dismissed`) are preserved across re-fires. `external_id` is the provider fingerprint. Don't "improve" upsert to update more fields; the narrow update set is intentional.
- **Alert aggregation** (`POST /alerts/aggregate`, `AlertService.aggregate`). Groups selected alerts into one aggregated alert: children are marked `Dismissed`, the parent takes the highest child severity, gets a fresh UUID as `external_id`, and carries `child_ids` / `child_count` / `_is_aggregated` in `extra_fields`. The frontend bulk-action bar (`aggregateAlerts()` in `alertsApi.ts`) drives it.
- **Correlation rules** (`models/correlation_rule.py`, `services/correlation_rule.py`, `api/v1/correlation_rule.py`). Full CRUD at `/correlation-rules` plus `PATCH /{id}/status` to toggle `enabled`. `conditions` is a JSONB list of `{field, operator, value}` dicts validated against the `AllowedOperator` enum in `schemas/correlation_rule.py`; `scope` and `group_by` are also JSONB. The service adds `get_active()` and `set_enabled()` on top of `CRUDBase`.
- **`extra_fields` (JSONB)** holds the full original provider payload (labels, annotations, fingerprint, timestamps) for reference and is the JSONB target for dynamic filtering.
- **Schema autocreation.** `core/database.py` imports `app.models` and calls `SQLModel.metadata.create_all(engine)` at import time. There is **no Alembic** — new tables are created from the models on startup, but changes to existing tables won't auto-apply. Manual SQL for such changes lives in `backend/migrations/` (e.g. `auth_migration.sql` adds `alerts.assignee` + `sources.webhook_secret` and backfills secrets); run it against an existing DB before deploying the code that needs it.

API is mounted under `/api/v1`. Routers: `/health`, `/auth` (`login`, `me`), `/sources`, `/alerts` (incl. `POST /aggregate`), `/alerts/{alert_id}/notes`, `/ingest/{grafana|prometheus}/{source_id}`, `/incidents`, `/correlation-rules`. All except `/health`, `/auth`, and `/ingest` require a bearer token.

Other backend facts worth knowing:

- **Config** (`core/config.py`): `DATABASE_URL` (default points at the docker-compose Postgres), `SECRET_KEY` (JWT signing — has an insecure dev default; set a real one in `.env`), `ACCESS_TOKEN_EXPIRE_MINUTES` (default 480), `DEBUG=true` enables SQL echo, `ALLOWED_ORIGINS` is the CORS list. `Settings` uses `extra="ignore"` so `.env` vars belonging to other branches (e.g. RAG) don't crash startup.
- **Incident model** (`models/incident.py`): `priority` P1–P4, `stage` Open/In Progress/Resolved, `source` (`"manual"` or set when promoted from an alert), `linked_alert_id` FK, `affected_services` JSONB. Its `notes` field is a **plain string** unrelated to the `Note` table — a second notes divergence beyond the one documented below. Service is a bare `CRUDBase(Incident)`.

## Frontend architecture

- Next.js App Router. Global layout (`app/layout.tsx`) delegates to `app/components/AppShell.tsx` (client component): it renders the persistent sidebar (Alerts Feed `/`, Incidents `/incidents`, Correlation `/correlation`) with the logged-in user + logout button, and **redirects to `/login` when no token is stored** (UX guard only — real enforcement is the backend's 401s). Routes: `/login`, `/`, `/incidents`, `/incidents/[id]`, `/correlation`, `/correlation/new`. **Every page is `'use client'`** — there is no server rendering, no middleware, no Next API routes.
- **Auth session:** `app/services/apiClient.ts` owns the base URL (`NEXT_PUBLIC_API_URL`, default `http://localhost:8000/api/v1`), the token/user in localStorage (`alertiq-auth-token` / `alertiq-auth-user`), and `apiFetch()` — a fetch wrapper that injects `Authorization: Bearer` and on any 401 clears the session and redirects to `/login`. `authApi.ts` has `login()`/`logout()`. All API calls (including the correlation pages) go through `apiFetch` — the old `NEXT_PUBLIC_API_BASE_URL` split is resolved; don't reintroduce raw `fetch` calls to the backend.
- API access goes through `app/services/*.ts` (`alertsApi.ts`, `incidentsApi.ts`). These functions swallow errors and return `[]`/`null` rather than throwing, and convert backend snake_case ↔ frontend camelCase via explicit normalize/denormalize helpers in each file.
- No global state library — component `useState` only. No polling: data loads on mount with manual refresh callbacks. Column visibility persists to localStorage (key `alertiq-visible-columns`; registry in `app/data/columnConfig.ts` — a utility, not a mock). Icons are Font Awesome via CDN `<link>` in `layout.tsx`.
- Shared types in `app/types/` (`alert.ts` incl. `isAggregated`/`childCount`, `incident.ts`, `correlation.ts`); reusable UI in `app/components/` (`DataTable`, `AlertsTable`, `PageHeader`, `AlertDetailsPanel`, `ColumnPicker`, `PromoteToIncidentModal`) plus `app/correlation/components/CorrelationRulesTable.tsx`.
- Mock data: `app/data/mockAlerts.ts` is dead code (the feed hits the real API). `app/data/mockIncidents.ts` is a **live fallback** — the incidents page shows it whenever the API returns an empty list, so incidents you see in the UI may not exist in the DB.

## Alert notes — known divergence

The **`Note` table + `/api/v1/alerts/{alert_id}/notes` endpoints is the canonical design** (`models/note.py`, `services/note.py`, `api/v1/notes.py`). The frontend (`alertsApi.ts`) currently takes a shortcut, storing notes inside the alert's `extra_fields._notes` JSONB array via `PATCH /alerts/{id}` instead. New notes work should move toward the Note-table API rather than extending the `extra_fields._notes` approach.

## Resolution Copilot — not on main

A RAG-based "Resolution Copilot" (pgvector embeddings, semantic retrieval over solved alerts, grounded LLM suggestions) lives on the **unmerged `feat/alert-fix-suggestion` branch (PR #23)**. On `main` there is **no source for it** — `backend/app/services/rag/` and `backend/app/scripts/` contain only leftover `.pyc` artifacts, and `requirements.txt` has no LLM/pgvector deps. Don't chase that ghost code on `main`; the feature plan is in `docs/resolution-copilot-tasks.md`.

## Conventions

- Python targets 3.12. Use type hints; keep the router/service/schema separation. Match the existing docstring style (module-level docstrings explaining the layer's role).
- Enum values are human-facing title-case strings (e.g. `AlertStatus.IN_PROGRESS = "In progress"`), while incoming provider values are lowercase and mapped in the normalizer.
- Work happens on feature branches merged via PR to `main` (see git history).
- **Keep this file current:** a PR that adds an endpoint, page, component, or env var should update CLAUDE.md in the same change.