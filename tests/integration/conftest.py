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
from app.auth.rate_limit import _key_ip
from app.core.database import engine
from app.core.redis import get_redis_client

_REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session", autouse=True)
def _apply_migrations() -> None:
    command.upgrade(Config(str(_REPO_ROOT / "alembic.ini")), "head")


@pytest.fixture()
def session():
    with Session(engine) as session:
        yield session
        session.rollback()


@pytest.fixture(autouse=True)
def _reinitialiser_limite_connexion_par_ip() -> None:
    """Toutes les requêtes TestClient viennent de la même adresse ("testclient") et la suite
    partage le Redis de développement : sans cette remise à zéro, les échecs de connexion de
    TOUTE la suite (et des exécutions précédentes dans la fenêtre) s'additionneraient sur le
    compteur par IP (app/auth/rate_limit.py::MAX_ATTEMPTS_PAR_IP) et finiraient par bloquer des
    tests sans rapport."""
    get_redis_client().delete(_key_ip("testclient"))
