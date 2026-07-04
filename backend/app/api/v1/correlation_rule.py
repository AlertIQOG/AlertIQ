import uuid

from fastapi import APIRouter, Query, status

from app.api.v1.dependencies import DbSession
from app.core.exceptions import NotFoundError
from app.models.correlation_rule import CorrelationRule
from app.schemas.correlation_rule import (
    CorrelationRuleCreate,
    CorrelationRuleRead,
    CorrelationRuleUpdate,
)
from app.services.correlation_rule import correlation_rule_service

router = APIRouter()


@router.post("/", response_model=CorrelationRuleRead, status_code=status.HTTP_201_CREATED)
def create_correlation_rule(
    *,
    session: DbSession,
    body: CorrelationRuleCreate,
) -> CorrelationRuleRead:
    db_obj = CorrelationRule.model_validate(body.model_dump())
    created = correlation_rule_service.create(session, obj_in=db_obj)
    return created


@router.get("/", response_model=list[CorrelationRuleRead])
def list_correlation_rules(
    *,
    session: DbSession,
    enabled: bool | None = Query(default=None),
) -> list[CorrelationRuleRead]:
    if enabled is True:
        return correlation_rule_service.get_active(session)

    if enabled is False:
        return correlation_rule_service.get_filtered(
            session,
            filters={"enabled": False},
            skip=0,
            limit=500,
        )

    return correlation_rule_service.get_multi(session, skip=0, limit=500)


@router.get("/{rule_id}", response_model=CorrelationRuleRead)
def get_correlation_rule(
    *,
    session: DbSession,
    rule_id: uuid.UUID,
) -> CorrelationRuleRead:
    rule = correlation_rule_service.get(session, id=rule_id)

    if not rule:
        raise NotFoundError("CorrelationRule", str(rule_id))

    return rule


@router.patch("/{rule_id}", response_model=CorrelationRuleRead)
def update_correlation_rule(
    *,
    session: DbSession,
    rule_id: uuid.UUID,
    body: CorrelationRuleUpdate,
) -> CorrelationRuleRead:
    rule = correlation_rule_service.get(session, id=rule_id)

    if not rule:
        raise NotFoundError("CorrelationRule", str(rule_id))

    update_data = body.model_dump(exclude_unset=True)
    updated = correlation_rule_service.update(
        session,
        db_obj=rule,
        update_data=update_data,
    )

    return updated


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_correlation_rule(
    *,
    session: DbSession,
    rule_id: uuid.UUID,
) -> None:
    rule = correlation_rule_service.remove(session, id=rule_id)

    if not rule:
        raise NotFoundError("CorrelationRule", str(rule_id))


@router.patch("/{rule_id}/status", response_model=CorrelationRuleRead)
def update_correlation_rule_status(
    *,
    session: DbSession,
    rule_id: uuid.UUID,
    enabled: bool,
) -> CorrelationRuleRead:
    rule = correlation_rule_service.set_enabled(
        session,
        rule_id=rule_id,
        enabled=enabled,
    )

    if not rule:
        raise NotFoundError("CorrelationRule", str(rule_id))

    return rule