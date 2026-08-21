from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()


def _connect_args() -> dict[str, int]:
    if settings.database_url.startswith("postgresql"):
        return {"connect_timeout": settings.database_connect_timeout_seconds}
    return {}


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args=_connect_args(),
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Provide a database session and always close it after use."""
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_database() -> None:
    """Execute a minimal database readiness query."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
