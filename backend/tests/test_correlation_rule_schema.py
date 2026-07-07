"""
Unit tests for the correlation-rule schemas — focused on the new ``actions``
field (multiselect: aggregate alerts and/or send email).

Pure pydantic validation, no database.
"""

import pytest
from pydantic import ValidationError

from app.schemas.correlation_rule import (
    CorrelationRuleCreate,
    CorrelationRuleRead,
    CorrelationRuleUpdate,
)


def _base_kwargs(**overrides):
    kwargs = dict(
        name="High CPU",
        conditions=[{"field": "cpu_usage", "operator": "greater_than", "value": 90}],
        time_window_minutes=5,
        group_by=["service"],
    )
    kwargs.update(overrides)
    return kwargs


def test_actions_defaults_to_aggregate():
    """Omitting actions keeps the historical behaviour (aggregate only)."""
    rule = CorrelationRuleCreate(**_base_kwargs())
    assert rule.actions == ["aggregate"]


def test_actions_accepts_aggregate_and_email():
    rule = CorrelationRuleCreate(**_base_kwargs(actions=["aggregate", "email"]))
    assert rule.actions == ["aggregate", "email"]


def test_actions_accepts_email_only():
    rule = CorrelationRuleCreate(**_base_kwargs(actions=["email"]))
    assert rule.actions == ["email"]


def test_empty_actions_is_rejected():
    with pytest.raises(ValidationError):
        CorrelationRuleCreate(**_base_kwargs(actions=[]))


def test_unknown_action_is_rejected():
    with pytest.raises(ValidationError):
        CorrelationRuleCreate(**_base_kwargs(actions=["aggregate", "sms"]))


def test_duplicate_actions_are_deduplicated():
    rule = CorrelationRuleCreate(**_base_kwargs(actions=["email", "email", "aggregate"]))
    assert rule.actions == ["email", "aggregate"]


def test_update_actions_can_be_set():
    update = CorrelationRuleUpdate(actions=["email"])
    assert update.actions == ["email"]


def test_update_empty_actions_is_rejected():
    with pytest.raises(ValidationError):
        CorrelationRuleUpdate(actions=[])


def test_read_model_exposes_actions():
    rule = CorrelationRuleRead(
        id="00000000-0000-0000-0000-000000000000",
        name="High CPU",
        enabled=True,
        scope={},
        conditions=[],
        time_window_minutes=5,
        group_by=["service"],
        actions=["aggregate", "email"],
    )
    assert rule.actions == ["aggregate", "email"]
