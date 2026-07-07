"""Database engine & session dependency."""

from collections.abc import Generator

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
)

# pgvector is required by the Resolution Copilot chunk store. Create the extension
# before create_all so vector columns can be defined. Idempotent and safe to re-run.
with engine.begin() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

import app.models  # noqa: F401, E402 — ensures all models are registered before create_all
SQLModel.metadata.create_all(engine)

# create_all only creates missing tables; it never ALTERs an existing one. Add
# columns introduced after a table first shipped here, idempotently, so an
# already-provisioned database picks them up on the next boot.
with engine.begin() as conn:
    conn.execute(
        text(
            "ALTER TABLE correlation_rules "
            "ADD COLUMN IF NOT EXISTS actions jsonb NOT NULL DEFAULT '[\"aggregate\"]'::jsonb"
        )
    )


def get_session() -> Generator[Session, None, None]:
    """Yield a database session."""
    with Session(engine) as session:
        yield session
