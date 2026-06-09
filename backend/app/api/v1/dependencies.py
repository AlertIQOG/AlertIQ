"""
Shared FastAPI dependencies for API v1 routes.
"""

import uuid
from typing import Annotated, Any

from fastapi import Depends, Query
from sqlmodel import Session

from app.core.database import get_session
from app.core.exceptions import NotFoundError
from app.models.alert import AlertSeverity, AlertStatus

# Re-usable annotated dependency — avoids repeating ``Depends(get_session)``
# in every single endpoint signature.
DbSession = Annotated[Session, Depends(get_session)]


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
    ) -> None:
        self.severity = severity
        self.status = status
        self.region = region
        self.source_id = source_id
        self.application = application
        self.component = component
        self.node_name = node_name
        self.operator = operator


# ── Parent-resource validators ────────────────────────────────────


def _valid_alert_id(alert_id: uuid.UUID, session: DbSession) -> uuid.UUID:
    """Validate alert exists, raising 404 if not."""
    from app.services.alert import alert_service

    if not alert_service.get(session, id=alert_id):
        raise NotFoundError("Alert", str(alert_id))
    return alert_id


ValidAlertId = Annotated[uuid.UUID, Depends(_valid_alert_id)]

