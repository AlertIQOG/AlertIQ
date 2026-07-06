"""
Aggregated Alert model.

An ``AggregatedAlert`` is a *container* produced by the correlation engine
(:mod:`app.services.correlation_engine`).  When an incoming alert matches an
active correlation rule, it is grouped — together with other alerts sharing the
same ``group_by`` values — into one of these rows instead of being surfaced as
an isolated alert.

Lifecycle:
  - ``OPEN``   — the correlation time-window is still active; new matching
                 alerts are folded in (``count`` / ``severity`` / ``last_seen``
                 are updated).
  - ``CLOSED`` — the time-window elapsed (or it was closed manually); further
                 matching alerts open a fresh aggregate instead.

This is a distinct concept from the *manual* aggregation performed by
``AlertService.aggregate`` (which collapses hand-picked alerts into a summary
``Alert`` row flagged with ``extra_fields._is_aggregated``).
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import Column, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.models.alert import AlertSeverity


class AggregatedAlertStatus(str, Enum):
    """Whether the aggregate is still accepting new members."""

    OPEN = "Open"
    CLOSED = "Closed"


class AggregatedAlert(SQLModel, table=True):
    __tablename__ = "aggregated_alerts"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    # The correlation rule that produced this aggregate (snapshot of the name
    # is kept so the aggregate is still readable if the rule is later renamed
    # or deleted).
    rule_id: uuid.UUID = Field(foreign_key="correlation_rules.id", index=True)
    rule_name: str

    title: str

    # Canonical, deterministic key built from the rule's ``group_by`` values,
    # e.g. ``"service=payments|host=web-01"``.  Together with ``rule_id`` and an
    # ``OPEN`` status this identifies the single aggregate an alert belongs to.
    group_key: str = Field(index=True)

    # The raw field/value pairs behind ``group_key`` — handy for the UI.
    group_values: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))

    # Highest severity seen among the member alerts.
    severity: AlertSeverity

    status: AggregatedAlertStatus = Field(default=AggregatedAlertStatus.OPEN, index=True)

    # Number of distinct member alerts folded into this aggregate.
    count: int = Field(default=0)

    # IDs (as strings) of the member alerts — the source of truth for
    # deduplication (a re-fired alert must not be counted twice).
    alert_ids: list[str] = Field(default_factory=list, sa_column=Column(JSONB))

    # Populated when the aggregate is closed, e.g. ``"window_expired"``.
    close_reason: str | None = Field(default=None)

    # Window bookkeeping (all timezone-aware).
    first_seen: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    last_seen: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    # ``first_seen + rule.time_window_minutes`` — snapshotted at creation so the
    # window is stable even if the rule is edited afterwards.
    window_ends_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )

    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), nullable=False
        ),
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        ),
    )
