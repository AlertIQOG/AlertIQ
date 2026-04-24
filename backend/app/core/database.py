from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

# Setup the database engine using the connection string from settings
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,  # Log SQL queries when in debug mode
)





def get_session() -> Generator[Session, None, None]:
    """
    FastAPI dependency for database sessions.
    Offers a per-request session that gets closed properly.
    """
    with Session(engine) as session:
        yield session
