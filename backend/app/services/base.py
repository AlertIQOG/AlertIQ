"""
Generic CRUD service base class.

Every domain service inherits from this to get standard Create, Read,
Update, Delete operations without duplicating boilerplate.

Rules:
  - Services speak in domain models and domain exceptions only.
  - They never import FastAPI, HTTPException, or status codes.
"""

from typing import Any, Generic, TypeVar

from sqlmodel import Session, SQLModel, select

ModelType = TypeVar("ModelType", bound=SQLModel)


class CRUDBase(Generic[ModelType]):
    """Reusable CRUD operations for any SQLModel table."""

    def __init__(self, model: type[ModelType]) -> None:
        self.model = model

    def get(self, session: Session, *, id: Any) -> ModelType | None:
        """Return a single record by primary key, or ``None``."""
        return session.get(self.model, id)

    def get_multi(
        self, session: Session, *, skip: int = 0, limit: int = 100
    ) -> list[ModelType]:
        """Return a paginated list of records."""
        statement = select(self.model).offset(skip).limit(limit)
        return list(session.exec(statement).all())

    def create(self, session: Session, *, obj_in: ModelType) -> ModelType:
        """Insert a new record and return it refreshed from the DB."""
        session.add(obj_in)
        session.commit()
        session.refresh(obj_in)
        return obj_in

    def update(
        self, session: Session, *, db_obj: ModelType, update_data: dict[str, Any]
    ) -> ModelType:
        """Apply a partial update dict to an existing record."""
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        session.add(db_obj)
        session.commit()
        session.refresh(db_obj)
        return db_obj

    def remove(self, session: Session, *, id: Any) -> ModelType | None:
        """Delete a record by primary key. Returns the deleted object or ``None``."""
        obj = session.get(self.model, id)
        if obj:
            session.delete(obj)
            session.commit()
        return obj
