import uuid

from fastapi.testclient import TestClient

from app.auth.hashing import hash_password
from app.auth.models import Utilisateur
from app.auth.tokens import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.core.enums import Role
from app.core.models import Notification
from app.main import app

client = TestClient(app, base_url="https://testserver")


def _create_utilisateur(session, role: Role, *, password: str = "s3cret-pass") -> Utilisateur:
    user = Utilisateur(
        email=f"{role.value.lower()}-{uuid.uuid4()}@example.com",
        mot_de_passe_hache=hash_password(password),
        role=role,
        actif=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _create_notification(session, utilisateur_id: uuid.UUID, *, lu: bool = False) -> Notification:
    notification = Notification(
        utilisateur_id=utilisateur_id, type="TEST", message="Message de test.", lu=lu
    )
    session.add(notification)
    session.commit()
    session.refresh(notification)
    return notification


def _login(email: str, password: str) -> TestClient:
    authed_client = TestClient(app, base_url="https://testserver")
    response = authed_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    authed_client.headers.update({CSRF_HEADER_NAME: authed_client.cookies[CSRF_COOKIE_NAME]})
    return authed_client


def test_lister_mes_notifications_ne_montre_que_les_miennes(session) -> None:
    utilisateur = _create_utilisateur(session, Role.ENTREPRISE)
    autre = _create_utilisateur(session, Role.ENTREPRISE)
    ma_notification = _create_notification(session, utilisateur.id)
    _create_notification(session, autre.id)

    authed_client = _login(utilisateur.email, "s3cret-pass")
    response = authed_client.get("/api/v1/notifications")

    assert response.status_code == 200
    body = response.json()
    ids = [item["id"] for item in body["items"]]
    assert str(ma_notification.id) in ids
    assert len(ids) == 1
    assert body["total"] == 1


def test_lister_mes_notifications_plus_recente_dabord(session) -> None:
    utilisateur = _create_utilisateur(session, Role.AUDITEUR)
    premiere = _create_notification(session, utilisateur.id)
    deuxieme = _create_notification(session, utilisateur.id)

    authed_client = _login(utilisateur.email, "s3cret-pass")
    response = authed_client.get("/api/v1/notifications")

    ids = [item["id"] for item in response.json()["items"]]
    assert ids.index(str(deuxieme.id)) < ids.index(str(premiere.id))


def test_lister_mes_notifications_filtre_non_lues_seulement(session) -> None:
    utilisateur = _create_utilisateur(session, Role.AUDITEUR)
    non_lue = _create_notification(session, utilisateur.id, lu=False)
    _create_notification(session, utilisateur.id, lu=True)

    authed_client = _login(utilisateur.email, "s3cret-pass")
    response = authed_client.get("/api/v1/notifications", params={"non_lues_seulement": True})

    ids = [item["id"] for item in response.json()["items"]]
    assert ids == [str(non_lue.id)]


def test_marquer_lue_change_le_statut(session) -> None:
    utilisateur = _create_utilisateur(session, Role.CHERCHEUR)
    notification = _create_notification(session, utilisateur.id, lu=False)

    authed_client = _login(utilisateur.email, "s3cret-pass")
    response = authed_client.post(f"/api/v1/notifications/{notification.id}/lu")

    assert response.status_code == 200
    assert response.json()["lu"] is True
    session.refresh(notification)
    assert notification.lu is True


def test_marquer_lue_est_idempotent(session) -> None:
    utilisateur = _create_utilisateur(session, Role.AUDITEUR)
    notification = _create_notification(session, utilisateur.id, lu=True)
    authed_client = _login(utilisateur.email, "s3cret-pass")

    response = authed_client.post(f"/api/v1/notifications/{notification.id}/lu")

    assert response.status_code == 200
    assert response.json()["lu"] is True


def test_marquer_lue_dune_notification_dautrui_est_404(session) -> None:
    utilisateur = _create_utilisateur(session, Role.AUDITEUR)
    autre = _create_utilisateur(session, Role.AUDITEUR)
    notification_dautrui = _create_notification(session, autre.id)

    authed_client = _login(utilisateur.email, "s3cret-pass")
    response = authed_client.post(f"/api/v1/notifications/{notification_dautrui.id}/lu")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "notification_introuvable"


def test_marquer_lue_notification_inexistante_est_404(session) -> None:
    utilisateur = _create_utilisateur(session, Role.AUDITEUR)
    authed_client = _login(utilisateur.email, "s3cret-pass")

    response = authed_client.post(f"/api/v1/notifications/{uuid.uuid4()}/lu")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "notification_introuvable"


def test_lister_notifications_sans_authentification_est_401() -> None:
    response = client.get("/api/v1/notifications")

    assert response.status_code == 401


def test_marquer_lue_sans_authentification_est_401() -> None:
    response = client.post(f"/api/v1/notifications/{uuid.uuid4()}/lu")

    assert response.status_code == 401
