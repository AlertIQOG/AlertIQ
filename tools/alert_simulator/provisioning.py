"""
Auto-provisioning: log in and get-or-create the mock sources.

Point the generator at a running AlertIQ with an admin login and it finds (or
creates) its own Grafana/Prometheus sources and reads back their id + secret.
"""

from __future__ import annotations

from dataclasses import dataclass

from api_client import ApiClient, RequestFailed

# A cascade delete on a big source can take a while server-side (observed
# >30s for ~150 alerts) — give it real room to avoid a false failure.
_DELETE_TIMEOUT = 120.0

DEFAULT_GRAFANA_SOURCE_NAME = "AlertIQ Simulator - Grafana"
DEFAULT_PROMETHEUS_SOURCE_NAME = "AlertIQ Simulator - Prometheus"


class ProvisioningError(RuntimeError):
    pass


@dataclass(frozen=True)
class SourceInfo:
    id: str
    webhook_secret: str


def login(client: ApiClient, username: str, password: str) -> None:
    """OAuth2 password login; sets ``client.headers["Authorization"]``.

    No-op if already authenticated, so callers can call it defensively.
    """
    if "Authorization" in client.headers:
        return
    status, body = client.post("/auth/login", form={"username": username, "password": password})
    token = body.get("access_token") if isinstance(body, dict) else None
    if status != 200 or not token:
        raise ProvisioningError(f"login failed for user {username!r}: HTTP {status} {body}")
    client.headers["Authorization"] = f"Bearer {token}"


_LIST_PAGE_SIZE = 500  # backend's max allowed `limit`


def _find_source(client: ApiClient, *, name: str, provider_type: str) -> dict | None:
    """Search every source, paging through the backend's max page size."""
    skip = 0
    while True:
        status, page = client.get("/sources/", params={"skip": skip, "limit": _LIST_PAGE_SIZE})
        if status != 200:
            raise ProvisioningError(f"listing sources failed: HTTP {status} {page}")
        for source in page:
            if source.get("name") == name and source.get("provider_type") == provider_type:
                return source
        if len(page) < _LIST_PAGE_SIZE:
            return None
        skip += _LIST_PAGE_SIZE


def ensure_source(
    client: ApiClient,
    *,
    name: str,
    provider_type: str,
) -> SourceInfo:
    """Find a source by name, creating it if it doesn't exist yet.

    ``SourceRead`` includes ``webhook_secret`` on both list and create, so an
    existing source's secret can be recovered without rotating it.
    """
    existing = _find_source(client, name=name, provider_type=provider_type)
    if existing is not None:
        return SourceInfo(id=existing["id"], webhook_secret=existing["webhook_secret"])

    status, created = client.post(
        "/sources/", json_body={"name": name, "provider_type": provider_type}
    )
    if status != 201:
        raise ProvisioningError(f"creating source {name!r} failed: HTTP {status} {created}")
    return SourceInfo(id=created["id"], webhook_secret=created["webhook_secret"])


def delete_source_if_exists(client: ApiClient, *, name: str, provider_type: str) -> bool:
    """Delete the exact-named source (cascade-deletes its alerts) if it exists.

    Exact match only, never a pattern — never touches anything but this
    tool's own sources. On a client-side timeout, re-checks whether the
    delete actually finished server-side before reporting failure.
    """
    existing = _find_source(client, name=name, provider_type=provider_type)
    if existing is None:
        return False

    try:
        status, body = client.request(
            "DELETE", f"/sources/{existing['id']}", timeout=_DELETE_TIMEOUT
        )
    except RequestFailed:
        if _find_source(client, name=name, provider_type=provider_type) is None:
            return True  # timed out client-side, but it did finish
        raise

    if status != 204:
        raise ProvisioningError(f"deleting source {name!r} failed: HTTP {status} {body}")
    return True
