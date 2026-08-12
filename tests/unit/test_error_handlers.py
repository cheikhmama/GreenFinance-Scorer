from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.exceptions import (
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
    register_exception_handlers,
)


def _build_test_app() -> FastAPI:
    """App FastAPI jetable, isolée, portant les routes de test temporaires
    nécessaires pour exercer les gestionnaires d'erreurs sans polluer
    l'application réelle."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom/not-found")
    def boom_not_found() -> None:
        raise NotFoundError("Entreprise introuvable")

    @app.get("/boom/validation")
    def boom_validation() -> None:
        raise ValidationError("Champ invalide")

    @app.get("/boom/permission")
    def boom_permission() -> None:
        raise PermissionDeniedError("Accès refusé")

    @app.get("/boom/generic")
    def boom_generic() -> None:
        raise ZeroDivisionError("secret-internal-detail")

    return app


client = TestClient(_build_test_app(), raise_server_exceptions=False)


def test_not_found_error_returns_404_structured() -> None:
    response = client.get("/boom/not-found")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == "Entreprise introuvable"
    assert "correlation_id" in body["error"]


def test_validation_error_returns_422_structured() -> None:
    response = client.get("/boom/validation")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_permission_denied_error_returns_403_structured() -> None:
    response = client.get("/boom/permission")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"


def test_generic_exception_returns_500_without_leaking_traceback() -> None:
    response = client.get("/boom/generic")

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert "secret-internal-detail" not in response.text
    assert "Traceback" not in response.text
    assert "ZeroDivisionError" not in response.text
