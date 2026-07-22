"""
Generic CRUD service base class.

Every domain service inherits from this to get standard Create, Read,
Update, Delete operations without duplicating boilerplate.

The ``get_filtered`` method uses **SQLAlchemy introspection** to
dynamically build ``WHERE`` clauses from a plain ``dict``.  This means
new filters can be added at the API layer (dependency classes) without
touching any service code.

Rules:
  - Services speak in domain models and domain exceptions only.
  - They never import FastAPI, HTTPException, or status codes.
"""

from typing import Any, Generic, TypeVar

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects.postgresql import JSONB as JSONB_TYPE
from sqlmodel import Session, SQLModel, select

ModelType = TypeVar("ModelType", bound=SQLModel)


class CRUDBase(Generic[ModelType]):
    """Reusable CRUD operations for any SQLModel table."""

    def __init__(self, model: type[ModelType]) -> None:
        self.model = model
        self._column_names, self._jsonb_field = self._inspect_columns(model)

    # ── Column introspection ──────────────────────────────────────

    @staticmethod
    def _inspect_columns(model: type[SQLModel]) -> tuple[set[str], str | None]:
        """
        Inspect a SQLModel class and return its column metadata.

        Returns:
            A tuple of ``(column_names, jsonb_field)`` where
            ``jsonb_field`` is the attribute name of the first JSONB
            column found (or ``None`` if the model has no JSONB column).
        """
        mapper = sa_inspect(model)
        column_names: set[str] = set()
        jsonb_field: str | None = None

        for attr in mapper.column_attrs:
            column_names.add(attr.key)
            if jsonb_field is None:
                for col in attr.columns:
                    if isinstance(col.type, JSONB_TYPE):
                        jsonb_field = attr.key
                        break

        return column_names, jsonb_field

    # ── Read ──────────────────────────────────────────────────────

    def _apply_filters(self, statement: Any, filters: dict[str, Any]) -> Any:
        """Attach ``WHERE`` clauses for each non-``None`` filter to ``statement``.

        Resolution mirrors ``get_filtered``: a key matching a model column emits
        ``column = value``; otherwise it probes the model's JSONB field. Shared
        so subclasses can build custom-ordered queries without duplicating this.
        """
        for field, value in filters.items():
            if value is None:
                continue

            if field in self._column_names:
                # Direct column match -> standard WHERE clause
                statement = statement.where(getattr(self.model, field) == value)
            elif self._jsonb_field is not None:
                # Not a column -> probe inside the JSONB field
                jsonb_col = getattr(self.model, self._jsonb_field)
                statement = statement.where(jsonb_col[field].astext == str(value))

        return statement

    def get(self, session: Session, *, id: Any) -> ModelType | None:
        """Return a single record by primary key, or ``None``."""
        return session.get(self.model, id)

    def get_multi(
        self, session: Session, *, skip: int = 0, limit: int = 100
    ) -> list[ModelType]:
        """Return a paginated list of records."""
        statement = select(self.model).offset(skip).limit(limit)
        return list(session.exec(statement).all())

    def get_filtered(
        self,
        session: Session,
        *,
        filters: dict[str, Any],
        skip: int = 0,
        limit: int = 100,
        order_by: str | None = None,
        order_desc: bool = False,
    ) -> list[ModelType]:
        """
        Return a paginated list of records matching **all** provided filters.

        How each filter key is resolved (fully dynamic):

        1. **Top-level column** -- if the key matches a column on the model,
           a standard ``WHERE column = value`` clause is emitted.
        2. **JSONB fallback** -- if the key is *not* a column but the model
           has a JSONB column (e.g. ``extra_fields``), a
           ``WHERE jsonb_col->>key = value`` clause is emitted.
        3. **None values** are silently skipped.

        Ordering is applied via ``order_by`` (column name) and ``order_desc``.
        Pagination (``skip`` / ``limit``) is applied **after** filtering and
        ordering.

        This design means adding a new filter requires **zero** changes in
        the service layer -- just declare the new ``Query`` parameter in the
        corresponding ``FilterParams`` dependency class.
        """
        statement = self._apply_filters(select(self.model), filters)

        if order_by and order_by in self._column_names:
            col = getattr(self.model, order_by)
            statement = statement.order_by(col.desc() if order_desc else col.asc())

        statement = statement.offset(skip).limit(limit)
        return list(session.exec(statement).all())

    # ── Create / Update / Delete ──────────────────────────────────

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
