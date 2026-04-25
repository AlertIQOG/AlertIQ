"""Database engine & session dependency."""

from collections.abc import Generator

from sqlmodel import Session, create_engine

from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
)


def get_session() -> Generator[Session, None, None]:
    """
    FastAPI dependency — yields a per-request DB session.

    The session is automatically closed when the request finishes.
    """
    with Session(engine) as session:
        yield session
