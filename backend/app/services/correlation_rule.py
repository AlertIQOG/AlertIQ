import uuid
from datetime import datetime

from sqlalchemy import update
from sqlmodel import Session, select

from app.models.correlation_rule import CorrelationRule
from app.services.base import CRUDBase


class CorrelationRuleService(CRUDBase[CorrelationRule]):
    def get_active(self, session: Session) -> list[CorrelationRule]:
        statement = select(CorrelationRule).where(CorrelationRule.enabled == True)
        return list(session.exec(statement).all())

    def touch_last_triggered(
        self,
        session: Session,
        *,
        rule: CorrelationRule,
        now: datetime,
    ) -> None:
        """Record that ``rule`` just matched an alert.

        A targeted UPDATE that pins ``updated_at`` to its current value —
        ``updated_at`` means "configuration last edited", and the column's
        ``onupdate`` would otherwise bump it on every match.
        """
        session.execute(
            update(CorrelationRule)
            .where(CorrelationRule.id == rule.id)  # type: ignore[arg-type]
            .values(last_triggered_at=now, updated_at=CorrelationRule.updated_at)
        )
        session.commit()

    def set_enabled(
        self,
        session: Session,
        *,
        rule_id: uuid.UUID,
        enabled: bool,
    ) -> CorrelationRule | None:
        rule = self.get(session, id=rule_id)

        if not rule:
            return None

        rule.enabled = enabled
        session.add(rule)
        session.commit()
        session.refresh(rule)
        return rule


correlation_rule_service = CorrelationRuleService(CorrelationRule)