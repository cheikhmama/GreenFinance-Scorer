from collections.abc import Generator

from sqlalchemy import Engine, text
from sqlmodel import Session, create_engine

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


class DatabaseConnectionError(RuntimeError):
    pass


def check_database_connection(engine_: Engine | None = None) -> None:
    target = engine_ if engine_ is not None else engine
    try:
        with Session(target) as session:
            session.execute(text("SELECT 1"))
    except Exception as exc:
        raise DatabaseConnectionError(
            f"Impossible de se connecter à la base de données: {exc}"
        ) from exc
