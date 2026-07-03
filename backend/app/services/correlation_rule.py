import uuid

from sqlmodel import Session, select

from app.models.correlation_rule import CorrelationRule
from app.services.base import CRUDBase


class CorrelationRuleService(CRUDBase[CorrelationRule]):
    def get_active(self, session: Session) -> list[CorrelationRule]:
        statement = select(CorrelationRule).where(CorrelationRule.enabled == True)
        return list(session.exec(statement).all())

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