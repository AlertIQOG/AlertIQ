"""
Shared FastAPI dependencies for API v1 routes.
"""

import secrets
import uuid
from typing import Annotated, Any, Literal

from fastapi import Depends, Header, Query
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session

from app.core.database import get_session
from app.core.exceptions import AuthenticationError, NotFoundError
from app.core.security import decode_access_token
from app.models.alert import AlertSeverity, AlertStatus
from app.models.user import User

# Re-usable annotated dependency — avoids repeating ``Depends(get_session)``
# in every single endpoint signature.
DbSession = Annotated[Session, Depends(get_session)]

# ── Authentication ────────────────────────────────────────────────

# auto_error=False so a missing token raises our domain AuthenticationError
# (mapped to 401 by the exception handlers) instead of a raw HTTPException.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user(
    session: DbSession, token: Annotated[str | None, Depends(oauth2_scheme)]
) -> User:
    """Resolve the ``Authorization: Bearer`` JWT into an active ``User``."""
    if token is None:
        raise AuthenticationError()

    payload = decode_access_token(token)
    if payload is None or "sub" not in payload:
        raise AuthenticationError("Invalid or expired token")

    user = session.get(User, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise AuthenticationError("User is unknown or inactive")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def verify_webhook_token(
    source_id: uuid.UUID,
    session: DbSession,
    x_webhook_token: Annotated[str | None, Header()] = None,
) -> uuid.UUID:
    """
    Authenticate an ingest webhook against its source's secret.

    Subsumes the source-existence check: raises 404 for an unknown source
    and 401 for a missing/wrong token (constant-time compare).
    """
    from app.services.source import source_service

    source = source_service.get(session, id=source_id)
    if source is None:
        raise NotFoundError("Source", str(source_id))

    if source.webhook_secret is None:
        # Source predates webhook auth and has no secret yet — reject
        # rather than silently accept unauthenticated traffic.
        raise AuthenticationError(
            "Source has no webhook secret configured — set one to enable ingest"
        )

    if x_webhook_token is None or not secrets.compare_digest(
        x_webhook_token, source.webhook_secret
    ):
        raise AuthenticationError("Invalid webhook token")
    return source_id


ValidWebhookSourceId = Annotated[uuid.UUID, Depends(verify_webhook_token)]


class PaginationParams:
    """
    Standard pagination query parameters.

    Usage in a route:
        def list_items(pagination: PaginationParams = Depends()):
    """

    def __init__(
        self,
        skip: int = Query(0, ge=0, description="Records to skip"),
        limit: int = Query(100, ge=1, le=500, description="Max records to return"),
    ) -> None:
        self.skip = skip
        self.limit = limit


# Fields the alerts feed may be ordered by — an explicit allow-list so the
# clickable column headers can only request real, safe columns. Severity and
# status are ordered by triage rank (not alphabetically) in ``AlertService``.
AlertSortField = Literal[
    "severity",
    "status",
    "message",
    "region",
    "application",
    "component",
    "impact",
    "node_name",
    "operator",
    "assignee",
    "external_id",
    "created_at",
    "updated_at",
]


class AlertSortParams:
    """
    Ordering query parameters for the alerts endpoint.

    Usage in a route:
        def list_alerts(sort: AlertSortParams = Depends()):
    """

    def __init__(
        self,
        sort_by: AlertSortField = Query(
            "created_at", description="Field to order the feed by"
        ),
        sort_dir: Literal["asc", "desc"] = Query(
            "desc", description="Order direction (ascending or descending)"
        ),
    ) -> None:
        self.sort_by = sort_by
        self.order_desc = sort_dir == "desc"


class FilterParams:
    """
    Base class for filter-parameter dependencies.

    Subclasses declare their own ``Query`` parameters in ``__init__``.
    The ``to_dict()`` helper strips ``None`` values and returns a clean
    ``dict`` ready to be forwarded to ``CRUDBase.get_filtered()``.

    To add a new resource filter class:
        1. Subclass ``FilterParams``.
        2. Declare ``Query(...)`` params in ``__init__``.
        3. That's it — no service-layer changes required.
    """

    def to_dict(self) -> dict[str, Any]:
        """Return only non-``None`` filter values as a plain dict."""
        return {k: v for k, v in vars(self).items() if v is not None}


class AlertFilterParams(FilterParams):
    """
    Optional server-side filter query parameters for the alerts endpoint.

    All parameters are optional.  When multiple are provided they form an
    AND relationship (only alerts matching **all** criteria are returned).

    Adding a new filter is a **one-line change** — just add a ``Query``
    parameter here.  ``CRUDBase.get_filtered`` will resolve it
    automatically against the model's columns or its JSONB field.
    """

    def __init__(
        self,
        severity: AlertSeverity | None = Query(
            None, description="Filter by severity level (e.g. Critical, Warning)"
        ),
        status: AlertStatus | None = Query(
            None, description="Filter by alert status (e.g. Open, Solved)"
        ),
        region: str | None = Query(
            None, description="Filter by region (e.g. PROD, STG)"
        ),
        source_id: uuid.UUID | None = Query(
            None, description="Filter by source / provider ID"
        ),
        application: str | None = Query(
            None, description="Filter by application name (e.g. core-api, payments)"
        ),
        component: str | None = Query(
            None, description="Filter by component (e.g. compute, network, storage)"
        ),
        node_name: str | None = Query(
            None, description="Filter by node name (e.g. prod-node-1)"
        ),
        operator: str | None = Query(
            None, description="Filter by assigned operator"
        ),
        assignee: str | None = Query(
            None, description="Filter by assigned user (username)"
        ),
    ) -> None:
        self.severity = severity
        self.status = status
        self.region = region
        self.source_id = source_id
        self.application = application
        self.component = component
        self.node_name = node_name
        self.operator = operator
        self.assignee = assignee


# ── Parent-resource validators ────────────────────────────────────


def _valid_alert_id(alert_id: uuid.UUID, session: DbSession) -> uuid.UUID:
    """Validate alert exists, raising 404 if not."""
    from app.services.alert import alert_service

    if not alert_service.get(session, id=alert_id):
        raise NotFoundError("Alert", str(alert_id))
    return alert_id


ValidAlertId = Annotated[uuid.UUID, Depends(_valid_alert_id)]

