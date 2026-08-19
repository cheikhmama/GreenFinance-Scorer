from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

EXPECTED_TAGS = {
    "auth",
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
