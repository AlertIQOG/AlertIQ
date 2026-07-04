import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


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


class CorrelationRuleCreate(CorrelationRuleBase):
    @model_validator(mode="after")
    def validate_rule(self) -> "CorrelationRuleCreate":
        if not self.name.strip():
            raise ValueError("Rule name cannot be empty")

        if not self.conditions:
            raise ValueError("Rule must contain at least one condition")

        if not self.group_by:
            raise ValueError("Rule must contain at least one group_by field")

        return self


class CorrelationRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    enabled: bool | None = None
    scope: dict[str, Any] | None = None
    conditions: list[CorrelationCondition] | None = None
    time_window_minutes: int | None = Field(default=None, gt=0, le=1440)
    group_by: list[str] | None = None


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
    created_at: datetime | None = None
    updated_at: datetime | None = None