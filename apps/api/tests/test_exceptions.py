"""Tests for global exception handling (HTTPException / 404s)."""

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_unknown_route_returns_standard_error_envelope():
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404

    body = response.json()
    assert body["success"] is False
    assert body["data"] is None
    assert "request_id" in body and body["request_id"]
    assert "timestamp" in body


def test_unknown_route_includes_request_id_header():
    response = client.get("/api/v1/does-not-exist")
    assert "X-Request-ID" in response.headers
    assert response.headers["X-Request-ID"] == response.json()["request_id"]
