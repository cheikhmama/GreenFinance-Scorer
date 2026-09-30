"""CSRFMiddleware isolé (tâche 4.5) : une application minimale, une route par méthode, aucun
router métier — seule la porte CSRF est éprouvée, cas par cas."""

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.csrf import CSRFMiddleware, generate_csrf_token
from app.auth.tokens import (
    API_V1_PREFIX,
    COOKIE_NAME,
    CSRF_HEADER_NAME,
    create_access_token,
)
from app.core.config import get_settings
from app.core.enums import Role

UTILISATEUR = uuid.uuid4()
ORIGINE_AUTORISEE = get_settings().cors_allowed_origins_list[0]


@pytest.fixture()
def client() -> TestClient:
    application = FastAPI()
    application.add_middleware(CSRFMiddleware)

    @application.get("/api/v1/ressource")
    def lire() -> dict[str, str]:
        return {"ok": "lecture"}

    @application.post("/api/v1/ressource")
    def ecrire() -> dict[str, str]:
        return {"ok": "ecriture"}

    @application.post(f"{API_V1_PREFIX}/auth/login")
    def connexion() -> dict[str, str]:
        return {"ok": "connexion"}

    return TestClient(application, base_url="https://testserver")


def _session(client: TestClient, generation: int = 0) -> str:
    client.cookies.set(COOKIE_NAME, create_access_token(UTILISATEUR, Role.INVESTOR, generation))
    return generate_csrf_token(UTILISATEUR, generation)


def test_lecture_jamais_soumise_au_jeton(client) -> None:
    _session(client)

    assert client.get("/api/v1/ressource").status_code == 200


def test_ecriture_sans_session_laissee_a_l_authentification(client) -> None:
    """Sans cookie de session, rien à protéger ici : le 401 viendra de get_current_user."""
    assert client.post("/api/v1/ressource").status_code == 200


def test_ecriture_avec_session_exige_le_bon_jeton(client) -> None:
    jeton = _session(client)

    sans = client.post("/api/v1/ressource")
    faux = client.post("/api/v1/ressource", headers={CSRF_HEADER_NAME: "0" * 64})
    bon = client.post("/api/v1/ressource", headers={CSRF_HEADER_NAME: jeton})

    assert (sans.status_code, faux.status_code, bon.status_code) == (403, 403, 200)
    assert sans.json()["error"]["code"] == "csrf_failed"


def test_jeton_d_une_generation_revoquee_refuse(client) -> None:
    """Après révocation (changement de mot de passe, déconnexion), l'ancien jeton CSRF ne vaut
    plus pour la nouvelle session : il est lié à la génération du JWT."""
    ancien = generate_csrf_token(UTILISATEUR, 0)
    _session(client, generation=1)

    assert client.post("/api/v1/ressource", headers={CSRF_HEADER_NAME: ancien}).status_code == 403


@pytest.mark.parametrize("en_tete", ["origin", "referer"])
def test_origine_etrangere_refusee_meme_avec_le_bon_jeton(client, en_tete: str) -> None:
    jeton = _session(client)

    etrangere = client.post(
        "/api/v1/ressource",
        headers={CSRF_HEADER_NAME: jeton, en_tete: "https://attaquant.example/page"},
    )
    autorisee = client.post(
        "/api/v1/ressource", headers={CSRF_HEADER_NAME: jeton, en_tete: f"{ORIGINE_AUTORISEE}/x"}
    )

    assert etrangere.status_code == 403
    assert etrangere.json()["error"]["message"] == "Origine non autorisée."
    assert autorisee.status_code == 200


def test_connexion_exemptee(client) -> None:
    """Aucun jeton CSRF ne peut exister avant la première connexion."""
    _session(client)

    assert client.post(f"{API_V1_PREFIX}/auth/login").status_code == 200


def test_session_invalide_laissee_a_l_authentification(client) -> None:
    client.cookies.set(COOKIE_NAME, "pas-un-jwt")

    assert client.post("/api/v1/ressource").status_code == 200
