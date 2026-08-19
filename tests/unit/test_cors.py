"""Tests CORS — volontairement indépendants de tout .env local.

Deux préoccupations séparées :
1. le câblage réel de api_app pull bien son origine depuis get_settings()
   (test_api_app_wires_cors_from_settings) — sans jamais supposer une valeur
   précise, juste que le middleware réutilise exactement ce que la config
   renvoie, quel que soit son contenu ;
2. le comportement de CORSMiddleware pour une origine explicite choisie par
   le test — sur une application FastAPI jetable construite ici (voir
   ARCHITECTURE.md §7), jamais sur l'app réelle dont l'origine active
   dépendrait du .env de la machine qui exécute les tests.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient


def _make_test_app(allowed_origins: list[str]) -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/probe")
    def probe() -> dict[str, bool]:
        return {"ok": True}

    return app


def test_api_app_wires_cors_from_settings() -> None:
    from app.api.router import api_app
    from app.core.config import get_settings

    cors_entries = [mw for mw in api_app.user_middleware if mw.cls is CORSMiddleware]
    assert len(cors_entries) == 1, "api_app doit porter exactement un CORSMiddleware"

    options = cors_entries[0].kwargs
    assert options["allow_origins"] == get_settings().cors_allowed_origins_list
    assert options["allow_credentials"] is True


def test_cors_allows_a_configured_origin_with_credentials() -> None:
    app = _make_test_app(["http://example-frontend.test"])
    client = TestClient(app)

    response = client.options(
        "/probe",
        headers={
            "Origin": "http://example-frontend.test",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://example-frontend.test"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_cors_rejects_an_unlisted_origin() -> None:
    app = _make_test_app(["http://example-frontend.test"])
    client = TestClient(app)

    response = client.options(
        "/probe",
        headers={
            "Origin": "http://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert "access-control-allow-origin" not in response.headers


def test_cors_reflects_any_origin_when_misconfigured_with_a_wildcard() -> None:
    """Documente (empiriquement vérifié) le piège réel que app/core/config.py
    ferme désormais explicitement : CORSMiddleware ne refuse PAS
    allow_origins=["*"] combiné à allow_credentials=True — il reflète
    l'origine de la requête telle quelle, ce qui autoriserait n'importe quel
    site à appeler l'API avec le cookie de session. C'est exactement pour
    empêcher ce cas que Settings.cors_allowed_origins_list lève une erreur
    si "*" y figure (voir test_config.py) — jamais construit ainsi en usage
    réel, ce test-ci documente juste pourquoi le garde-fou existe."""
    app = _make_test_app(["*"])
    client = TestClient(app)

    response = client.options(
        "/probe",
        headers={
            "Origin": "http://n-importe-quoi.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.headers.get("access-control-allow-origin") == "http://n-importe-quoi.example.com"
