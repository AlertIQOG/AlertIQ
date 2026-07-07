import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


AllowedOperator = Literal[
    "equals",
    "not_equals",
    "contains",
    "greater_than",
    "less_than",
    "greater_or_equal",
    "less_or_equal",
    "is_present",
]

# Actions a rule can run when it matches. Exposed as a multiselect in the UI.
CorrelationAction = Literal["aggregate", "email"]


def _dedupe_actions(actions: list[str]) -> list[str]:
    """Drop duplicates while preserving the order the user selected them in."""
    seen: list[str] = []
    for action in actions:
        if action not in seen:
            seen.append(action)
    return seen


class CorrelationCondition(BaseModel):
    field: str
    operator: AllowedOperator
    value: str | int | float | bool | None = None


class CorrelationRuleBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    enabled: bool = True
    scope: dict[str, Any] = Field(default_factory=dict)
    conditions: list[CorrelationCondition] = Field(min_length=1)
    time_window_minutes: int = Field(gt=0, le=1440)
    group_by: list[str] = Field(min_length=1)
    actions: list[CorrelationAction] = Field(default_factory=lambda: ["aggregate"], min_length=1)

    @field_validator("actions")
    @classmethod
    def dedupe_actions(cls, actions: list[str]) -> list[str]:
        return _dedupe_actions(actions)


class CorrelationRuleCreate(CorrelationRuleBase):
    @model_validator(mode="after")
    def validate_rule(self) -> "CorrelationRuleCreate":
        if not self.name.strip():
            raise ValueError("Rule name cannot be empty")

        if not self.conditions:
            raise ValueError("Rule must contain at least one condition")

        if not self.group_by:
            raise ValueError("Rule must contain at least one group_by field")

        if not self.actions:
            raise ValueError("Rule must contain at least one action")

        return self


class CorrelationRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    enabled: bool | None = None
    scope: dict[str, Any] | None = None
    conditions: list[CorrelationCondition] | None = None
    time_window_minutes: int | None = Field(default=None, gt=0, le=1440)
    group_by: list[str] | None = None
    actions: list[CorrelationAction] | None = Field(default=None, min_length=1)

    @field_validator("actions")
    @classmethod
    def dedupe_actions(cls, actions: list[str] | None) -> list[str] | None:
        return _dedupe_actions(actions) if actions is not None else None


class CorrelationRuleRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    description: str | None = None
    enabled: bool
    scope: dict[str, Any]
    conditions: list[dict[str, Any]]
    time_window_minutes: int
    group_by: list[str]
    actions: list[str] = Field(default_factory=lambda: ["aggregate"])
    created_at: datetime | None = None
    updated_at: datetime | None = None