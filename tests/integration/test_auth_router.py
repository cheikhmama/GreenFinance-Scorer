import uuid

import redis
from fastapi.testclient import TestClient
from sqlmodel import select

from app.auth.hashing import hash_password
from app.auth.models import Utilisateur
from app.auth.rate_limit import MAX_ATTEMPTS, clear_login_attempts
from app.auth.tokens import COOKIE_NAME, CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.core.enums import Role
from app.core.models import JournalAudit
from app.main import app

client = TestClient(app, base_url="https://testserver")


def _create_utilisateur(session, *, password: str, role: Role = Role.INVESTISSEUR, actif: bool = True) -> Utilisateur:
    user = Utilisateur(
        email=f"{role.value.lower()}-{uuid.uuid4()}@example.com",
        mot_de_passe_hache=hash_password(password),
        role=role,
        actif=actif,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_login_with_correct_credentials_sets_the_cookie_and_returns_the_user(session) -> None:
    user = _create_utilisateur(session, password="s3cret-pass")

    response = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "s3cret-pass"}
    )

    assert response.status_code == 200
    assert response.json()["email"] == user.email
    assert response.json()["role"] == user.role.value
    assert response.json()["doit_changer_mot_de_passe"] is False
    assert "mot_de_passe_hache" not in response.json()
    assert COOKIE_NAME in response.cookies
    assert CSRF_COOKIE_NAME in response.cookies


def test_login_with_wrong_password_is_rejected(session) -> None:
    user = _create_utilisateur(session, password="s3cret-pass")

    response = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "wrong-password"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"
    assert COOKIE_NAME not in response.cookies


def test_login_with_unknown_email_is_rejected() -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": f"inconnu-{uuid.uuid4()}@example.com", "password": "whatever"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_login_for_a_deactivated_account_is_rejected(session) -> None:
    user = _create_utilisateur(session, password="s3cret-pass", actif=False)

    response = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "s3cret-pass"}
    )

    assert response.status_code == 401


def test_me_without_a_session_cookie_is_rejected() -> None:
    anonymous_client = TestClient(app, base_url="https://testserver")

    response = anonymous_client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_login_then_me_returns_the_same_user(session) -> None:
    user = _create_utilisateur(session, password="s3cret-pass", role=Role.AUDITEUR)
    authed_client = TestClient(app, base_url="https://testserver")

    login_response = authed_client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "s3cret-pass"}
    )
    assert login_response.status_code == 200

    me_response = authed_client.get("/api/v1/auth/me")

    assert me_response.status_code == 200
    assert me_response.json()["id"] == str(user.id)
    assert me_response.json()["role"] == Role.AUDITEUR.value


def test_login_is_rate_limited_after_repeated_failures_then_recovers_on_success(session) -> None:
    user = _create_utilisateur(session, password="s3cret-pass")
    clear_login_attempts(user.email)  # isole ce test d'un éventuel état laissé par un run précédent

    for _ in range(MAX_ATTEMPTS):
        response = client.post(
            "/api/v1/auth/login", json={"email": user.email, "password": "wrong-password"}
        )
        assert response.status_code == 401

    blocked_response = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "s3cret-pass"}
    )
    assert blocked_response.status_code == 429
    assert blocked_response.json()["error"]["code"] == "too_many_requests"

    clear_login_attempts(user.email)
    recovered_response = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "s3cret-pass"}
    )
    assert recovered_response.status_code == 200


def test_login_returns_503_when_redis_is_unavailable(session, monkeypatch) -> None:
    """Échec fermé explicite : sans Redis, le login ne doit ni réussir sans
    protection anti-bruteforce, ni renvoyer une 500 générique qui masquerait
    la vraie cause."""
    user = _create_utilisateur(session, password="s3cret-pass")
    unreachable_client = redis.Redis(host="127.0.0.1", port=1, socket_connect_timeout=1)
    monkeypatch.setattr("app.auth.rate_limit.get_redis_client", lambda: unreachable_client)

    response = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "s3cret-pass"}
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"
    assert COOKIE_NAME not in response.cookies


def test_logout_clears_the_cookie_and_me_is_rejected_afterwards(session) -> None:
    user = _create_utilisateur(session, password="s3cret-pass")
    authed_client = TestClient(app, base_url="https://testserver")
    authed_client.post("/api/v1/auth/login", json={"email": user.email, "password": "s3cret-pass"})
    authed_client.headers.update({CSRF_HEADER_NAME: authed_client.cookies[CSRF_COOKIE_NAME]})

    logout_response = authed_client.post("/api/v1/auth/logout")
    me_response = authed_client.get("/api/v1/auth/me")

    assert logout_response.status_code == 204
    assert me_response.status_code == 401


def test_login_success_failure_and_logout_are_all_journalised(session) -> None:
    """Phase 3 §3.5 — le journal d'audit (app/core/audit.py) trace ces trois événements, jamais
    de mot de passe ni de jeton (voir app/core/audit.py::auditer)."""
    user = _create_utilisateur(session, password="s3cret-pass")

    wrong_password_response = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "mauvais-mot-de-passe"}
    )
    assert wrong_password_response.status_code == 401

    authed_client = TestClient(app, base_url="https://testserver")
    authed_client.post("/api/v1/auth/login", json={"email": user.email, "password": "s3cret-pass"})
    authed_client.headers.update({CSRF_HEADER_NAME: authed_client.cookies[CSRF_COOKIE_NAME]})
    authed_client.post("/api/v1/auth/logout")

    entrees = session.exec(
        select(JournalAudit)
        .where(JournalAudit.acteur_id == user.id)
        .order_by(JournalAudit.date)
    ).all()
    actions_et_resultats = [(e.action, e.resultat) for e in entrees]
    assert ("connexion", "echec") in actions_et_resultats
    assert ("connexion", "succes") in actions_et_resultats
    assert ("deconnexion", "succes") in actions_et_resultats
    for entree in entrees:
        assert "s3cret-pass" not in (entree.ancienne_valeur or "")
        assert "s3cret-pass" not in (entree.nouvelle_valeur or "")


def test_logout_revokes_a_stolen_copy_of_the_cookie(session) -> None:
    """La révocation (app/auth/revocation.py) invalide *toute* session, pas seulement celle qui
    s'est déconnectée — c'est exactement le trou signalé par la Phase 3 : un JWT volé avant sa
    déconnexion doit cesser de fonctionner, pas seulement le cookie de l'appareil légitime."""
    user = _create_utilisateur(session, password="s3cret-pass")
    legitimate_client = TestClient(app, base_url="https://testserver")
    legitimate_client.post("/api/v1/auth/login", json={"email": user.email, "password": "s3cret-pass"})
    legitimate_client.headers.update(
        {CSRF_HEADER_NAME: legitimate_client.cookies[CSRF_COOKIE_NAME]}
    )

    stolen_client = TestClient(app, base_url="https://testserver")
    stolen_client.cookies.set(COOKIE_NAME, legitimate_client.cookies[COOKIE_NAME])
    assert stolen_client.get("/api/v1/auth/me").status_code == 200  # le vol fonctionnait avant

    legitimate_client.post("/api/v1/auth/logout")

    assert stolen_client.get("/api/v1/auth/me").status_code == 401


def test_change_password_then_old_cookie_is_rejected_but_new_session_works(session) -> None:
    user = _create_utilisateur(session, password="s3cret-pass")
    authed_client = TestClient(app, base_url="https://testserver")
    authed_client.post("/api/v1/auth/login", json={"email": user.email, "password": "s3cret-pass"})
    old_access_cookie = authed_client.cookies[COOKIE_NAME]
    authed_client.headers.update({CSRF_HEADER_NAME: authed_client.cookies[CSRF_COOKIE_NAME]})

    change_response = authed_client.post(
        "/api/v1/auth/changer-mot-de-passe",
        json={"mot_de_passe_actuel": "s3cret-pass", "nouveau_mot_de_passe": "nouveau-secret-2"},
    )
    assert change_response.status_code == 200

    # Le client qui a fait la demande reste connecté (nouvelle session posée par la réponse).
    assert authed_client.get("/api/v1/auth/me").status_code == 200

    # Mais l'ancien jeton, lui, est désormais révoqué.
    stale_client = TestClient(app, base_url="https://testserver")
    stale_client.cookies.set(COOKIE_NAME, old_access_cookie)
    assert stale_client.get("/api/v1/auth/me").status_code == 401

    # Le nouveau mot de passe fonctionne pour une connexion ultérieure, l'ancien plus.
    relog_ancien = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "s3cret-pass"}
    )
    assert relog_ancien.status_code == 401
    relog_nouveau = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "nouveau-secret-2"}
    )
    assert relog_nouveau.status_code == 200


def test_change_password_with_wrong_current_password_is_rejected(session) -> None:
    user = _create_utilisateur(session, password="s3cret-pass")
    authed_client = TestClient(app, base_url="https://testserver")
    authed_client.post("/api/v1/auth/login", json={"email": user.email, "password": "s3cret-pass"})
    authed_client.headers.update({CSRF_HEADER_NAME: authed_client.cookies[CSRF_COOKIE_NAME]})

    response = authed_client.post(
        "/api/v1/auth/changer-mot-de-passe",
        json={"mot_de_passe_actuel": "mauvais-mot-de-passe", "nouveau_mot_de_passe": "peu-importe-2"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_mutating_request_without_csrf_header_is_rejected(session) -> None:
    user = _create_utilisateur(session, password="s3cret-pass")
    authed_client = TestClient(app, base_url="https://testserver")
    authed_client.post("/api/v1/auth/login", json={"email": user.email, "password": "s3cret-pass"})
    # Volontairement pas d'en-tête X-CSRF-Token ici, contrairement à _login() dans les autres
    # suites — c'est exactement ce que cette route mutante doit refuser.

    response = authed_client.post("/api/v1/auth/logout")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"


def test_mutating_request_with_wrong_csrf_token_is_rejected(session) -> None:
    user = _create_utilisateur(session, password="s3cret-pass")
    authed_client = TestClient(app, base_url="https://testserver")
    authed_client.post("/api/v1/auth/login", json={"email": user.email, "password": "s3cret-pass"})
    authed_client.headers.update({CSRF_HEADER_NAME: "un-jeton-invente"})

    response = authed_client.post("/api/v1/auth/logout")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"
