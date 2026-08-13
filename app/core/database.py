from collections.abc import Generator
from datetime import UTC, datetime

from sqlalchemy import Engine, text
from sqlmodel import Session, create_engine

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url)


def utcnow() -> datetime:
    """Horodatage UTC courant, à utiliser comme default_factory des champs
    date_* des modèles — évite datetime.utcnow() (déprécié depuis Python
    3.12) tout en restant un datetime naïf, cohérent avec les colonnes
    TIMESTAMP WITHOUT TIME ZONE utilisées par le schéma."""
    return datetime.now(UTC).replace(tzinfo=None)


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
