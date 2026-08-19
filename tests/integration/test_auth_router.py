import uuid

import redis
from fastapi.testclient import TestClient

from app.auth.hashing import hash_password
from app.auth.models import Utilisateur
from app.auth.rate_limit import MAX_ATTEMPTS, clear_login_attempts
from app.core.enums import Role
from app.main import app

client = TestClient(app)


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
    assert "mot_de_passe_hache" not in response.json()
    assert "access_token" in response.cookies


def test_login_with_wrong_password_is_rejected(session) -> None:
    user = _create_utilisateur(session, password="s3cret-pass")

    response = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "wrong-password"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"
    assert "access_token" not in response.cookies


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
    anonymous_client = TestClient(app)

    response = anonymous_client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_login_then_me_returns_the_same_user(session) -> None:
    user = _create_utilisateur(session, password="s3cret-pass", role=Role.AUDITEUR)
    authed_client = TestClient(app)

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
    assert "access_token" not in response.cookies


def test_logout_clears_the_cookie_and_me_is_rejected_afterwards(session) -> None:
    user = _create_utilisateur(session, password="s3cret-pass")
    authed_client = TestClient(app)
    authed_client.post("/api/v1/auth/login", json={"email": user.email, "password": "s3cret-pass"})

    logout_response = authed_client.post("/api/v1/auth/logout")
    me_response = authed_client.get("/api/v1/auth/me")

    assert logout_response.status_code == 204
    assert me_response.status_code == 401
