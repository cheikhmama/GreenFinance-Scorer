"""Fixtures partagées pour les tests d'intégration adossés à une base réelle.

_apply_migrations applique `alembic upgrade head` sur la base cible : depuis
le Prompt 3.9, la migration Alembic consolidée (b5f953dddf56) est la seule
source de vérité du schéma — plus de `create_all` de secours. Idempotent
(alembic ne rejoue pas une révision déjà appliquée), donc sûr à exécuter à
chaque session de tests même sur une base qui a déjà le schéma à jour.
"""

from pathlib import Path

import pytest
from alembic.config import Config
from sqlmodel import Session

from alembic import command
from app.core.database import engine

_REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session", autouse=True)
def _apply_migrations() -> None:
    command.upgrade(Config(str(_REPO_ROOT / "alembic.ini")), "head")


@pytest.fixture()
def session():
    with Session(engine) as session:
        yield session
        session.rollback()
