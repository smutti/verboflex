"""Executable contract for the public health endpoint."""

from fastapi.testclient import TestClient

from verboflex.main import app


def test_health_endpoint_is_constant_and_non_sensitive() -> None:
    """Return only the exact approved liveness payload."""
    response = TestClient(app).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
