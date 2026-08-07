"""Tests for the /api/v1/version endpoint."""

from fastapi.testclient import TestClient

from config import get_settings
from main import app

client = TestClient(app)


def test_version_returns_200():
    response = client.get("/api/v1/version")
    assert response.status_code == 200


def test_version_response_envelope_matches_settings():
    settings = get_settings()
    response = client.get("/api/v1/version")
    body = response.json()

    assert body["success"] is True
    assert body["data"]["name"] == settings.APP_NAME
    assert body["data"]["version"] == settings.APP_VERSION
    assert body["data"]["environment"] == settings.ENVIRONMENT
    assert "request_id" in body and body["request_id"]
    assert "timestamp" in body
