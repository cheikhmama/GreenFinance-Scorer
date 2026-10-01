import uuid

import pytest
from fastapi.testclient import TestClient

from app.auth.hashing import hash_password
from app.auth.models import User
from app.auth.tokens import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.core.enums import Role
from app.main import app

client = TestClient(app)

EXPECTED_TAGS = {
    "auth",
    "notifications",
    "admin",
    "audit",
    "company",
    "investor",
    "researcher",
    "institution",
}


def test_openapi_lists_a_tag_per_module() -> None:
    response = client.get("/api/v1/openapi.json")

    assert response.status_code == 200
    tags = {tag["name"] for tag in response.json().get("tags", [])}
    assert EXPECTED_TAGS <= tags


def test_health_remains_accessible_without_the_versioned_prefix() -> None:
    response = client.get("/health")

    assert response.status_code in (200, 503)
    assert client.get("/api/v1/health").status_code == 404


# Les tests CORS vivent dans tests/unit/test_cors.py : le câblage (api_app tire
# bien son origine de get_settings()) et le comportement de CORSMiddleware sont
# vérifiés indépendamment de tout .env local — voir le docstring de ce fichier.


# ============================================================================
# Balayage RBAC systématique (Phase 3 §3.4) — toutes les routes protégées,
# pas seulement une route représentative par espace comme le faisaient jusque
# là test_{admin,audit,company}_router.py.
# ============================================================================

_ID = str(uuid.uuid4())

# (méthode, chemin, rôle requis — None = n'importe quel compte authentifié, corps JSON minimal
# valide si la route en attend un — un 401/403 doit intervenir avant toute validation métier du
# contenu, mais un corps absent pourrait produire un 422 qui masquerait le vrai test ici).
_ROUTES: list[tuple[str, str, Role | None, dict[str, object] | None]] = [
    ("POST", "/auth/logout", None, None),
    ("GET", "/auth/me", None, None),
    ("POST", "/auth/changer-mot-de-passe", None, {"current_password": "x", "new_password": "y"}),
    ("GET", "/notifications", None, None),
    ("POST", f"/notifications/{_ID}/lu", None, None),
    ("GET", "/admin/utilisateurs?role=AUDITOR", Role.ADMIN, None),
    ("POST", "/admin/utilisateurs", Role.ADMIN, {"email": "x@example.com", "role": "AUDITOR"}),
    ("POST", f"/admin/utilisateurs/{_ID}/desactiver", Role.ADMIN, None),
    ("GET", "/admin/rapports/a-affecter", Role.ADMIN, None),
    ("POST", f"/admin/rapports/{_ID}/affecter", Role.ADMIN, {"auditor_id": _ID}),
    ("GET", "/admin/rapports/en-validation", Role.ADMIN, None),
    ("GET", f"/admin/rapports/{_ID}", Role.ADMIN, None),
    ("GET", f"/admin/rapports/{_ID}/avis", Role.ADMIN, None),
    ("POST", f"/admin/rapports/{_ID}/valider", Role.ADMIN, {}),
    ("POST", f"/admin/rapports/{_ID}/rejeter", Role.ADMIN, {}),
    ("POST", f"/admin/rapports/{_ID}/demander-correction", Role.ADMIN, {}),
    ("GET", "/admin/entreprises", Role.ADMIN, None),
    ("GET", "/admin/entreprises/publiables", Role.ADMIN, None),
    ("GET", f"/admin/entreprises/{_ID}", Role.ADMIN, None),
    (
        "PATCH",
        f"/admin/entreprises/{_ID}",
        Role.ADMIN,
        {"name": "x", "sector": "y", "country": "z"},
    ),
    ("POST", f"/admin/entreprises/{_ID}/publier", Role.ADMIN, None),
    ("GET", "/audit/rapports", Role.AUDITOR, None),
    ("GET", f"/audit/rapports/{_ID}", Role.AUDITOR, None),
    ("POST", f"/audit/rapports/{_ID}/avis", Role.AUDITOR, {"decision": "FAVORABLE"}),
    ("GET", f"/company/rapports/{_ID}", Role.ENTERPRISE, None),
]

# Aucune route ci-dessus n'exige CHERCHEUR — un choix de « mauvais rôle » systématique et sûr
# pour chacune, y compris pour /company (qui exige ENTREPRISE).
_MAUVAIS_ROLE = Role.RESEARCHER


def _creer_et_connecter(session, role: Role) -> TestClient:
    utilisateur = User(
        email=f"rbac-{role.value.lower()}-{uuid.uuid4()}@example.com",
        password_hash=hash_password("s3cret-pass"),
        role=role,
        active=True,
    )
    session.add(utilisateur)
    session.commit()

    authed_client = TestClient(app, base_url="https://testserver")
    response = authed_client.post(
        "/api/v1/auth/login", json={"email": utilisateur.email, "password": "s3cret-pass"}
    )
    assert response.status_code == 200
    authed_client.headers.update({CSRF_HEADER_NAME: authed_client.cookies[CSRF_COOKIE_NAME]})
    return authed_client


@pytest.mark.parametrize("methode,chemin,role_requis,corps", _ROUTES)
def test_route_sans_authentification_est_rejetee(
    methode: str, chemin: str, role_requis: Role | None, corps: dict[str, object] | None
) -> None:
    anonymous_client = TestClient(app, base_url="https://testserver")

    response = anonymous_client.request(methode, f"/api/v1{chemin}", json=corps)

    assert response.status_code == 401, f"{methode} {chemin} : attendu 401, reçu {response.status_code}"
    assert response.json()["error"]["code"] in ("not_authenticated", "invalid_token")


@pytest.mark.parametrize("methode,chemin,role_requis,corps", _ROUTES)
def test_route_avec_le_mauvais_role_est_rejetee(
    session, methode: str, chemin: str, role_requis: Role | None, corps: dict[str, object] | None
) -> None:
    if role_requis is None:
        pytest.skip("route accessible à tout compte authentifié, aucun « mauvais rôle » à tester")

    authed_client = _creer_et_connecter(session, _MAUVAIS_ROLE)

    response = authed_client.request(methode, f"/api/v1{chemin}", json=corps)

    assert response.status_code == 403, f"{methode} {chemin} : attendu 403, reçu {response.status_code}"
    assert response.json()["error"]["code"] == "permission_denied"
