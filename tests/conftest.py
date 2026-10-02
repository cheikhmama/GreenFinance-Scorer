"""Isole la base et le stockage fichiers utilisés par les tests de ceux du développement.

Sans l'isolation base, tous les tests d'intégration tapent directement sur
`app.core.database.engine`, donc sur la MÊME base Postgres que le développement/la vérification
manuelle — chaque run pytest y laisse des centaines de comptes/entreprises de test (aucune
isolation transactionnelle par test, voir tests/integration/conftest.py::session : le rollback
n'annule que ce qui n'a pas été commit, et les handlers de route commitent toujours par
conception). Sans l'isolation stockage, les PDF envoyés via POST /company/rapports pendant les
tests s'écrivent sous le vrai STORAGE_PATH (./storage) — même défaut, mêmes conséquences : ça a
rempli storage/rapports/test/ et laissé 230+ dossiers UUID orphelins (jamais nettoyés par un
DELETE puisque les lignes ESGReport correspondantes vivent dans la base de test, droppée à part).

Ce module doit s'exécuter avant TOUT import de app.* dans la session pytest — d'où sa position à
la racine de tests/, chargée avant tests/integration/conftest.py (qui importe déjà
app.core.database au niveau module). DATABASE_URL et STORAGE_PATH sont réécrits en variables
d'environnement avant que app.core.config ne construise Settings (get_settings, @lru_cache) au
premier appel — pydantic-settings donne priorité à une variable d'environnement réelle sur la
valeur lue dans .env.
"""

import atexit
import os
import shutil
import tempfile
from urllib.parse import urlsplit, urlunsplit

import psycopg
from dotenv import dotenv_values
from psycopg import sql

_REPO_ROOT_ENV = os.path.join(os.path.dirname(__file__), "..", ".env")


def _base_database_url() -> str:
    # Une vraie variable d'environnement (ex. posée par CI) prime toujours sur .env, comme le
    # ferait pydantic-settings lui-même.
    depuis_environnement = os.environ.get("DATABASE_URL")
    if depuis_environnement:
        return depuis_environnement
    return dotenv_values(_REPO_ROOT_ENV).get("DATABASE_URL") or ""


def _derive_test_url(base_url: str) -> str:
    scheme, netloc, path, query, fragment = urlsplit(base_url)
    return urlunsplit((scheme, netloc, f"{path}_test", query, fragment))


def _psycopg_dsn(sqlalchemy_url: str) -> str:
    # SQLAlchemy accepte "postgresql+psycopg://...", psycopg attend "postgresql://...".
    return sqlalchemy_url.replace("postgresql+psycopg://", "postgresql://", 1)


def _ensure_database_exists(base_url: str, target_url: str) -> None:
    base_db_name = urlsplit(base_url).path.lstrip("/")
    target_db_name = urlsplit(target_url).path.lstrip("/")
    if base_db_name == target_db_name:
        return  # TEST_DATABASE_URL pointe explicitement sur la même base -- rien à créer.

    # CREATE DATABASE ne peut pas s'exécuter dans une transaction -- connexion dédiée, autocommit,
    # à la base de base (garantie d'exister, cf. docker-compose.yml/Postgres natif local).
    with psycopg.connect(_psycopg_dsn(base_url), autocommit=True) as conn:
        deja_presente = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (target_db_name,)
        ).fetchone()
        if deja_presente is None:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target_db_name)))


_base_url = _base_database_url()
if not _base_url:
    raise RuntimeError(
        "DATABASE_URL introuvable (ni variable d'environnement, ni .env) -- "
        "impossible d'isoler la base de test."
    )

_test_url = os.environ.get("TEST_DATABASE_URL") or _derive_test_url(_base_url)
_ensure_database_exists(_base_url, _test_url)
os.environ["DATABASE_URL"] = _test_url

# Dossier jetable pour STORAGE_PATH, supprimé à la fin du run pytest -- symétrique de
# l'isolation DATABASE_URL ci-dessus.
_test_storage_dir = tempfile.mkdtemp(prefix="greenfinance_test_storage_")
atexit.register(shutil.rmtree, _test_storage_dir, ignore_errors=True)
os.environ["STORAGE_PATH"] = _test_storage_dir


# --- File de travaux (tâche 4.1) -------------------------------------------------------------
# Aucun test ne dépose de vrai job dans Redis : sans worker pour les consommer, ils s'y
# accumuleraient d'un run à l'autre (et un job d'extraction `extract:{id}` déjà présent
# bloquerait le suivant). Chaque dépôt est enregistré dans `jobs_enfiles`, que les tests
# consultent pour vérifier CE qui a été programmé.

import pytest


@pytest.fixture(autouse=True)
def jobs_enfiles(monkeypatch) -> list[tuple[str, tuple, str | None, str]]:
    depots: list[tuple[str, tuple, str | None, str]] = []

    async def _enregistrer(fonction: str, args: tuple, job_id: str | None, file: str) -> bool:
        if job_id is not None and any(depot[2] == job_id for depot in depots):
            return False  # même règle qu'ARQ : un identifiant déjà en file n'est pas redéposé
        depots.append((fonction, args, job_id, file))
        return True

    monkeypatch.setattr("app.worker.queue._envoyer_a_redis", _enregistrer)
    return depots


@pytest.fixture(autouse=True)
def gleif_hors_ligne(monkeypatch) -> None:
    """Aucun test n'appelle la vraie GLEIF (tâche 5.3) : par défaut, l'appel échoue comme un réseau
    coupé — le contrôle KYC répond alors « non vérifiable ». Un test qui veut une fiche GLEIF
    remplace app.admin.kyc.recuperer_fiche_gleif (ou httpx.get, pour tester le client lui-même)."""
    import httpx

    def _reseau_interdit(*_args, **_kwargs):
        raise httpx.ConnectError("réseau interdit pendant les tests")

    monkeypatch.setattr("app.admin.kyc.httpx.get", _reseau_interdit)


CODE_DE_VERIFICATION = "123456"


@pytest.fixture(autouse=True)
def envoi_code_verification(monkeypatch):
    """Vérification de l'adresse à l'inscription (tâche 5.11) : code fixe, e-mail du code capté
    (jamais déposé dans la file réelle), limites par IP remises à zéro à chaque test."""
    from unittest.mock import Mock

    from app.core.redis import get_redis_client

    monkeypatch.setattr(
        "app.company.verification_email.secrets.randbelow", lambda _n: int(CODE_DE_VERIFICATION)
    )
    envoi = Mock()
    monkeypatch.setattr("app.company.verification_email.envoyer_email_differe", envoi)
    client = get_redis_client()
    for cle in client.scan_iter("registration_email_*"):
        client.delete(cle)
    return envoi
