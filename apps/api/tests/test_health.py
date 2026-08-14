"""Smoke tests for the health endpoints."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_v1_ping() -> None:
    response = client.get("/api/v1/ping")
    assert response.status_code == 200
    assert response.json()["service"] == "rankpilot-api"
