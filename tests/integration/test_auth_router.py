import base64
import uuid
from datetime import timedelta
from unittest.mock import Mock

import pytest
import redis
import structlog
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select

from app.auth.email_change import _hash_token as _hash_jeton_email
from app.auth.hashing import hash_password, verify_password
from app.auth.models import EmailChangeRequest, PasswordResetToken, User
from app.auth.password_reset import _hash_token
from app.auth.rate_limit import MAX_ATTEMPTS, MAX_ATTEMPTS_PAR_IP, clear_login_attempts
from app.auth.tokens import COOKIE_NAME, CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.core import storage
from app.core.database import utcnow
from app.core.email import EmailDeliveryError
from app.core.enums import Role
from app.core.models import AuditLogEntry
from app.main import app

client = TestClient(app, base_url="https://testserver")


@pytest.fixture(autouse=True)
def _mock_password_reset_delivery(monkeypatch):
    """Aucune suite de test ne doit contacter un vrai relais SMTP."""
    monkeypatch.setattr("app.auth.password_reset.ensure_email_configured", lambda: None)
    delivery = Mock()
    monkeypatch.setattr("app.auth.password_reset.envoyer_email_differe", delivery)
    monkeypatch.setattr("app.auth.email_change.ensure_email_configured", lambda: None)
    monkeypatch.setattr("app.auth.email_change.envoyer_email_differe", delivery)
    return delivery


def _create_utilisateur(session, *, password: str, role: Role = Role.INVESTOR, actif: bool = True) -> User:
    user = User(
        email=f"{role.value.lower()}-{uuid.uuid4()}@example.com",
        password_hash=hash_password(password),
        role=role,
        active=actif,
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
    user = _create_utilisateur(session, password="s3cret-pass", role=Role.AUDITOR)
    authed_client = TestClient(app, base_url="https://testserver")

    login_response = authed_client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "s3cret-pass"}
    )
    assert login_response.status_code == 200

    me_response = authed_client.get("/api/v1/auth/me")

    assert me_response.status_code == 200
    assert me_response.json()["id"] == str(user.id)
    assert me_response.json()["role"] == Role.AUDITOR.value


def _client_connecte(user: User, password: str) -> TestClient:
    authed_client = TestClient(app, base_url="https://testserver")
    authed_client.post("/api/v1/auth/login", json={"email": user.email, "password": password})
    authed_client.headers.update({CSRF_HEADER_NAME: authed_client.cookies[CSRF_COOKIE_NAME]})
    return authed_client


def _fixer_le_prochain_jeton_email(monkeypatch) -> str:
    jeton = f"jeton-email-{uuid.uuid4()}"
    monkeypatch.setattr("app.auth.email_change.secrets.token_urlsafe", lambda _n: jeton)
    return jeton


def test_modifier_mon_profil_change_le_nom_immediatement_jamais_le_role(session) -> None:
    user = _create_utilisateur(session, password="s3cret-pass", role=Role.RESEARCHER)
    authed_client = _client_connecte(user, "s3cret-pass")

    response = authed_client.patch(
        "/api/v1/auth/me",
        json={"name": "Nouveau Nom", "email": user.email, "role": Role.ADMIN.value},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Nouveau Nom"
    assert body["email"] == user.email
    assert body["pending_email"] is None
    assert body["role"] == Role.RESEARCHER.value


def test_changer_email_exige_le_mot_de_passe_actuel(session) -> None:
    user = _create_utilisateur(session, password="s3cret-pass")
    authed_client = _client_connecte(user, "s3cret-pass")
    nouvel_email = f"nouveau-{uuid.uuid4()}@example.com"

    sans = authed_client.patch("/api/v1/auth/me", json={"name": "N", "email": nouvel_email})
    faux = authed_client.patch(
        "/api/v1/auth/me",
        json={"name": "N", "email": nouvel_email, "current_password": "mauvais-pass"},
    )

    assert sans.status_code == 422
    assert sans.json()["error"]["code"] == "mot_de_passe_requis"
    assert faux.status_code == 401
    clear_login_attempts(user.email)
    session.refresh(user)
    assert user.email != nouvel_email


def test_changer_email_nest_applique_quapres_confirmation_par_la_nouvelle_adresse(
    session, monkeypatch, _mock_password_reset_delivery
) -> None:
    user = _create_utilisateur(session, password="s3cret-pass")
    ancien_email = user.email
    authed_client = _client_connecte(user, "s3cret-pass")
    jeton = _fixer_le_prochain_jeton_email(monkeypatch)
    nouvel_email = f"Nouveau-{uuid.uuid4()}@Example.COM"

    demande = authed_client.patch(
        "/api/v1/auth/me",
        json={"name": "N", "email": nouvel_email, "current_password": "s3cret-pass"},
    )

    # Demande seulement : l'identifiant de connexion ne change pas encore.
    assert demande.status_code == 200
    assert demande.json()["email"] == ancien_email
    assert demande.json()["pending_email"] == nouvel_email.lower()
    destinataires = [appel.kwargs["recipient"] for appel in _mock_password_reset_delivery.call_args_list]
    assert destinataires == [nouvel_email.lower(), ancien_email]
    entree = session.exec(
        select(EmailChangeRequest).where(EmailChangeRequest.user_id == user.id)
    ).one()
    assert entree.token_hash == _hash_jeton_email(jeton)

    confirmation = _client_public().post(
        "/api/v1/auth/confirmer-changement-email", json={"token": jeton}
    )
    rejeu = _client_public().post("/api/v1/auth/confirmer-changement-email", json={"token": jeton})

    assert confirmation.status_code == 200
    assert confirmation.json()["email"] == nouvel_email.lower()
    assert rejeu.status_code == 422
    assert rejeu.json()["error"]["code"] == "jeton_invalide"
    journal = session.exec(
        select(AuditLogEntry).where(
            AuditLogEntry.action == "email_changed", AuditLogEntry.resource_id == user.id
        )
    ).one()
    assert journal.old_value == ancien_email
    assert journal.new_value == nouvel_email.lower()


def test_modifier_mon_profil_avec_un_email_deja_utilise_est_refuse(session) -> None:
    autre = _create_utilisateur(session, password="autre-pass")
    user = _create_utilisateur(session, password="s3cret-pass")
    authed_client = _client_connecte(user, "s3cret-pass")

    response = authed_client.patch(
        "/api/v1/auth/me",
        json={"name": "Un Nom", "email": autre.email.upper(), "current_password": "s3cret-pass"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "email_deja_utilise"


def test_modifier_mon_profil_avec_un_email_invalide_est_refuse(session) -> None:
    user = _create_utilisateur(session, password="s3cret-pass")
    authed_client = TestClient(app, base_url="https://testserver")
    authed_client.post("/api/v1/auth/login", json={"email": user.email, "password": "s3cret-pass"})
    authed_client.headers.update({CSRF_HEADER_NAME: authed_client.cookies[CSRF_COOKIE_NAME]})

    response = authed_client.patch(
        "/api/v1/auth/me", json={"name": "Un Nom", "email": "pas-un-email"}
    )

    assert response.status_code == 422


_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def test_televerser_puis_supprimer_mon_avatar(session) -> None:
    user = _create_utilisateur(session, password="s3cret-pass")
    authed_client = TestClient(app, base_url="https://testserver")
    authed_client.post("/api/v1/auth/login", json={"email": user.email, "password": "s3cret-pass"})
    authed_client.headers.update({CSRF_HEADER_NAME: authed_client.cookies[CSRF_COOKIE_NAME]})

    upload = authed_client.post(
        "/api/v1/auth/me/avatar", files={"fichier": ("avatar.png", _PNG_1X1, "image/png")}
    )
    assert upload.status_code == 200
    # Tâche 4.3 : une URL vers le fichier, plus un data URI stocké dans la ligne utilisateur.
    url = upload.json()["avatar"]
    assert url.startswith(f"/api/v1/auth/avatars/{user.id}/") and url.endswith(".png")
    image = authed_client.get(url)
    assert image.status_code == 200
    assert image.content == _PNG_1X1
    assert image.headers["content-type"] == "image/png"
    assert "immutable" in image.headers["cache-control"]
    fichier = storage.resolve_path(f"avatars/{user.id}/{url.rsplit('/', 1)[1]}")
    assert fichier.is_file()

    # Un nouvel envoi change l'URL ; l'ancienne ne sert plus rien et son fichier disparaît.
    remplacement = authed_client.post(
        "/api/v1/auth/me/avatar", files={"fichier": ("avatar.png", _PNG_1X1, "image/png")}
    )
    assert remplacement.json()["avatar"] != url
    assert authed_client.get(url).status_code == 404
    assert not fichier.exists()
    # Jamais un fichier arbitraire : seul le nom enregistré sur la ligne est servi.
    assert authed_client.get(f"/api/v1/auth/avatars/{user.id}/..%2F..%2F.env").status_code == 404
    assert TestClient(app, base_url="https://testserver").get(
        remplacement.json()["avatar"]
    ).status_code == 401

    delete = authed_client.delete("/api/v1/auth/me/avatar")
    assert delete.status_code == 200
    assert delete.json()["avatar"] is None
    assert authed_client.get(remplacement.json()["avatar"]).status_code == 404


def test_televerser_avatar_non_image_est_refuse_proprement(session) -> None:
    user = _create_utilisateur(session, password="s3cret-pass")
    authed_client = TestClient(app, base_url="https://testserver")
    authed_client.post("/api/v1/auth/login", json={"email": user.email, "password": "s3cret-pass"})
    authed_client.headers.update({CSRF_HEADER_NAME: authed_client.cookies[CSRF_COOKIE_NAME]})

    response = authed_client.post(
        "/api/v1/auth/me/avatar",
        files={"fichier": ("pas-une-image.txt", b"contenu texte quelconque", "image/png")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "signature_invalide"


def test_verifier_mon_mot_de_passe_valide_ou_invalide(session) -> None:
    user = _create_utilisateur(session, password="s3cret-pass")
    clear_login_attempts(user.email)
    authed_client = TestClient(app, base_url="https://testserver")
    authed_client.post("/api/v1/auth/login", json={"email": user.email, "password": "s3cret-pass"})
    authed_client.headers.update({CSRF_HEADER_NAME: authed_client.cookies[CSRF_COOKIE_NAME]})

    invalide = authed_client.post(
        "/api/v1/auth/verifier-mot-de-passe", json={"password": "mauvais-mot-de-passe"}
    )
    assert invalide.status_code == 401
    assert invalide.json()["error"]["code"] == "invalid_credentials"

    valide = authed_client.post(
        "/api/v1/auth/verifier-mot-de-passe", json={"password": "s3cret-pass"}
    )
    assert valide.status_code == 204


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
        select(AuditLogEntry)
        .where(AuditLogEntry.actor_id == user.id)
        .order_by(col(AuditLogEntry.occurred_at))
    ).all()
    actions_et_resultats = [(e.action, e.result) for e in entrees]
    assert ("login", "failure") in actions_et_resultats
    assert ("login", "success") in actions_et_resultats
    assert ("logout", "success") in actions_et_resultats
    for entree in entrees:
        assert "s3cret-pass" not in (entree.old_value or "")
        assert "s3cret-pass" not in (entree.new_value or "")


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
        json={"current_password": "s3cret-pass", "new_password": "nouveau-secret-2"},
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
        json={"current_password": "mauvais-mot-de-passe", "new_password": "peu-importe-2"},
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


# ============================================================================
# Mot de passe oublié (app/auth/password_reset.py) — l'envoi SMTP est simulé : le jeton en
# clair n'apparaît jamais dans une réponse HTTP, on le fixe donc via monkeypatch pour pouvoir le
# manipuler dans ces tests. Chaque test utilise un TestClient fraîchement instancié plutôt que le `client`
# partagé du haut de ce fichier : celui-ci accumule le cookie de session du dernier login réussi
# qui l'a utilisé, ce qui déclencherait à tort CSRFMiddleware sur ces routes pourtant publiques
# (voir app/auth/csrf.py — la vérification s'applique dès qu'un cookie de session est présent,
# quelle que soit la route visée).
# ============================================================================


def _fixer_le_prochain_jeton(monkeypatch, prefixes: list[str]) -> list[str]:
    """Fixe la valeur (secrets.token_urlsafe) renvoyée par les prochains appels à
    demander_reinitialisation, une par préfixe fourni, dans l'ordre — un suffixe uuid4 rend
    chaque valeur unique d'une exécution à l'autre : jeton_hache porte une contrainte unique en
    base, et cette suite d'intégration n'a pas d'isolation transactionnelle par test (la base de
    test/dev est partagée et persiste réellement les lignes commitées), donc un littéral fixe
    entrerait en collision dès la deuxième exécution de la suite."""
    valeurs = [f"{prefixe}-{uuid.uuid4()}" for prefixe in prefixes]
    it = iter(valeurs)
    monkeypatch.setattr("app.auth.password_reset.secrets.token_urlsafe", lambda _n: next(it))
    return valeurs


def _client_public() -> TestClient:
    return TestClient(app, base_url="https://testserver")


def test_mot_de_passe_oublie_repond_204_que_le_compte_existe_ou_non(session, monkeypatch) -> None:
    user = _create_utilisateur(session, password="s3cret-pass")
    _fixer_le_prochain_jeton(monkeypatch, ["jeton-connu"])

    reponse_connue = _client_public().post(
        "/api/v1/auth/mot-de-passe-oublie", json={"email": user.email}
    )
    reponse_inconnue = _client_public().post(
        "/api/v1/auth/mot-de-passe-oublie", json={"email": f"inconnu-{uuid.uuid4()}@example.com"}
    )

    assert reponse_connue.status_code == 204
    assert reponse_inconnue.status_code == 204


def test_mot_de_passe_oublie_cree_un_jeton_pour_un_compte_actif(session, monkeypatch) -> None:
    user = _create_utilisateur(session, password="s3cret-pass")
    (jeton,) = _fixer_le_prochain_jeton(monkeypatch, ["jeton-de-test"])

    _client_public().post("/api/v1/auth/mot-de-passe-oublie", json={"email": user.email})

    entree = session.exec(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id
        )
    ).one()
    assert entree.token_hash == _hash_token(jeton)
    assert entree.used_at is None
    assert entree.expires_at > utcnow()


def test_mot_de_passe_oublie_ne_cree_rien_pour_un_compte_desactive(session, monkeypatch) -> None:
    user = _create_utilisateur(session, password="s3cret-pass", actif=False)
    _fixer_le_prochain_jeton(monkeypatch, ["jeton-jamais-utilise"])

    response = _client_public().post("/api/v1/auth/mot-de-passe-oublie", json={"email": user.email})

    assert response.status_code == 204
    assert (
        session.exec(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == user.id
            )
        ).first()
        is None
    )


def test_mot_de_passe_oublie_invalide_le_lien_precedent(session, monkeypatch) -> None:
    """Une deuxième demande doit rendre la première inutilisable — jamais deux liens valides en
    même temps pour un même compte."""
    user = _create_utilisateur(session, password="s3cret-pass")
    (premier_jeton,) = _fixer_le_prochain_jeton(monkeypatch, ["premier-jeton"])
    _client_public().post("/api/v1/auth/mot-de-passe-oublie", json={"email": user.email})
    (second_jeton,) = _fixer_le_prochain_jeton(monkeypatch, ["second-jeton"])
    _client_public().post("/api/v1/auth/mot-de-passe-oublie", json={"email": user.email})

    reponse_premier = _client_public().post(
        "/api/v1/auth/reinitialiser-mot-de-passe",
        json={"token": premier_jeton, "new_password": "peu-importe-2"},
    )
    reponse_second = _client_public().post(
        "/api/v1/auth/reinitialiser-mot-de-passe",
        json={"token": second_jeton, "new_password": "nouveau-secret-3"},
    )

    assert reponse_premier.status_code == 422
    assert reponse_premier.json()["error"]["code"] == "jeton_invalide"
    assert reponse_second.status_code == 204


def test_mot_de_passe_oublie_is_rate_limited_regardless_of_whether_the_account_exists(
    session, monkeypatch
) -> None:
    """Le compteur de débit doit s'incrémenter même pour une adresse inconnue : un 429 qui
    n'apparaîtrait que pour un compte existant deviendrait lui-même un oracle d'énumération."""
    email_inconnu = f"inconnu-{uuid.uuid4()}@example.com"
    _fixer_le_prochain_jeton(monkeypatch, ["a", "b", "c"])

    for _ in range(3):
        response = _client_public().post(
            "/api/v1/auth/mot-de-passe-oublie", json={"email": email_inconnu}
        )
        assert response.status_code == 204

    blocked = _client_public().post(
        "/api/v1/auth/mot-de-passe-oublie", json={"email": email_inconnu}
    )
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "too_many_requests"


def test_reinitialiser_mot_de_passe_change_le_mot_de_passe_et_revoque_les_sessions(
    session, monkeypatch
) -> None:
    user = _create_utilisateur(session, password="ancien-secret")
    authed_client = TestClient(app, base_url="https://testserver")
    authed_client.post("/api/v1/auth/login", json={"email": user.email, "password": "ancien-secret"})
    ancien_cookie = authed_client.cookies[COOKIE_NAME]
    (jeton,) = _fixer_le_prochain_jeton(monkeypatch, ["jeton-de-reinitialisation"])
    _client_public().post("/api/v1/auth/mot-de-passe-oublie", json={"email": user.email})

    response = _client_public().post(
        "/api/v1/auth/reinitialiser-mot-de-passe",
        json={"token": jeton, "new_password": "nouveau-secret-2"},
    )

    assert response.status_code == 204
    session.refresh(user)
    assert user.password_hash is not None
    assert verify_password("nouveau-secret-2", user.password_hash)
    assert not verify_password("ancien-secret", user.password_hash)

    # L'ancienne session, ouverte avant la réinitialisation, est révoquée.
    stale_client = TestClient(app, base_url="https://testserver")
    stale_client.cookies.set(COOKIE_NAME, ancien_cookie)
    assert stale_client.get("/api/v1/auth/me").status_code == 401

    relog_ancien = _client_public().post(
        "/api/v1/auth/login", json={"email": user.email, "password": "ancien-secret"}
    )
    assert relog_ancien.status_code == 401
    relog_nouveau = _client_public().post(
        "/api/v1/auth/login", json={"email": user.email, "password": "nouveau-secret-2"}
    )
    assert relog_nouveau.status_code == 200


def test_reinitialiser_mot_de_passe_avec_un_jeton_deja_utilise_est_refuse(session, monkeypatch) -> None:
    user = _create_utilisateur(session, password="ancien-secret")
    (jeton,) = _fixer_le_prochain_jeton(monkeypatch, ["jeton-a-usage-unique"])
    _client_public().post("/api/v1/auth/mot-de-passe-oublie", json={"email": user.email})
    premiere = _client_public().post(
        "/api/v1/auth/reinitialiser-mot-de-passe",
        json={"token": jeton, "new_password": "nouveau-secret-2"},
    )
    assert premiere.status_code == 204

    rejouee = _client_public().post(
        "/api/v1/auth/reinitialiser-mot-de-passe",
        json={"token": jeton, "new_password": "encore-un-autre-3"},
    )

    assert rejouee.status_code == 422
    assert rejouee.json()["error"]["code"] == "jeton_invalide"


def test_reinitialiser_mot_de_passe_avec_un_jeton_expire_est_refuse(session) -> None:
    user = _create_utilisateur(session, password="ancien-secret")
    jeton = f"jeton-expire-{uuid.uuid4()}"
    session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=_hash_token(jeton),
            # Nettement dans le passé : expires_at=utcnow() pouvait tomber sur le même tic d'horloge
            # que la vérification (expires_at < utcnow()) et passer pour encore valide.
            expires_at=utcnow() - timedelta(minutes=1),
        )
    )
    session.commit()

    response = _client_public().post(
        "/api/v1/auth/reinitialiser-mot-de-passe",
        json={"token": jeton, "new_password": "peu-importe-2"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "jeton_invalide"


def test_reinitialiser_mot_de_passe_avec_un_jeton_inconnu_est_refuse() -> None:
    response = _client_public().post(
        "/api/v1/auth/reinitialiser-mot-de-passe",
        json={"token": "un-jeton-jamais-emis", "new_password": "peu-importe-2"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "jeton_invalide"


def test_password_reset_link_is_only_sent_by_email(
    session, monkeypatch, _mock_password_reset_delivery
) -> None:
    """Contrairement au mot de passe temporaire admin (renvoyé une fois dans la réponse,
    app/admin/utilisateurs.py), le jeton de réinitialisation ne doit jamais transiter par la
    réponse HTTP à l'appelant — seul le titulaire du compte, via le canal de livraison du lien
    par e-mail, doit pouvoir l'obtenir. Les journaux ne doivent jamais contenir le lien."""
    user = _create_utilisateur(session, password="s3cret-pass")
    (jeton,) = _fixer_le_prochain_jeton(monkeypatch, ["jeton-secret-a-ne-pas-fuiter"])

    with structlog.testing.capture_logs() as logs:
        response = _client_public().post(
            "/api/v1/auth/mot-de-passe-oublie", json={"email": user.email}
        )

    assert response.status_code == 204
    assert response.text in ("", "null")
    assert jeton not in response.text
    assert jeton not in str(logs)
    sent = _mock_password_reset_delivery.call_args.kwargs
    assert sent["recipient"] == user.email
    assert f"/reinitialiser-mot-de-passe?token={jeton}" in sent["body"]


def test_password_reset_delivery_failure_keeps_the_same_public_response(
    session, monkeypatch, _mock_password_reset_delivery
) -> None:
    user = _create_utilisateur(session, password="s3cret-pass")
    (jeton,) = _fixer_le_prochain_jeton(monkeypatch, ["jeton-confidentiel"])
    _mock_password_reset_delivery.side_effect = EmailDeliveryError("SMTP secret interne")

    with structlog.testing.capture_logs() as logs:
        known = _client_public().post(
            "/api/v1/auth/mot-de-passe-oublie", json={"email": user.email}
        )
        unknown = _client_public().post(
            "/api/v1/auth/mot-de-passe-oublie",
            json={"email": f"inconnu-{uuid.uuid4()}@example.com"},
        )

    assert known.status_code == unknown.status_code == 204
    assert known.content == unknown.content == b""
    assert _mock_password_reset_delivery.call_count == 1
    assert any(log["event"] == "password_reset_delivery_failed" for log in logs)
    assert jeton not in str(logs)
    assert user.email not in str(logs)
    assert "SMTP secret interne" not in str(logs)


def test_password_reset_without_smtp_returns_503_for_every_address(session, monkeypatch) -> None:
    user = _create_utilisateur(session, password="s3cret-pass")
    monkeypatch.setattr(
        "app.auth.password_reset.ensure_email_configured",
        Mock(side_effect=EmailDeliveryError("SMTP absent")),
    )

    known = _client_public().post(
        "/api/v1/auth/mot-de-passe-oublie", json={"email": user.email}
    )
    unknown = _client_public().post(
        "/api/v1/auth/mot-de-passe-oublie",
        json={"email": f"inconnu-{uuid.uuid4()}@example.com"},
    )

    assert known.status_code == unknown.status_code == 503
    assert known.json()["error"]["code"] == unknown.json()["error"]["code"] == "service_unavailable"
    assert known.json()["error"]["message"] == unknown.json()["error"]["message"]
    assert session.exec(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id
        )
    ).first() is None


def test_connexion_insensible_a_la_casse_de_lemail(session) -> None:
    user = _create_utilisateur(session, password="s3cret-pass")

    response = _client_public().post(
        "/api/v1/auth/login", json={"email": f"  {user.email.upper()} ", "password": "s3cret-pass"}
    )

    assert response.status_code == 200
    assert response.json()["email"] == user.email


def test_un_email_en_majuscules_ne_peut_jamais_etre_stocke(session) -> None:
    session.add(User(email=f"Majuscules-{uuid.uuid4()}@Example.com", role=Role.INVESTOR))
    with pytest.raises(IntegrityError, match="ck_users_email_lowercase"):
        session.commit()
    session.rollback()


@pytest.mark.parametrize("nouveau", ["court-11car", "x" * 73, "é" * 37])
def test_changer_mot_de_passe_applique_la_regle_12_a_72_octets(session, nouveau) -> None:
    user = _create_utilisateur(session, password="s3cret-pass")
    authed_client = _client_connecte(user, "s3cret-pass")

    response = authed_client.post(
        "/api/v1/auth/changer-mot-de-passe",
        json={"current_password": "s3cret-pass", "new_password": nouveau},
    )

    assert response.status_code == 422
    session.refresh(user)
    assert user.password_hash is not None
    assert verify_password("s3cret-pass", user.password_hash)


def test_changer_mot_de_passe_est_limite_comme_la_connexion(session) -> None:
    user = _create_utilisateur(session, password="s3cret-pass")
    authed_client = _client_connecte(user, "s3cret-pass")
    try:
        for _ in range(MAX_ATTEMPTS):
            echec = authed_client.post(
                "/api/v1/auth/changer-mot-de-passe",
                json={"current_password": "mauvais", "new_password": "nouveau-secret-12"},
            )
            assert echec.status_code == 401

        bloque = authed_client.post(
            "/api/v1/auth/changer-mot-de-passe",
            json={"current_password": "s3cret-pass", "new_password": "nouveau-secret-12"},
        )
        assert bloque.status_code == 429
    finally:
        clear_login_attempts(user.email)


def test_connexion_limitee_par_ip_meme_sur_des_comptes_differents(session) -> None:
    """Pulvérisation d'un mot de passe sur de nombreux comptes : chaque compte reste sous sa
    propre limite, c'est le compteur par IP qui bloque."""
    for _ in range(MAX_ATTEMPTS_PAR_IP):
        echec = _client_public().post(
            "/api/v1/auth/login",
            json={"email": f"inconnu-{uuid.uuid4()}@example.com", "password": "Printemps2026!"},
        )
        assert echec.status_code == 401

    user = _create_utilisateur(session, password="s3cret-pass")
    bloque = _client_public().post(
        "/api/v1/auth/login", json={"email": user.email, "password": "s3cret-pass"}
    )
    assert bloque.status_code == 429
