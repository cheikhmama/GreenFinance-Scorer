"""En-têtes de sécurité (app/core/security_headers.py) : posés partout, sans écraser une route."""

from fastapi import FastAPI, Response
from fastapi.testclient import TestClient

from app.core.security_headers import SecurityHeadersMiddleware


def _client(*, hsts: bool = False) -> TestClient:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware, hsts=hsts)

    @app.get("/api/v1/x")
    def api() -> dict[str, str]:
        return {"ok": "1"}

    @app.get("/api/v1/cache")
    def cache(response: Response) -> dict[str, str]:
        response.headers["Cache-Control"] = "max-age=60"
        return {"ok": "1"}

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"ok": "1"}

    return TestClient(app)


def test_en_tetes_poses_sur_lapi() -> None:
    reponse = _client().get("/api/v1/x")
    assert reponse.headers["x-content-type-options"] == "nosniff"
    assert reponse.headers["x-frame-options"] == "DENY"
    assert reponse.headers["referrer-policy"] == "no-referrer"
    assert reponse.headers["cache-control"] == "no-store"
    assert "strict-transport-security" not in reponse.headers


def test_cache_control_dune_route_conserve_et_hors_api_absent() -> None:
    client = _client()
    assert client.get("/api/v1/cache").headers["cache-control"] == "max-age=60"
    sante = client.get("/health")
    assert sante.headers["x-frame-options"] == "DENY"
    assert "cache-control" not in sante.headers


def test_hsts_en_production() -> None:
    reponse = _client(hsts=True).get("/health")
    assert reponse.headers["strict-transport-security"].startswith("max-age=31536000")
